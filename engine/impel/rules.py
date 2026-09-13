"""규칙 파일 로드·검증, 주소 매칭, 시간표 판정. mitmproxy에 의존하지 않는다."""
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, FrozenSet, List, Optional

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # index == datetime.weekday()
_WEEK_HOURS = 24 * 7
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


@dataclass
class Group:
    id: str
    title: str
    addresses: List[Address]
    open_hours: Dict[int, FrozenSet[int]]  # weekday(0=월) -> 열린 시각(그 시부터 한 시간)

    def is_open(self, at: datetime) -> bool:
        return at.hour in self.open_hours.get(at.weekday(), frozenset())

    def always_closed(self) -> bool:
        return not any(self.open_hours.values())

    def next_open(self, at: datetime) -> Optional[datetime]:
        """지금 이후 첫 열린 칸의 시작 시각. 7일 안에 없으면 None."""
        start = at.replace(minute=0, second=0, microsecond=0)
        for offset in range(1, _WEEK_HOURS + 1):
            t = start + timedelta(hours=offset)
            if t.hour in self.open_hours.get(t.weekday(), frozenset()):
                return t
        return None

    def matches(self, host: str, path: str) -> bool:
        return any(a.matches(host, path) for a in self.addresses)


@dataclass
class Rules:
    groups: List[Group]

    @staticmethod
    def empty() -> "Rules":
        return Rules([])

    @staticmethod
    def from_json(text: str) -> "Rules":
        """rules.json 본문을 파싱·검증한다. 어긋나면 ValueError."""
        doc = json.loads(text)  # JSONDecodeError는 ValueError의 하위 클래스
        if not isinstance(doc, dict) or doc.get("version") != 1:
            raise ValueError("unsupported rules document")
        raw_groups = doc.get("groups", [])
        if not isinstance(raw_groups, list):
            raise ValueError("groups must be a list")
        groups = []
        for g in raw_groups:
            if not isinstance(g, dict):
                raise ValueError("group must be an object")
            gid = g.get("id")
            if not isinstance(gid, str) or not gid:
                raise ValueError("group id required")
            title = g.get("title", "")
            if not isinstance(title, str):
                raise ValueError("title must be a string")
            raw_addrs = g.get("addresses", [])
            if not isinstance(raw_addrs, list):
                raise ValueError("addresses must be a list")
            if not all(isinstance(a, str) for a in raw_addrs):
                raise ValueError("addresses must be strings")
            addresses = [Address.parse(a) for a in raw_addrs if a.strip()]  # 빈 줄만 건너뛴다
            raw_open = g.get("open") or {}
            if not isinstance(raw_open, dict):
                raise ValueError("open must be an object")
            open_hours = {}  # type: Dict[int, FrozenSet[int]]
            for key, hours in raw_open.items():
                if key not in DAY_KEYS:
                    raise ValueError("unknown day key: %r" % key)
                if not isinstance(hours, list) or not all(
                    isinstance(h, int) and not isinstance(h, bool) and 0 <= h <= 23 for h in hours
                ):
                    raise ValueError("hours for %s must be integers 0..23" % key)
                open_hours[DAY_KEYS.index(key)] = frozenset(hours)
            groups.append(Group(gid, title, addresses, open_hours))
        return Rules(groups)

    def intercept_host(self, host: str) -> bool:
        return any(a.matches_host(host) for g in self.groups for a in g.addresses)

    def decide(self, host: str, path: str, at: datetime) -> Optional[Group]:
        """차단해야 하면 그 묶음(여럿이면 첫째), 아니면 None."""
        for g in self.groups:
            if g.matches(host, path) and not g.is_open(at):
                return g
        return None

    def mirror_hosts(self) -> List[str]:
        """hosts 블록에 미러할 호스트: 24시간 차단 묶음의 호스트 통째 주소 + www. 변형."""
        out = set()
        for g in self.groups:
            if not g.always_closed():
                continue
            for a in g.addresses:
                if a.path is None:
                    out.add(a.host)
                    out.add("www." + a.host)
        return sorted(out)


class RulesFile:
    """규칙 파일을 수정 시각 기준으로 다시 읽는다. 실패하면 직전 규칙을 유지한다."""

    def __init__(self, path: str, log: Optional[Callable[[str], None]] = None):
        self.path = path
        self.version = 0
        self._mtime = None  # type: Optional[int]
        self._rules = Rules.empty()
        self._log = log or (lambda msg: None)

    def current(self) -> Rules:
        try:
            mtime = os.stat(self.path).st_mtime_ns
        except FileNotFoundError:
            return self._rules
        if mtime == self._mtime:
            return self._rules
        self._mtime = mtime
        try:
            with open(self.path, encoding="utf-8") as f:
                text = f.read()
            self._rules = Rules.from_json(text)
            self.version += 1
        except (OSError, ValueError) as e:
            self._log("rules reload failed: %s" % e)
        return self._rules
