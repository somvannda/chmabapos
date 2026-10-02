"""localize_point_of_sale_help

Fills the only English-only gap in the Khmer help corpus: the ``point-of-sale``
section and its ``pos.customer-display`` article. The help seed migrations
(``c6d7e8f9a0b1`` / ``a4b5c6d7e8f9`` / ``b5c6d7e8f9a0``) copied
``app.support_content.KH_TRANSLATIONS`` into the ``help_articles`` ``*_km``
columns with ``ON CONFLICT DO NOTHING``; those two ids had no Khmer then, so this
revision UPDATEs the existing rows — it must not insert, or admin edits made in
the meantime would be lost.

The Khmer text is drafted to match the surrounding corpus and is pending a
native-speaker review.

Revision ID: d4a7b1e9c2f6
Revises: f3c9d1e7a2b4
Create Date: 2026-10-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a7b1e9c2f6"
down_revision: Union[str, None] = "f3c9d1e7a2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SECTION_ID = "point-of-sale"
_ARTICLE_ID = "pos.customer-display"

_SECTION_TITLE_KM = "ចំណុចលក់"
_SECTION_BLURB_KM = "ដំណើរការម៉ាស៊ីនគិតលុយ និងអេក្រង់អតិថិជន។"
_ARTICLE_TITLE_KM = "រៀបចំអេក្រង់អតិថិជន"
_ARTICLE_STEPS_KM = [
    "នៅ ការកំណត់ បើក អេក្រង់អតិថិជន ហើយបើកជម្រើស បើកអេក្រង់អតិថិជន។",
    "បន្ថែមរូបសញ្ញាវិក្កយបត្រ និងអាសយដ្ឋានហាង ដើម្បីឲ្យអតិថិជនឃើញកន្លែងដែលពួកគេកំពុងបង់ប្រាក់ (ការកំណត់ បន្ទាប់មក វិក្កយបត្រ និង ការកំណត់ហាង)។",
    "នៅម៉ាស៊ីនគិតលុយ ចុច បើកអេក្រង់អតិថិជន។ បង្អួចទីពីរនឹងបើកបង្ហាញការបញ្ជាទិញ ហើយនៅពេលគិតលុយ កូដ KHQR។",
    "ផ្លាស់បង្អួចនោះទៅអេក្រង់ដែលបែរមុខទៅអតិថិជន។ វាធ្វើបច្ចុប្បន្នភាពស្របនឹងម៉ាស៊ីនគិតលុយសម្រាប់រាល់ការលក់។",
    "ដើម្បីបញ្ឈប់ការចែករំលែក សូមបិទជម្រើស បើកអេក្រង់អតិថិជនវិញ; ប៊ូតុងនឹងបាត់ពីម៉ាស៊ីនគិតលុយ។",
]
_ARTICLE_TIP_KM = "អេក្រង់បង្ហាញទិន្នន័យ លុះត្រាតែមានម៉ាស៊ីនគិតលុយបើកនៅលើកុំព្យូទ័រតែមួយ។ បើបើកដោយឡែក វាបង្ហាញ កំពុងរង់ចាំម៉ាស៊ីនគិតលុយ។"


_help_articles = sa.table(
    "help_articles",
    sa.column("id", sa.String),
    sa.column("section_id", sa.String),
    sa.column("section_title_km", sa.String),
    sa.column("section_blurb_km", sa.String),
    sa.column("title_km", sa.String),
    sa.column("steps_km", sa.JSON),
    sa.column("tip_km", sa.Text),
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.update(_help_articles)
        .where(_help_articles.c.section_id == _SECTION_ID)
        .values(section_title_km=_SECTION_TITLE_KM, section_blurb_km=_SECTION_BLURB_KM)
    )
    bind.execute(
        sa.update(_help_articles)
        .where(_help_articles.c.id == _ARTICLE_ID)
        .values(title_km=_ARTICLE_TITLE_KM, steps_km=_ARTICLE_STEPS_KM, tip_km=_ARTICLE_TIP_KM)
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.update(_help_articles)
        .where(_help_articles.c.id == _ARTICLE_ID)
        .values(title_km=None, steps_km=None, tip_km=None)
    )
    # Only clear the section fields that still hold what this revision set, so a
    # later platform-admin edit is not clobbered.
    bind.execute(
        sa.update(_help_articles)
        .where(
            sa.and_(
                _help_articles.c.section_id == _SECTION_ID,
                _help_articles.c.section_title_km == _SECTION_TITLE_KM,
            )
        )
        .values(section_title_km=None, section_blurb_km=None)
    )
