from impel.proxyconf import parse_services, parse_proxy, ensure_all, clear_all

SERVICES = """An asterisk (*) denotes that a network service is disabled.
USB 10/100/1000 LAN
*Thunderbolt Bridge
Wi-Fi
iPhone USB
"""


def test_parse_services_skips_header_and_disabled():
    assert parse_services(SERVICES) == ["USB 10/100/1000 LAN", "Wi-Fi", "iPhone USB"]


def test_parse_proxy():
    assert parse_proxy("Enabled: No\nServer:\nPort: 0\nAuthenticated Proxy Enabled: 0\n") == (False, "", 0)
    assert parse_proxy("Enabled: Yes\nServer: 127.0.0.1\nPort: 8899\nAuthenticated Proxy Enabled: 0\n") == (True, "127.0.0.1", 8899)


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


def test_ensure_all_sets_only_what_is_missing_or_wrong():
    r = FakeRunner({("Wi-Fi", "web"): (True, "127.0.0.1", 8899), ("Wi-Fi", "secure"): (True, "127.0.0.1", 1234)})
    changed, failed = ensure_all("127.0.0.1", 8899, runner=r)
    assert ["networksetup", "-setwebproxy", "Wi-Fi", "127.0.0.1", "8899"] not in r.calls  # 이미 맞던 건 안 건드림
    assert r.state[("Wi-Fi", "secure")] == (True, "127.0.0.1", 8899)  # 포트가 틀리면 고침
    assert ("Thunderbolt Bridge", "web") not in r.state  # 비활성 서비스는 건드리지 않음
    assert len(changed) == 5 and failed == []  # 3 서비스 × 2 - 이미 맞던 1
    assert ensure_all("127.0.0.1", 8899, runner=r) == ([], [])  # 다 맞으면 아무것도 안 함


def test_ensure_all_reports_failed_service():
    r = FakeRunner({}, deny={"iPhone USB"})
    changed, failed = ensure_all("127.0.0.1", 8899, runner=r)
    assert failed == ["iPhone USB -setwebproxy", "iPhone USB -setsecurewebproxy"]
    assert len(changed) == 4 and not [c for c in changed if c.startswith("iPhone USB")]


def test_clear_all_turns_off_every_active_service():
    r = FakeRunner({("Wi-Fi", "web"): (True, "127.0.0.1", 8899), ("Wi-Fi", "secure"): (True, "127.0.0.1", 8899)})
    clear_all(runner=r)
    assert r.state[("Wi-Fi", "web")][0] is False and r.state[("Wi-Fi", "secure")][0] is False
    assert [c[2] for c in r.calls if c[1] == "-setwebproxystate"] == ["USB 10/100/1000 LAN", "Wi-Fi", "iPhone USB"]
