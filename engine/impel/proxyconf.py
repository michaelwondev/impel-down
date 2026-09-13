"""macOS 시스템 프록시(HTTP·HTTPS)를 networksetup으로 읽고 유지한다."""
import subprocess
from typing import Callable, List, Tuple

Runner = Callable[[List[str]], str]

_PAIRS = (("-getwebproxy", "-setwebproxy", "-setwebproxystate"),
          ("-getsecurewebproxy", "-setsecurewebproxy", "-setsecurewebproxystate"))


def run(cmd: List[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout


def parse_services(text: str) -> List[str]:
    """`networksetup -listallnetworkservices` 출력에서 활성 서비스 이름만.
    첫 줄은 안내문, `*`로 시작하면 비활성."""
    names = []
    for line in text.splitlines()[1:]:
        s = line.strip()
        if s and not s.startswith("*"):
            names.append(s)
    return names


def parse_proxy(text: str) -> Tuple[bool, str, int]:
    """`networksetup -getwebproxy <svc>` 출력 → (enabled, server, port)."""
    enabled, server, port = False, "", 0
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "Enabled":
            enabled = value == "Yes"
        elif key == "Server":
            server = value
        elif key == "Port":
            port = int(value) if value.isdigit() else 0
    return enabled, server, port


def _is_set(runner: Runner, getter: str, svc: str, host: str, port: int) -> bool:
    enabled, server, current_port = parse_proxy(runner(["networksetup", getter, svc]))
    return enabled and server == host and current_port == port


def ensure_all(host: str, port: int, runner: Runner = run) -> Tuple[List[str], List[str]]:
    """모든 활성 서비스의 HTTP·HTTPS 프록시를 host:port로 맞춘다.

    setter 뒤 getter로 재확인해 (실제 바뀐 항목, 설정이 안 먹힌 항목)을 돌려준다.
    """
    changed, failed = [], []
    for svc in parse_services(runner(["networksetup", "-listallnetworkservices"])):
        for getter, setter, _ in _PAIRS:
            if _is_set(runner, getter, svc, host, port):
                continue
            runner(["networksetup", setter, svc, host, str(port)])
            label = "%s %s" % (svc, setter)
            (changed if _is_set(runner, getter, svc, host, port) else failed).append(label)
    return changed, failed


def clear_all(runner: Runner = run) -> None:
    for svc in parse_services(runner(["networksetup", "-listallnetworkservices"])):
        for _, _, state_setter in _PAIRS:
            runner(["networksetup", state_setter, svc, "off"])
