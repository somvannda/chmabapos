"""polish onboarding email templates

Refresh the nine seeded onboarding ``EmailTemplate`` rows to the branded HTML
layout in ``app.services.email_layout``. ``scripts/seed.py`` only inserts a
template once (matched by name), so installs that already have the plain-text
version need this one-time UPDATE to pick up the new design. On a fresh
database this touches nothing, and the seed inserts the branded copy.

Revision ID: a7c3e9f1b2d4
Revises: f4a1b2c3d4e5
Create Date: 2026-10-02 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.config import settings
from app.services.onboarding_emails import BASE_TOKEN, ONBOARDING_EMAILS


revision: str = "a7c3e9f1b2d4"
down_revision: Union[str, None] = "f4a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    base = settings.frontend_url.rstrip("/")
    statement = sa.text(
        "UPDATE email_templates SET subject = :subject, body_html = :body_html, updated_at = now() WHERE name = :name"
    )
    connection = op.get_bind()
    for email in ONBOARDING_EMAILS:
        connection.execute(
            statement,
            {
                "name": str(email["name"]),
                "subject": str(email["subject"]),
                "body_html": str(email["body_html"]).replace(BASE_TOKEN, base),
            },
        )


def downgrade() -> None:
    # Data-only migration: the previous plain-text bodies are not restored.
    pass
