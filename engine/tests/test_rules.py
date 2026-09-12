import pytest
from impel.rules import Address, normalize_address, is_valid_hostname


@pytest.mark.parametrize("raw, expected", [
    ("community.example", "community.example"),
    ("https://www.community.example/", "community.example"),
    ("http://Community.Example/board/list/?id=abc", "community.example/board/list"),
    ("video.example/shorts/abc123#top", "video.example/shorts/abc123"),
    ("  video.example/shorts/  ", "video.example/shorts"),
    ("www.video.example", "video.example"),
])
def test_normalize_address(raw, expected):
    assert normalize_address(raw) == expected


@pytest.mark.parametrize("host, ok", [
    ("community.example", True),
    ("a.b.community.example", True),
    ("x-y.example", True),
    ("-bad.example", False),
    ("nodot", False),
    ("has space.example", False),
    ("community.example/path", False),
    ("", False),
])
def test_is_valid_hostname(host, ok):
    assert is_valid_hostname(host) is ok


def test_parse_whole_host():
    a = Address.parse("https://www.community.example/")
    assert a.host == "community.example" and a.path is None


def test_parse_with_path():
    a = Address.parse("video.example/shorts/")
    assert a.host == "video.example" and a.path == "/shorts"


def test_parse_rejects_bad_host():
    with pytest.raises(ValueError):
        Address.parse("not a host")


@pytest.mark.parametrize("host, expected", [
    ("community.example", True),
    ("gall.community.example", True),
    ("COMMUNITY.EXAMPLE", True),
    ("notcommunity.example", False),
    ("community.example.evil", False),
])
def test_matches_host(host, expected):
    assert Address.parse("community.example").matches_host(host) is expected


@pytest.mark.parametrize("host, path, expected", [
    ("video.example", "/shorts", True),
    ("video.example", "/shorts/abc", True),
    ("m.video.example", "/shorts?x=1", True),
    ("video.example", "/shortsx", False),
    ("video.example", "/", False),
    ("other.example", "/shorts", False),
])
def test_matches_path(host, path, expected):
    assert Address.parse("video.example/shorts").matches(host, path) is expected


def test_whole_host_matches_any_path():
    assert Address.parse("community.example").matches("community.example", "/anything?q=1") is True


# ---- Task 2: 시간표 판정·다음 열림 ----
from datetime import datetime
from impel.rules import Group, DAY_KEYS


def _group(open_hours):
    return Group("g1", "t", [Address.parse("community.example")], open_hours)


SAT, SUN, MON = 5, 6, 0


def test_day_keys_align_with_weekday():
    assert DAY_KEYS[datetime(2026, 9, 12).weekday()] == "sat"


def test_is_open_inside_window():
    g = _group({SAT: frozenset({20, 21, 22})})
    assert g.is_open(datetime(2026, 9, 12, 20, 0)) is True
    assert g.is_open(datetime(2026, 9, 12, 22, 59)) is True


def test_is_open_outside_window():
    g = _group({SAT: frozenset({20, 21, 22})})
    assert g.is_open(datetime(2026, 9, 12, 19, 59)) is False
    assert g.is_open(datetime(2026, 9, 12, 23, 0)) is False
    assert g.is_open(datetime(2026, 9, 11, 21, 0)) is False  # 금요일


def test_always_closed():
    assert _group({}).always_closed() is True
    assert _group({SAT: frozenset()}).always_closed() is True
    assert _group({SAT: frozenset({1})}).always_closed() is False


def test_next_open_same_day():
    g = _group({SAT: frozenset({20, 21, 22})})
    assert g.next_open(datetime(2026, 9, 12, 19, 30)) == datetime(2026, 9, 12, 20, 0)


def test_next_open_crosses_week():
    g = _group({SAT: frozenset({20})})
    # 토 21:00 → 다음 주 토 20:00
    assert g.next_open(datetime(2026, 9, 12, 21, 0)) == datetime(2026, 9, 19, 20, 0)


def test_next_open_none_when_always_closed():
    assert _group({}).next_open(datetime(2026, 9, 12, 10, 0)) is None


def test_next_open_skips_current_hour():
    # 닫힌 시각에서 부르면 현재 시각 칸은 후보가 아니다
    g = _group({SUN: frozenset({0})})
    assert g.next_open(datetime(2026, 9, 12, 23, 30)) == datetime(2026, 9, 13, 0, 0)


# ---- Task 3: 규칙 파일 파싱·판정·미러 목록 ----
import json
from impel.rules import Rules

SAMPLE = {
    "version": 1,
    "groups": [
        {"id": "g-community", "title": "커뮤니티",
         "addresses": ["community.example", "video.example/shorts"],
         "open": {"sat": [20, 21, 22], "sun": [20, 21, 22]}},
        {"id": "g-always", "title": "상시", "addresses": ["forum.example"], "open": {}},
    ],
}


