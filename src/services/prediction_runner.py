from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select


from src.db.models import Match, PredictionLog, TeamStats, OddsHistory, League
from src.db.session import get_session
from src.services.predictor import AdvancedStatisticalPredictor
from src.ml.model import MatchPredictorML


class PredictionRunner:
    def __init__(self):
        self.ml_model = MatchPredictorML()
        self.ml_model.load_model()
        self.predictor = AdvancedStatisticalPredictor()

    async def run_all_predictions(
        self, horizon_hours: int = 48, min_value: float = 0.05
    ) -> List[int]:
        """Generate predictions for upcoming matches and store in PredictionLog. Returns match IDs processed."""
        processed_count = 0
        processed_ids = []

        async with get_session() as session:
            # Fetch upcoming matches (next 24h)
            now = datetime.utcnow()
            upcoming = await session.execute(
                select(Match).where(
                    Match.start_time >= now,
                    Match.start_time <= now + timedelta(hours=24),
                )
            )
            matches = upcoming.scalars().all()

            for match in matches:
                # We need odds to predict
                # Fetch latest odds from history
                odds_entry = await session.execute(
                    select(OddsHistory)
                    .where(OddsHistory.match_id == match.id)
                    .order_by(OddsHistory.captured_at.desc())
                    .limit(1)
                )
                latest_odds = odds_entry.scalar_one_or_none()

                if not latest_odds:
                    continue

                # 1. Advanced Statistical Prediction
                home_stats_db = await session.scalar(
                    select(TeamStats)
                    .where(TeamStats.team_id == match.home_team_id)
                    .order_by(TeamStats.updated_at.desc())
                )
                away_stats_db = await session.scalar(
                    select(TeamStats)
                    .where(TeamStats.team_id == match.away_team_id)
                    .order_by(TeamStats.updated_at.desc())
                )

                # Prepare stats dictionaries
                # Using xG as proxy for Avg Goals Scored, xGA for Avg Goals Conceded if raw goals not tracked in stats
                h_stats = {
                    "goals_scored_avg": home_stats_db.xg
                    if home_stats_db and home_stats_db.xg
                    else 1.5,
                    "goals_conceded_avg": home_stats_db.xga
                    if home_stats_db and home_stats_db.xga
                    else 1.2,
                    "momentum": home_stats_db.momentum
                    if home_stats_db and home_stats_db.momentum
                    else 1.0,
                }

                a_stats = {
                    "goals_scored_avg": away_stats_db.xg
                    if away_stats_db and away_stats_db.xg
                    else 1.2,
                    "goals_conceded_avg": away_stats_db.xga
                    if away_stats_db and away_stats_db.xga
                    else 1.5,
                    "momentum": away_stats_db.momentum
                    if away_stats_db and away_stats_db.momentum
                    else 1.0,
                }

                prediction = self.predictor.predict_score_probabilities(
                    h_stats, a_stats
                )

                prob_h = prediction["probabilities"]["home"]
                prob_d = prediction["probabilities"]["draw"]
                prob_a = prediction["probabilities"]["away"]

                xg_home = prediction["expected_score"]["home"]
                xg_away = prediction["expected_score"]["away"]

                # 2. ML Prediction (if applicable)
                ml_prob = None
                if self.ml_model.model:
                    league = await session.get(League, match.league_id)
                    league_name = league.name if league else "Unknown"

                    # Prepare stats for ML model (Performance based, NO ODDS)
                    # We map available stats to the model's expected features
                    # Model expects: avg_gf, avg_ga, avg_sf, avg_sa

                    # Map Home Stats
                    ml_home_stats = {
                        "avg_gf": h_stats["goals_scored_avg"],
                        "avg_ga": h_stats["goals_conceded_avg"],
                        # We use defaults or derived values for shots if not explicitly tracked yet
                        # Assuming ~10 shots per goal as a rough proxy if missing, or just 10.0 average
                        "avg_sf": h_stats["goals_scored_avg"] * 10,
                        "avg_sa": h_stats["goals_conceded_avg"] * 10,
                    }

                    # Map Away Stats
                    ml_away_stats = {
                        "avg_gf": a_stats["goals_scored_avg"],
                        "avg_ga": a_stats["goals_conceded_avg"],
                        "avg_sf": a_stats["goals_scored_avg"] * 10,
                        "avg_sa": a_stats["goals_conceded_avg"] * 10,
                    }

                    ml_prob = self.ml_model.predict_proba(
                        ml_home_stats,
                        ml_away_stats,
                        league_name,
                    )

                # Combine
                final_prob_h, final_prob_d, final_prob_a = prob_h, prob_d, prob_a
                model_ver = "v2_advanced_poisson"

                if ml_prob:
                    # Simple ensemble: 50/50
                    final_prob_h = (prob_h + ml_prob["home"]) / 2
                    final_prob_d = (prob_d + ml_prob["draw"]) / 2
                    final_prob_a = (prob_a + ml_prob["away"]) / 2
                    model_ver = "v3_ensemble_ml_advanced"

                # Value Calculation
                # implied prob = 1 / odds
                if not latest_odds.odds_home:
                    continue

                implied_h = 1 / latest_odds.odds_home

                # Edge = (Model Prob - Implied Prob) / Implied Prob
                edge = final_prob_h - implied_h

                recommendation = "NO_BET"
                stake = 0.0

                # Base stake logic
                if edge > 0.05:  # 5% edge
                    recommendation = "VALUE"
                    stake = 0.01  # 1% flat
                    if edge > 0.10:
                        recommendation = "STRONG_VALUE"
                        stake = 0.02

                # Lineup Confirmation Bonus
                # 선발 라인업이 확정된 경우 신뢰도 및 베팅 금액 상향
                is_lineup_confirmed = match.lineup_confirmed_at is not None
                if is_lineup_confirmed and recommendation != "NO_BET":
                    stake *= 1.5  # Increase stake by 50%
                    recommendation += "_LINEUP"  # e.g., VALUE_LINEUP
                    if stake > 0.05:  # Cap at 5%
                        stake = 0.05

                # Update Match
                match.recommendation = recommendation
                match.recommended_stake_pct = stake

                # Log Prediction
                log = PredictionLog(
                    match_id=match.id,
                    model_name="Ensemble_v1",
                    probabilities={
                        "home": final_prob_h,
                        "draw": final_prob_d,
                        "away": final_prob_a,
                    },
                    expected_score={"home": xg_home, "away": xg_away},
                    value_score=edge,
                    meta={
                        "model_version": model_ver,
                        "poisson": {"h": prob_h, "d": prob_d, "a": prob_a},
                        "ml": ml_prob,
                        "lineup_confirmed": is_lineup_confirmed,
                    },
                )
                session.add(log)
                processed_count += 1
                processed_ids.append(match.id)

            await session.commit()

        return processed_ids
