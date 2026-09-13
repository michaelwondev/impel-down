from datetime import datetime
from impel.notice import render


def test_render_with_next_open():
    html = render("커뮤니티", datetime(2026, 9, 12, 20, 0), "gall.community.example")
    assert html.startswith("<!doctype html>")
    assert "정신 차리고 중요한 일에 집중하세요." in html and "커뮤니티" in html
    assert "다음 열림 토 20:00" in html
    assert "gall.community.example" in html


def test_render_without_next_open():
    assert "다음 열림" not in render("상시", None, "video.example")


def test_render_escapes_html():
    html = render("<b>x</b>", None, "evil.example/<script>")
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<script>" not in html
