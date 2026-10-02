"""Export the help corpus (English + Khmer) for a native-speaker review.

Usage:
    python scripts/export_help_translations.py [out.csv]

Reads the live ``help_articles`` table (falling back to the static corpus when the
table is empty) and writes one row per section and article, with the English and
Khmer fields side by side plus a ``status`` column that flags missing or partial
Khmer. Use it to hand a translator a single reviewable file; apply the result to
both ``app/support_content.KH_TRANSLATIONS`` (the static fallback) and a data
migration that UPDATES the ``help_articles`` rows (the seeds use
``on_conflict_do_nothing``, so inserts would not overwrite).

Pass no argument to write CSV to stdout, or a path to write a file.
"""

from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from app import support_content  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services import help_repo  # noqa: E402

FIELDS = ["kind", "section_id", "id", "status", "en_title", "km_title", "en_body", "km_body"]


def _article_km(article: dict) -> tuple[str, list[str], str]:
    """Khmer title/steps/tip for an article from either corpus shape.

    DB rows carry ``*_km`` columns; the static corpus keeps them in the
    ``KH_TRANSLATIONS`` overlay.
    """
    if "title_km" in article:
        return article.get("title_km") or "", list(article.get("steps_km") or []), article.get("tip_km") or ""
    overlay = support_content.KH_TRANSLATIONS.get(article["id"], {})
    return overlay.get("title") or "", list(overlay.get("steps") or []), overlay.get("tip") or ""


def _section_km(section: dict) -> tuple[str, str]:
    if "title_km" in section:
        return section.get("title_km") or "", section.get("blurb_km") or ""
    overlay = support_content.KH_TRANSLATIONS.get(section["id"], {})
    return overlay.get("title") or "", overlay.get("blurb") or ""


def _status(english: list[str], khmer: list[str]) -> str:
    """``ok`` / ``partial_km`` / ``missing_km`` based on which English fields exist."""
    needed = [index for index, value in enumerate(english) if value]
    missing = [index for index in needed if index >= len(khmer) or not khmer[index]]
    if not missing:
        return "ok"
    if len(missing) == len(needed):
        return "missing_km"
    return "partial_km"


def _article_row(section_id: str, article: dict) -> dict:
    km_title, km_steps, km_tip = _article_km(article)
    steps = [str(step) for step in (article.get("steps") or [])]
    tip = article.get("tip") or ""
    english = [article.get("title") or "", *steps, tip]
    khmer = [km_title, *km_steps, km_tip]
    body = "\n".join(steps)
    if tip:
        body += f"\nTIP: {tip}"
    km_body = "\n".join(km_steps)
    if km_tip:
        km_body += f"\nTIP: {km_tip}"
    return {
        "kind": "article",
        "section_id": section_id,
        "id": article["id"],
        "status": _status(english, khmer),
        "en_title": article.get("title") or "",
        "km_title": km_title,
        "en_body": body,
        "km_body": km_body,
    }


def _rows(sections: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for section in sections:
        km_title, km_blurb = _section_km(section)
        title, blurb = section.get("title") or "", section.get("blurb") or ""
        rows.append(
            {
                "kind": "section",
                "section_id": section["id"],
                "id": section["id"],
                "status": _status([title, blurb], [km_title, km_blurb]),
                "en_title": title,
                "km_title": km_title,
                "en_body": blurb,
                "km_body": km_blurb,
            }
        )
        rows.extend(_article_row(section["id"], article) for article in section["articles"])
    return rows


async def _load() -> list[dict]:
    async with SessionLocal() as db:
        sections = await help_repo.load_sections(db)
    return sections if sections is not None else support_content.SUPPORT_SECTIONS


def main() -> None:
    destination = sys.argv[1] if len(sys.argv) > 1 else "-"
    rows = _rows(asyncio.run(_load()))
    if destination == "-":
        writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    else:
        with Path(destination).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    gaps = [row for row in rows if row["status"] != "ok"]
    print(f"{len(rows)} rows; {len(gaps)} need Khmer", file=sys.stderr)
    for row in gaps:
        print(f"  {row['status']}: {row['kind']} {row['id']}", file=sys.stderr)


if __name__ == "__main__":
    main()
