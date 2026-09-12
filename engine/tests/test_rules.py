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
