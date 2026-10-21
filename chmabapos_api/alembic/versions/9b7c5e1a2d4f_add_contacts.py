"""Platform contacts and their categories.

Contacts are a small CRM for people the team tracks before they become users:
leads, potential leads, partners. Email is the natural key so an import can
update a known person. Deleting a category keeps its contacts by setting the
foreign key to NULL.

Revision ID: 9b7c5e1a2d4f
Revises: 14607ba3b68e
Create Date: 2026-10-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9b7c5e1a2d4f"
down_revision: Union[str, None] = "14607ba3b68e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_CATEGORIES = (
    ("2f6a1c4e-8d3b-4a91-9f27-1c5e8b0a7d11", "Lead", "violet", "New names to reach out to"),
    ("7b3d9e2a-1f6c-4c58-8a04-5e9d2b7c1a22", "Potential lead", "blue", "Showed interest but not qualified yet"),
    ("4c8e2a6f-9b1d-4f73-a0c5-3d7e1b9f2c33", "Qualified lead", "yellow", "Ready for a real conversation"),
    ("8d1f5b3c-6e2a-4b97-9c10-7a4e2d8f5b44", "Customer", "green", "Already buying from Chmaba"),
    ("1a9c7e4d-2b8f-4d36-8e51-6c3a9f0b7d55", "Partner", "violet", "Agencies and resellers"),
    ("5e2b8d1a-7c4f-4a69-b3d8-9f1c6e2a4b66", "Other", "neutral", "Anything that does not fit yet"),
)


def upgrade() -> None:
    op.create_table(
        "contact_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("color", sa.String(20), nullable=False, server_default="violet"),
        sa.Column("description", sa.String(240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_categories_name", "contact_categories", ["name"], unique=True)

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(160), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("company", sa.String(160), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["category_id"], ["contact_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_email", "contacts", ["email"], unique=True)
    op.create_index("ix_contacts_category_id", "contacts", ["category_id"])
    op.create_index("ix_contacts_created", "contacts", ["created_at"])
    op.create_index("ix_contacts_category_created", "contacts", ["category_id", "created_at"])

    categories = sa.table(
        "contact_categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("color", sa.String),
        sa.column("description", sa.String),
    )
    op.bulk_insert(
        categories,
        [
            {"id": category_id, "name": name, "color": color, "description": description}
            for category_id, name, color, description in DEFAULT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_contacts_category_created", table_name="contacts")
    op.drop_index("ix_contacts_created", table_name="contacts")
    op.drop_index("ix_contacts_category_id", table_name="contacts")
    op.drop_index("ix_contacts_email", table_name="contacts")
    op.drop_table("contacts")
    op.drop_index("ix_contact_categories_name", table_name="contact_categories")
    op.drop_table("contact_categories")
