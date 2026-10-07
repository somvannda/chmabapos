"""seed_qz_tray_help

Adds the "Print to a set printer with QZ Tray" guide to databases that were
seeded before it existed. The static corpus (``app.support_content``) stays the
source of truth, so the articles are read from it at run time. Existing rows are
never overwritten (``ON CONFLICT DO NOTHING``) so edits made in the platform-admin
help editor are preserved; only ``position`` is refreshed so sections and
articles keep the order the static corpus defines.

Revision ID: b7d1e2f3a4c5
Revises: a1a1a1a1a1a1
Create Date: 2026-10-07 00:00:00.000000
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert as pg_insert


revision: str = 'b7d1e2f3a4c5'
down_revision: Union[str, None] = 'a1a1a1a1a1a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Articles added after the previous seed. Downgrade removes only these so the
# rest of the corpus is preserved.
_ADDED_ARTICLE_IDS: tuple[str, ...] = ("pos.qz-tray",)


def _help_articles_table() -> sa.TableClause:
    return sa.table(
        'help_articles',
        sa.column('id', sa.String),
        sa.column('section_id', sa.String),
        sa.column('section_title', sa.String),
        sa.column('section_title_km', sa.String),
        sa.column('section_blurb', sa.String),
        sa.column('section_blurb_km', sa.String),
        sa.column('title', sa.String),
        sa.column('title_km', sa.String),
        sa.column('steps', sa.JSON),
        sa.column('steps_km', sa.JSON),
        sa.column('tip', sa.Text),
        sa.column('tip_km', sa.Text),
        sa.column('verticals', sa.JSON),
        sa.column('roles', sa.JSON),
        sa.column('position', sa.Integer),
        sa.column('is_active', sa.Boolean),
        sa.column('updated_at', sa.DateTime(timezone=True)),
        sa.column('updated_by', postgresql.UUID(as_uuid=True)),
    )


def upgrade() -> None:
    from app import support_content

    table = _help_articles_table()
    now = datetime.now(timezone.utc)
    rows: list[dict] = []
    position = 0
    for section in support_content.SUPPORT_SECTIONS:
        section_km = support_content.KH_TRANSLATIONS.get(section['id'], {})
        for article in section['articles']:
            article_km = support_content.KH_TRANSLATIONS.get(article['id'], {})
            rows.append(
                {
                    'id': article['id'],
                    'section_id': section['id'],
                    'section_title': section['title'],
                    'section_title_km': section_km.get('title'),
                    'section_blurb': section['blurb'],
                    'section_blurb_km': section_km.get('blurb'),
                    'title': article['title'],
                    'title_km': article_km.get('title'),
                    'steps': article['steps'],
                    'steps_km': article_km.get('steps'),
                    'tip': article.get('tip'),
                    'tip_km': article_km.get('tip'),
                    'verticals': article['verticals'],
                    'roles': article['roles'],
                    'position': position,
                    'is_active': True,
                    'updated_at': now,
                    'updated_by': None,
                }
            )
            position += 1
    if not rows:
        return

    bind = op.get_bind()
    # Add anything missing without touching admin-edited rows.
    bind.execute(pg_insert(table).values(rows).on_conflict_do_nothing(index_elements=['id']))
    # Then restore the authored order for every seeded article.
    bind.execute(
        sa.update(table).where(table.c.id == sa.bindparam('b_id')).values(position=sa.bindparam('b_pos')),
        [{'b_id': row['id'], 'b_pos': row['position']} for row in rows],
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM help_articles WHERE id = ANY(:ids)").bindparams(
            sa.bindparam('ids', list(_ADDED_ARTICLE_IDS), type_=postgresql.ARRAY(sa.String))
        )
    )
