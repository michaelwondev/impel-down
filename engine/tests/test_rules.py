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
