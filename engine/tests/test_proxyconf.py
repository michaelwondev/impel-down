from impel.proxyconf import parse_services, parse_proxy, ensure_all, clear_all

SERVICES = """An asterisk (*) denotes that a network service is disabled.
USB 10/100/1000 LAN
*Thunderbolt Bridge
Wi-Fi
iPhone USB
"""

OFF = """Enabled: No
Server:
Port: 0
Authenticated Proxy Enabled: 0
"""

ON = """Enabled: Yes
Server: 127.0.0.1
Port: 8899
Authenticated Proxy Enabled: 0
"""


def test_parse_services_skips_header_and_disabled():
    assert parse_services(SERVICES) == ["USB 10/100/1000 LAN", "Wi-Fi", "iPhone USB"]


def test_parse_proxy():
    assert parse_proxy(OFF) == (False, "", 0)
    assert parse_proxy(ON) == (True, "127.0.0.1", 8899)


class FakeRunner:
    def __init__(self, state, deny=()):
        self.state = state  # (service, kind) -> (enabled, server, port)
        self.deny = set(deny)  # setter를 무시하는 서비스 (설정 거부 흉내)
        self.calls = []

    def __call__(self, cmd):
        self.calls.append(cmd)
        if cmd[1] == "-listallnetworkservices":
            return SERVICES
        kind = "web" if "webproxy" in cmd[1] and "secure" not in cmd[1] else "secure"
        svc = cmd[2]
        if cmd[1] in ("-getwebproxy", "-getsecurewebproxy"):
            en, s, p = self.state.get((svc, kind), (False, "", 0))
            return "Enabled: %s\nServer: %s\nPort: %d\nAuthenticated Proxy Enabled: 0\n" % ("Yes" if en else "No", s, p)
        if cmd[1] in ("-setwebproxy", "-setsecurewebproxy"):
            if svc not in self.deny:
                self.state[(svc, kind)] = (True, cmd[3], int(cmd[4]))
            return ""
        if cmd[1] in ("-setwebproxystate", "-setsecurewebproxystate"):
            en, s, p = self.state.get((svc, kind), (False, "", 0))
            self.state[(svc, kind)] = (cmd[3] == "on", s, p)
            return ""
        raise AssertionError("unexpected command %r" % cmd)


def test_ensure_all_sets_missing_only():
    r = FakeRunner({("Wi-Fi", "web"): (True, "127.0.0.1", 8899)})
    changed, failed = ensure_all("127.0.0.1", 8899, runner=r)
    assert ["networksetup", "-setwebproxy", "Wi-Fi", "127.0.0.1", "8899"] not in r.calls  # 이미 맞던 건 안 건드림
    assert r.state[("Wi-Fi", "secure")] == (True, "127.0.0.1", 8899)
    assert r.state[("USB 10/100/1000 LAN", "web")] == (True, "127.0.0.1", 8899)
    assert ("Thunderbolt Bridge", "web") not in r.state  # 비활성 서비스는 건드리지 않음
    assert len(changed) == 5 and failed == []  # 3 서비스 × 2 - 이미 맞던 1


def test_ensure_all_fixes_wrong_port():
    r = FakeRunner({("Wi-Fi", "web"): (True, "127.0.0.1", 1234)})
    changed, _ = ensure_all("127.0.0.1", 8899, runner=r)
    assert r.state[("Wi-Fi", "web")] == (True, "127.0.0.1", 8899)
    assert "Wi-Fi -setwebproxy" in changed


def test_ensure_all_noop_when_all_set():
    state = {(s, k): (True, "127.0.0.1", 8899)
             for s in ["USB 10/100/1000 LAN", "Wi-Fi", "iPhone USB"] for k in ("web", "secure")}
    r = FakeRunner(state)
    assert ensure_all("127.0.0.1", 8899, runner=r) == ([], [])
    assert not [c for c in r.calls if c[1].startswith("-set")]


def test_ensure_all_reports_failed_service():
    # setter가 먹히지 않은 서비스는 changed가 아니라 failed로
    r = FakeRunner({}, deny={"iPhone USB"})
    changed, failed = ensure_all("127.0.0.1", 8899, runner=r)
    assert failed == ["iPhone USB -setwebproxy", "iPhone USB -setsecurewebproxy"]
    assert not [c for c in changed if c.startswith("iPhone USB")]
    assert len(changed) == 4


def test_clear_all_turns_off_every_active_service():
    state = {("Wi-Fi", "web"): (True, "127.0.0.1", 8899), ("Wi-Fi", "secure"): (True, "127.0.0.1", 8899)}
    r = FakeRunner(state)
    clear_all(runner=r)
    assert r.state[("Wi-Fi", "web")][0] is False and r.state[("Wi-Fi", "secure")][0] is False
    assert [c[2] for c in r.calls if c[1] == "-setwebproxystate"] == ["USB 10/100/1000 LAN", "Wi-Fi", "iPhone USB"]
