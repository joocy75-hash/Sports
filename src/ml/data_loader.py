import pandas as pd
import logging
import io
import aiohttp
from typing import List

logger = logging.getLogger(__name__)

# Football-Data.co.uk uses specific codes: E0 (Premier League), SP1 (La Liga), I1 (Serie A), D1 (Bundesliga)
LEAGUE_CODES = {
    "Premier League": "E0",
    "La Liga": "SP1",
    "Serie A": "I1",
    "Bundesliga": "D1",
    "Ligue 1": "F1",
}

BASE_URL = "https://www.football-data.co.uk/mmz4281"


class HistoricalDataLoader:
    def __init__(self):
        self.base_url = BASE_URL

    async def download_season_data(
        self, season: str, leagues: List[str]
    ) -> pd.DataFrame:
        """
        Download historical data from football-data.co.uk
        season format: '2324' for 2023/2024
        """
        all_data = []

        async with aiohttp.ClientSession() as session:
            for league_name in leagues:
                code = LEAGUE_CODES.get(league_name)
                if not code:
                    logger.warning(f"Unknown league: {league_name}")
                    continue

                url = f"{self.base_url}/{season}/{code}.csv"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            # Decode and parse CSV
                            df = pd.read_csv(
                                io.BytesIO(content), encoding="latin1"
                            )  # usually latin1
                            df["LeagueName"] = league_name
                            df["Season"] = season
                            all_data.append(df)
                            logger.info(f"Downloaded {league_name} {season}")
                        else:
                            logger.error(f"Failed to download {url}: {resp.status}")
                except Exception as e:
                    logger.error(f"Error downloading {url}: {e}")

        if not all_data:
            return pd.DataFrame()

        return pd.concat(all_data, ignore_index=True)

    def calculate_rolling_stats(
        self, df: pd.DataFrame, window: int = 5
    ) -> pd.DataFrame:
        """
        Calculate rolling averages for team stats.
        """
        df = df.sort_values("Date")

        # We need to restructure to get a single timeline per team
        # Create a long-form dataframe: Date, Team, GoalsFor, GoalsAgainst, ShotsFor, ShotsAgainst
        home_df = df[
            ["Date", "HomeTeam", "FTHG", "FTAG", "HS", "AS", "HST", "AST"]
        ].copy()
        home_df.columns = ["Date", "Team", "GF", "GA", "SF", "SA", "STF", "STA"]
        home_df["IsHome"] = 1

        away_df = df[
            ["Date", "AwayTeam", "FTAG", "FTHG", "AS", "HS", "AST", "HST"]
        ].copy()
        away_df.columns = ["Date", "Team", "GF", "GA", "SF", "SA", "STF", "STA"]
        away_df["IsHome"] = 0

        team_df = pd.concat([home_df, away_df]).sort_values(["Team", "Date"])

        # Calculate rolling means (shifted by 1 to avoid data leakage)
        cols_to_roll = ["GF", "GA", "SF", "SA", "STF", "STA"]

        # grouped = team_df.groupby("Team")[cols_to_roll]

        # Merge back to original df
        # We need to merge twice: once for HomeTeam, once for AwayTeam

        # Prepare Home Stats
        # rolling_stats has 'level_1' which corresponds to the original index if we preserved it?
        # No, rolling().mean() resets index structure somewhat.
        # Let's use a simpler approach: Apply transform

        for col in cols_to_roll:
            team_df[f"Avg_{col}"] = team_df.groupby("Team")[col].transform(
                lambda x: x.rolling(window=window, min_periods=3).mean().shift(1)
            )

        # Now map back to the main df
        # We can join on (Date, HomeTeam) and (Date, AwayTeam)

        # Home Stats
        h_stats = team_df[team_df["IsHome"] == 1][
            ["Date", "Team"] + [f"Avg_{c}" for c in cols_to_roll]
        ]
        h_stats.columns = ["Date", "HomeTeam"] + [f"HomeAvg{c}" for c in cols_to_roll]

        # Away Stats
        a_stats = team_df[team_df["IsHome"] == 0][
            ["Date", "Team"] + [f"Avg_{c}" for c in cols_to_roll]
        ]
        a_stats.columns = ["Date", "AwayTeam"] + [f"AwayAvg{c}" for c in cols_to_roll]

        df = pd.merge(df, h_stats, on=["Date", "HomeTeam"], how="left")
        df = pd.merge(df, a_stats, on=["Date", "AwayTeam"], how="left")

        return df

    def preprocess_for_training(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and prepare features for ML model.
        Target: 'FTR' (Full Time Result: H, D, A)
        Features: Rolling Stats (Goals, Shots) - NO ODDS
        """
        # Convert Date first
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

        # Calculate Rolling Stats
        df = self.calculate_rolling_stats(df)

        # Select relevant columns
        # We keep B365 odds ONLY for reference/value calculation in backtesting,
        # but the Model should NOT use them.
        cols = [
            "Date",
            "HomeTeam",
            "AwayTeam",
            "FTHG",
            "FTAG",
            "FTR",
            "B365H",
            "B365D",
            "B365A",  # Keep for reference
            "LeagueName",
            "Season",
            # New Features
            "HomeAvgGF",
            "HomeAvgGA",
            "HomeAvgSF",
            "HomeAvgSA",
            "AwayAvgGF",
            "AwayAvgGA",
            "AwayAvgSF",
            "AwayAvgSA",
        ]

        # Filter existing columns
        existing_cols = [c for c in cols if c in df.columns]
        df = df[existing_cols].copy()

        # Drop rows with missing stats (first few games of season)
        df.dropna(subset=["HomeAvgGF", "AwayAvgGF", "FTR"], inplace=True)

        return df
