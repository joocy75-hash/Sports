import asyncio
import logging
from src.ml.data_loader import HistoricalDataLoader
from src.ml.model import MatchPredictorML

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # 1. Download Data
    loader = HistoricalDataLoader()
    # Download last 3 seasons for major leagues
    seasons = ["2122", "2223", "2324"]
    leagues = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]

    logger.info("Downloading historical data...")
    df = await loader.download_season_data(
        season="2324", leagues=leagues
    )  # Start with just one season for speed

    if df.empty:
        logger.error("No data downloaded.")
        return

    logger.info(f"Downloaded {len(df)} matches.")

    # 2. Preprocess
    df_clean = loader.preprocess_for_training(df)

    # 3. Train Model
    trainer = MatchPredictorML()
    trainer.train(df_clean)

    logger.info("Training complete.")


if __name__ == "__main__":
    asyncio.run(main())
