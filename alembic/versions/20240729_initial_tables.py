"""create initial tables

Revision ID: 20240729_initial_tables
Revises:
Create Date: 2024-07-29 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20240729_initial_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create leagues table
    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=50), nullable=True),
        sa.Column("sport", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create teams table
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("sport", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create matches table
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("sport", sa.String(length=20), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("home_team_id", sa.Integer(), nullable=True),
        sa.Column("away_team_id", sa.Integer(), nullable=True),
        sa.Column("odds_home", sa.Float(), nullable=True),
        sa.Column("odds_draw", sa.Float(), nullable=True),
        sa.Column("odds_away", sa.Float(), nullable=True),
        sa.Column("score_home", sa.Integer(), nullable=True),
        sa.Column("score_away", sa.Integer(), nullable=True),
        sa.Column("xg_home", sa.Float(), nullable=True),
        sa.Column("xg_away", sa.Float(), nullable=True),
        sa.Column(
            "lineup_home", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "lineup_away", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("raw_odds", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["away_team_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["home_team_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create odds_history table
    op.create_table(
        "odds_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("odds_home", sa.Float(), nullable=True),
        sa.Column("odds_draw", sa.Float(), nullable=True),
        sa.Column("odds_away", sa.Float(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create prediction_logs table
    op.create_table(
        "prediction_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("prob_home", sa.Float(), nullable=True),
        sa.Column("prob_draw", sa.Float(), nullable=True),
        sa.Column("prob_away", sa.Float(), nullable=True),
        sa.Column("value_home", sa.Float(), nullable=True),
        sa.Column("value_draw", sa.Float(), nullable=True),
        sa.Column("value_away", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create team_stats table
    op.create_table(
        "team_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("matches_played", sa.Integer(), nullable=True),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("draws", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("goals_for", sa.Integer(), nullable=True),
        sa.Column("goals_against", sa.Integer(), nullable=True),
        sa.Column("xg_for", sa.Float(), nullable=True),
        sa.Column("xg_against", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("team_stats")
    op.drop_table("prediction_logs")
    op.drop_table("odds_history")
    op.drop_table("matches")
    op.drop_table("teams")
    op.drop_table("leagues")
