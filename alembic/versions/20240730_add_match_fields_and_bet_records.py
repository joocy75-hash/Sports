"""add match fields and bet_records

Revision ID: add_match_fields_and_bet_records
Revises:
Create Date: 2024-07-30 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_match_fields_and_bet_records"
down_revision: Union[str, None] = "20240729_initial_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "matches",
        sa.Column("lineup_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column(
            "sharp_detected", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column(
        "matches", sa.Column("sharp_direction", sa.String(length=10), nullable=True)
    )
    op.add_column(
        "matches", sa.Column("recommendation", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "matches", sa.Column("recommended_stake_pct", sa.Float(), nullable=True)
    )

    op.create_table(
        "bet_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "match_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False
        ),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bet_type", sa.String(length=20), nullable=True),
        sa.Column("stake_amount", sa.Float(), nullable=False),
        sa.Column("odds_taken", sa.Float(), nullable=False),
        sa.Column("result", sa.String(length=10), nullable=True),
        sa.Column("profit_loss", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("bet_records")
    op.drop_column("matches", "recommended_stake_pct")
    op.drop_column("matches", "recommendation")
    op.drop_column("matches", "sharp_direction")
    op.drop_column("matches", "sharp_detected")
    op.drop_column("matches", "lineup_confirmed_at")
