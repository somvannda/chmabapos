"""Store payment links per currency, starting with KHR.

ABA PayWay settles one currency per link, and ChmabaPay models it as a store
holding one link per currency (at most one USD and one KHR). Chmaba kept a single
link, so a merchant pricing in riel had nowhere to put the KHR one.

``aba_payway_links`` holds the map. The existing ``aba_payway_link`` /
``aba_payway_status`` columns stay as the USD view for now, kept in step by the
sync path, so every current reader keeps working while they migrate; a later
revision drops them once nothing reads them.

Additive and nullable: an existing merchant's USD link keeps working, and the map
is absent until a second currency (or a re-save) writes one.

Revision ID: f9a1c3e5b7d2
Revises: d8e1f4a7c2b9
Create Date: 2026-10-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f9a1c3e5b7d2"
down_revision: Union[str, None] = "d8e1f4a7c2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("aba_payway_links", sa.JSON(), nullable=True))
    op.add_column("stores", sa.Column("aba_payway_links", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "aba_payway_links")
    op.drop_column("companies", "aba_payway_links")