def test_from_json_parses_groups():
    r = Rules.from_json(json.dumps(SAMPLE))
    assert [g.id for g in r.groups] == ["g-community", "g-always"]
    assert r.groups[0].open_hours == {5: frozenset({20, 21, 22}), 6: frozenset({20, 21, 22})}
    assert r.groups[1].always_closed()


@pytest.mark.parametrize("bad", [
    '{"version": 2, "groups": []}',
    '{"version": 1, "groups": [{"title": "no id", "addresses": []}]}',
    '{"version": 1, "groups": [{"id": "x", "addresses": "notalist"}]}',
    '{"version": 1, "groups": [{"id": "x", "addresses": [], "open": {"funday": [1]}}]}',
    '{"version": 1, "groups": [{"id": "x", "addresses": [], "open": {"mon": [24]}}]}',
    '{"version": 1, "groups": [{"id": "x", "addresses": ["not a host"]}]}',
    '[]',
    'not json',
])
def test_from_json_rejects_bad_schema(bad):
    with pytest.raises(ValueError):
        Rules.from_json(bad)


def test_from_json_skips_blank_addresses():
    r = Rules.from_json('{"version": 1, "groups": [{"id": "x", "addresses": ["", "  ", "a.example"]}]}')
    assert [a.host for a in r.groups[0].addresses] == ["a.example"]


def test_intercept_host():
    r = Rules.from_json(json.dumps(SAMPLE))
    assert r.intercept_host("gall.community.example") is True
    assert r.intercept_host("video.example") is True   # 경로 주소도 호스트는 복호화 대상
    assert r.intercept_host("www.apple.example") is False


def test_decide_blocks_when_closed():
    r = Rules.from_json(json.dumps(SAMPLE))
    g = r.decide("community.example", "/", datetime(2026, 9, 11, 21, 0))  # 금요일
    assert g is not None and g.id == "g-community"


def test_decide_passes_when_open():
    r = Rules.from_json(json.dumps(SAMPLE))
    assert r.decide("community.example", "/", datetime(2026, 9, 12, 21, 0)) is None  # 토요일 21시


def test_decide_passes_unmatched_path():
    r = Rules.from_json(json.dumps(SAMPLE))
    assert r.decide("video.example", "/watch", datetime(2026, 9, 11, 21, 0)) is None


def test_decide_any_closed_group_blocks():
    doc = {"version": 1, "groups": [
        {"id": "open-now", "title": "a", "addresses": ["dup.example"],
         "open": {k: list(range(24)) for k in DAY_KEYS}},
        {"id": "closed", "title": "b", "addresses": ["dup.example"], "open": {}},
    ]}
    g = Rules.from_json(json.dumps(doc)).decide("dup.example", "/", datetime(2026, 9, 11, 21, 0))
    assert g is not None and g.id == "closed"


def test_mirror_hosts_only_always_closed_whole_hosts():
    r = Rules.from_json(json.dumps(SAMPLE))
    assert r.mirror_hosts() == ["forum.example", "www.forum.example"]


def test_empty():
    assert Rules.empty().groups == []


# ---- Task 4: 규칙 파일 재로드 ----
import os
import time
from impel.rules import RulesFile

GOOD = '{"version": 1, "groups": [{"id": "a", "title": "a", "addresses": ["a.example"]}]}'
GOOD2 = '{"version": 1, "groups": [{"id": "b", "title": "b", "addresses": ["b.example"]}]}'


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    # mtime 해상도보다 확실히 뒤로
    t = time.time() + 2
    os.utime(str(path), (t, t))


def test_rulesfile_missing_is_empty(tmp_path):
    rf = RulesFile(str(tmp_path / "rules.json"))
    assert rf.current().groups == [] and rf.version == 0


def test_rulesfile_loads_and_reloads_on_mtime(tmp_path):
    p = tmp_path / "rules.json"
    _write(p, GOOD)
    rf = RulesFile(str(p))
    assert rf.current().groups[0].id == "a" and rf.version == 1
    assert rf.current().groups[0].id == "a" and rf.version == 1  # mtime 같으면 안 읽음
    _write(p, GOOD2)
    assert rf.current().groups[0].id == "b" and rf.version == 2


def test_rulesfile_keeps_last_good_on_bad_content(tmp_path):
    p = tmp_path / "rules.json"
    _write(p, GOOD)
    logs = []
    rf = RulesFile(str(p), log=logs.append)
    rf.current()
    _write(p, "{ broken")
    assert rf.current().groups[0].id == "a"
    assert rf.version == 1 and logs and "reload failed" in logs[0]
