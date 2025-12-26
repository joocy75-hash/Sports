from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(64))
    sport: Mapped[str] = mapped_column(
        String(32), default="football"
    )  # football, nba, mlb

    matches: Mapped[list["Match"]] = relationship(back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    league_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leagues.id"))
    sport: Mapped[str] = mapped_column(String(32), default="football")
    logo_url: Mapped[Optional[str]] = mapped_column(String(256))

    league: Mapped[Optional[League]] = relationship(back_populates="teams")
    home_matches: Mapped[list["Match"]] = relationship(
        foreign_keys="Match.home_team_id", back_populates="home_team"
    )
    away_matches: Mapped[list["Match"]] = relationship(
        foreign_keys="Match.away_team_id", back_populates="away_team"
    )
    stats: Mapped[list["TeamStats"]] = relationship(back_populates="team")


League.teams = relationship("Team", back_populates="league")  # type: ignore[attr-defined]


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )  # fixture id from provider
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    sport: Mapped[str] = mapped_column(String(32), default="football")
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="scheduled")

    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)

    odds_home: Mapped[Optional[float]] = mapped_column(Float)
    odds_draw: Mapped[Optional[float]] = mapped_column(Float)
    odds_away: Mapped[Optional[float]] = mapped_column(Float)

    score_home: Mapped[Optional[int]] = mapped_column(Integer)
    score_away: Mapped[Optional[int]] = mapped_column(Integer)

    xg_home: Mapped[Optional[float]] = mapped_column(Float)
    xg_away: Mapped[Optional[float]] = mapped_column(Float)

    lineup_home: Mapped[Optional[dict]] = mapped_column(JSON)
    lineup_away: Mapped[Optional[dict]] = mapped_column(JSON)
    lineup_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    raw_odds: Mapped[Optional[dict]] = mapped_column(JSON)  # last fetched odds snapshot
    sharp_detected: Mapped[bool] = mapped_column(default=False)
    sharp_direction: Mapped[Optional[str]] = mapped_column(String(10))

    recommendation: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # STRONG_VALUE / VALUE / SKIP
    recommended_stake_pct: Mapped[Optional[float]] = mapped_column(
        Float
    )  # fraction of bankroll

    # KSPO 회차 정보
    product_name: Mapped[Optional[str]] = mapped_column(String(100))  # 예: "프로토"
    category_name: Mapped[Optional[str]] = mapped_column(
        String(100)
    )  # 예: "프로토 승부식", "농구 승5패"
    round_number: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # 회차 번호 (날짜 기반: 20251217)
    sport_type: Mapped[Optional[str]] = mapped_column(
        String(50)
    )  # 종목 (축구, 농구, 배구, 야구 등)
    game_number: Mapped[Optional[int]] = mapped_column(
        Integer
    )  # 베트맨 공식 경기 번호 (1~14)

    league: Mapped[League] = relationship(back_populates="matches")
    home_team: Mapped[Team] = relationship(
        foreign_keys=[home_team_id], back_populates="home_matches"
    )
    away_team: Mapped[Team] = relationship(
        foreign_keys=[away_team_id], back_populates="away_matches"
    )
    predictions: Mapped[list["PredictionLog"]] = relationship(back_populates="match")


class OddsHistory(Base):
    __tablename__ = "odds_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    bookmaker: Mapped[str] = mapped_column(String(64), default="pinnacle")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    odds_home: Mapped[Optional[float]] = mapped_column(Float)
    odds_draw: Mapped[Optional[float]] = mapped_column(Float)
    odds_away: Mapped[Optional[float]] = mapped_column(Float)
    market: Mapped[str] = mapped_column(String(32), default="1x2")
    payload: Mapped[Optional[dict]] = mapped_column(JSON)


class BetRecord(Base):
    __tablename__ = "bet_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    bet_type: Mapped[str] = mapped_column(String(20))  # e.g., home/draw/away/over/under
    stake_amount: Mapped[float] = mapped_column(Float)
    odds_taken: Mapped[float] = mapped_column(Float)
    result: Mapped[Optional[str]] = mapped_column(String(10))
    profit_loss: Mapped[Optional[float]] = mapped_column(Float)


class TeamStats(Base):
    __tablename__ = "team_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)

    xg: Mapped[Optional[float]] = mapped_column(Float)
    xga: Mapped[Optional[float]] = mapped_column(Float)
    momentum: Mapped[Optional[float]] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    team: Mapped[Team] = relationship(back_populates="stats")


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    prob_home: Mapped[float] = mapped_column(Float)
    prob_draw: Mapped[float] = mapped_column(Float)
    prob_away: Mapped[float] = mapped_column(Float)

    expected_score_home: Mapped[Optional[float]] = mapped_column(Float)
    expected_score_away: Mapped[Optional[float]] = mapped_column(Float)

    value_home: Mapped[Optional[float]] = mapped_column(Float)
    value_draw: Mapped[Optional[float]] = mapped_column(Float)
    value_away: Mapped[Optional[float]] = mapped_column(Float)

    meta: Mapped[Optional[dict]] = mapped_column(JSON)

    match: Mapped[Match] = relationship(back_populates="predictions")
