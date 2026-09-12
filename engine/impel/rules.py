"""규칙 파일 로드·검증, 주소 매칭, 시간표 판정. mitmproxy에 의존하지 않는다."""
import re
from dataclasses import dataclass
from typing import Optional

_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def is_valid_hostname(host: str) -> bool:
    return bool(_HOST_RE.match(host))


def normalize_address(text: str) -> str:
    """붙여넣은 주소를 규칙 주소로 정리한다. 앱의 정리 규칙과 같다.

    scheme · 앞의 www. · 끝의 / · ? 뒤 · # 뒤를 떼고 host+path만 남긴다. host는 소문자.
    """
    s = _SCHEME_RE.sub("", text.strip())
    s = s.split("#", 1)[0].split("?", 1)[0]
    if "/" in s:
        host, rest = s.split("/", 1)
        path = "/" + rest.strip("/")
    else:
        host, path = s, ""
    host = host.lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if path == "/":
        path = ""
    return host + path


@dataclass(frozen=True)
class Address:
    host: str
    path: Optional[str]  # None = 호스트 통째. 있으면 "/"로 시작, 끝 "/" 없음

    @staticmethod
    def parse(text: str) -> "Address":
        s = normalize_address(text)
        if "/" in s:
            host, rest = s.split("/", 1)
            path = "/" + rest  # type: Optional[str]
        else:
            host, path = s, None
        if not is_valid_hostname(host):
            raise ValueError("invalid host in address: %r" % text)
        return Address(host, path)

    def matches_host(self, host: str) -> bool:
        h = host.lower().rstrip(".")
        return h == self.host or h.endswith("." + self.host)

    def matches(self, host: str, path: str) -> bool:
        if not self.matches_host(host):
            return False
        if self.path is None:
            return True
        p = path.split("?", 1)[0]
        return p == self.path or p.startswith(self.path + "/")
