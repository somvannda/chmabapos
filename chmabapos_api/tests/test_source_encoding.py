from __future__ import annotations

from pathlib import Path


FRONTEND_SRC_ROOTS = [
    Path(__file__).resolve().parents[2] / "apps" / "web" / "src",
    Path(__file__).resolve().parents[2] / "apps" / "admin" / "src",
]
SOURCE_SUFFIXES = {".js", ".jsx", ".css"}
REPLACEMENT_CHARACTER = "\ufffd"


def _frontend_sources():
    for root in FRONTEND_SRC_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                yield path


def test_frontend_sources_have_no_replacement_characters() -> None:
    """A U+FFFD in source means a string was corrupted by a wrong-encoding round trip."""
    offenders = [str(path) for path in _frontend_sources() if REPLACEMENT_CHARACTER in path.read_text(encoding="utf-8")]
    assert not offenders, f"Replacement characters found in: {offenders}"
