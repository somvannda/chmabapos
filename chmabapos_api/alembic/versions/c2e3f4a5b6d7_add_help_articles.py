"""add_help_articles

Creates ``help_articles`` and seeds it from the static corpus in
``app/support_content.py`` so admins can edit help content without a deploy.
That module stays the fallback baseline if this table is ever empty.

Revision ID: c2e3f4a5b6d7
Revises: b1d2e3f4a5c6
Create Date: 2026-10-01 00:00:00.000000
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c2e3f4a5b6d7'
down_revision: Union[str, None] = 'b1d2e3f4a5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'help_articles',
        sa.Column('id', sa.String(length=80), nullable=False),
        sa.Column('section_id', sa.String(length=80), nullable=False),
        sa.Column('section_title', sa.String(length=160), nullable=False),
        sa.Column('section_title_km', sa.String(length=160), nullable=True),
        sa.Column('section_blurb', sa.String(length=300), nullable=False),
        sa.Column('section_blurb_km', sa.String(length=300), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('title_km', sa.String(length=200), nullable=True),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('steps_km', sa.JSON(), nullable=True),
        sa.Column('tip', sa.Text(), nullable=True),
        sa.Column('tip_km', sa.Text(), nullable=True),
        sa.Column('verticals', sa.JSON(), nullable=False),
        sa.Column('roles', sa.JSON(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_help_article_section_position', 'help_articles', ['section_id', 'position'])

    # Seed from the static corpus (the fallback) so the DB starts as a faithful
    # copy and existing tests keep passing against the same content.
    from app import support_content

    table = sa.table(
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
    now = datetime.now(timezone.utc)
    rows = []
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
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    op.drop_index('ix_help_article_section_position', table_name='help_articles')
    op.drop_table('help_articles')
