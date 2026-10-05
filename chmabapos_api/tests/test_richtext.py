from __future__ import annotations

from app.services.richtext import looks_like_html, sanitize_html


def test_plain_text_is_escaped_and_keeps_breaks() -> None:
    out = sanitize_html("Hello <world> & friends\nsecond line")
    assert out == "Hello &lt;world&gt; &amp; friends<br>second line"


def test_allowed_formatting_is_kept() -> None:
    out = sanitize_html("<p>Hi <strong>there</strong></p><ul><li>one</li></ul>")
    assert "<strong>there</strong>" in out
    assert "<ul>" in out and "<li>one</li>" in out


def test_scripts_and_event_handlers_are_removed() -> None:
    evil = '<p onclick="steal()">ok</p><script>alert(1)</script><img src=x onerror=alert(2)>'
    out = sanitize_html(evil)
    assert "onclick" not in out
    assert "<script" not in out.lower()
    assert "onerror" not in out
    assert "alert(1)" not in out
    assert "ok" in out


def test_link_scheme_is_restricted() -> None:
    out = sanitize_html('<a href="javascript:alert(1)">x</a> <a href="https://ok.test">y</a>')
    assert "javascript:" not in out
    assert 'href="https://ok.test"' in out
    assert 'rel="noopener noreferrer"' in out


def test_unknown_tags_are_dropped_but_text_kept() -> None:
    out = sanitize_html("<marquee><b>hi</b></marquee>")
    assert "marquee" not in out
    assert "<b>hi</b>" in out


def test_mismatched_tags_are_balanced() -> None:
    out = sanitize_html("<p>one<strong>two")
    assert out.count("<strong>") == out.count("</strong>") == 1
    assert out.count("<p>") == out.count("</p>") == 1


def test_plain_text_is_not_treated_as_html() -> None:
    assert looks_like_html("2 < 3 and 4 > 1") is False
    assert looks_like_html("the <world> is round") is False
    assert looks_like_html("<b>x</b>") is True


def test_empty_input() -> None:
    assert sanitize_html(None) == ""
    assert sanitize_html("   ") == ""
