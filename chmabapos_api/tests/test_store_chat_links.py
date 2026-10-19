"""Unit tests for link extraction from a chat message body.

Pure and DB-free: ``extract_links`` is the same rule the web client's ``linkify``
uses, so a bare domain (``chmaba.com``) links while a file name, a version number
or an email does not.
"""
from __future__ import annotations

from app.services.store_chat import extract_links


def test_extract_links_recognises_schemes_www_and_bare_domains() -> None:
    assert extract_links("see https://x.example.com/a and www.foo.org and chmaba.com/order/7") == [
        "https://x.example.com/a",
        "https://www.foo.org",
        "https://chmaba.com/order/7",
    ]


def test_extract_links_ignores_file_names_versions_and_emails() -> None:
    assert extract_links("report.pdf 1.2.3 me@chmaba.com and version 4.0.1") == []


def test_extract_links_trims_trailing_punctuation_and_tolerates_empty() -> None:
    assert extract_links("go to chmaba.com.") == ["https://chmaba.com"]
    assert extract_links("") == []
    assert extract_links(None) == []
