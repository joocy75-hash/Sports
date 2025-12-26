import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import select
from src.db.models import Match, OddsHistory, PredictionLog
from src.db.session import get_session
from src.services.prediction_runner import PredictionRunner


class BacktestSimulator:
    def __init__(self):
        self.runner = PredictionRunner()
        self.initial_bankroll = 10000.0
        self.current_bankroll = self.initial_bankroll
        self.bet_history: List[Dict[str, Any]] = []

    async def run_simulation(self, start_date: datetime, end_date: datetime):
        """
        Simulate betting strategy over a historical period.
        """
        print(f"Starting simulation from {start_date.date()} to {end_date.date()}...")

        async with get_session() as session:
            # Fetch completed matches in the range
            query = (
                select(Match)
                .where(
                    Match.start_time >= start_date,
                    Match.start_time <= end_date,
                    Match.status == "FT",  # Only finished matches
                )
                .order_by(Match.start_time)
            )

            result = await session.execute(query)
            matches = result.scalars().all()

            print(f"Found {len(matches)} matches for backtesting.")

            for match in matches:
                # 1. Get historical odds (closing odds or pre-match)
                odds_query = (
                    select(OddsHistory)
                    .where(OddsHistory.match_id == match.id)
                    .order_by(OddsHistory.captured_at.desc())
                    .limit(1)
                )

                odds_result = await session.execute(odds_query)
                odds = odds_result.scalar_one_or_none()

                if not odds:
                    continue

                # 2. Re-run prediction logic (Simulate 'past' prediction)
                # Note: In a real rigorous backtest, we should only use data available BEFORE match.start_time
                # Here we assume the PredictionRunner uses stats that were available.

                # We manually trigger the prediction logic for this single match
                # This is a simplified version of what PredictionRunner does

                # ... (Logic to call predictor would go here, but PredictionRunner is designed for 'upcoming')
                # For this simulation, let's check if we have a PredictionLog for this match
                # If not, we might need to generate one on the fly using historical stats.

                log_query = (
                    select(PredictionLog)
                    .where(PredictionLog.match_id == match.id)
                    .order_by(PredictionLog.created_at.asc())
                    .limit(1)
                )

                log_result = await session.execute(log_query)
                prediction_log = log_result.scalar_one_or_none()

                if not prediction_log:
                    # If no log exists, we skip (or we could implement on-the-fly prediction)
                    continue

                # 3. Evaluate Bet
                # Strategy: Bet on Home if Value > 5%

                probs = prediction_log.probabilities
                prob_home = probs.get("home", 0)
                implied_home = 1 / odds.odds_home if odds.odds_home else 0

                edge = prob_home - implied_home

                if edge > 0.05 and odds.odds_home:
                    stake_pct = 0.02  # 2% flat stake
                    stake_amount = self.current_bankroll * stake_pct

                    # Check result
                    # Assuming match.score_home and match.score_away are populated
                    # We need to parse the score string "2-1" etc.

                    if not match.score_fulltime:
                        continue

                    try:
                        h_score, a_score = map(int, match.score_fulltime.split("-"))
                    except:
                        continue

                    won = h_score > a_score
                    pnl = 0.0

                    if won:
                        pnl = stake_amount * (odds.odds_home - 1)
                        self.current_bankroll += pnl
                        result_str = "WIN"
                    else:
                        pnl = -stake_amount
                        self.current_bankroll += pnl
                        result_str = "LOSS"

                    self.bet_history.append(
                        {
                            "date": match.start_time,
                            "match": f"{match.home_team} vs {match.away_team}",
                            "bet": "HOME",
                            "odds": odds.odds_home,
                            "edge": round(edge, 3),
                            "stake": round(stake_amount, 2),
                            "result": result_str,
                            "pnl": round(pnl, 2),
                            "bankroll": round(self.current_bankroll, 2),
                        }
                    )

        # Summary
        wins = len([b for b in self.bet_history if b["result"] == "WIN"])
        losses = len([b for b in self.bet_history if b["result"] == "LOSS"])
        total_bets = len(self.bet_history)
        roi = (
            (self.current_bankroll - self.initial_bankroll) / self.initial_bankroll
        ) * 100

        print("\n=== Backtest Results ===")
        print(f"Total Bets: {total_bets}")
        print(f"Wins: {wins}, Losses: {losses}")
        print(
            f"Win Rate: {wins / total_bets * 100:.1f}%"
            if total_bets > 0
            else "Win Rate: 0%"
        )
        print(f"Final Bankroll: ${self.current_bankroll:.2f}")
        print(f"ROI: {roi:.2f}%")

        return {
            "total_bets": total_bets,
            "roi": roi,
            "final_bankroll": self.current_bankroll,
            "history": self.bet_history,
        }


if __name__ == "__main__":
    # Example usage
    sim = BacktestSimulator()
    # Run for last 30 days
    end = datetime.utcnow()
    start = end - timedelta(days=30)
    asyncio.run(sim.run_simulation(start, end))
