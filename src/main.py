import argparse
import asyncio
from datetime import date

from src.config.settings import get_settings
from src.core.logging import setup_logging
from src.db.session import init_db

from src.services.prediction_runner import PredictionRunner


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sports betting analysis orchestrator")
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Create tables in the configured Postgres database",
    )
    parser.add_argument(
        "--fetch-fixtures", type=str, help="ISO date (YYYY-MM-DD) to fetch fixtures for"
    )
    parser.add_argument(
        "--run-predictions",
        action="store_true",
        help="Run prediction/value calc for upcoming matches",
    )
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()

    if args.init_db:
        await init_db()
        print("DB initialized")

    if args.fetch_fixtures:
        from src.agents.data_collector import DataCollectorAgent

        target = date.fromisoformat(args.fetch_fixtures)
        agent = DataCollectorAgent(settings)
        await agent.fetch_and_store(target)
        await agent.api_client.close()
        print(f"Fixtures fetched for {target.isoformat()}")

    if args.run_predictions:

        runner = PredictionRunner()
        processed = await runner.run_all_predictions()
        print(f"Predictions stored for matches: {processed}")

    if args.run_scheduler:
        from src.scheduler import main as scheduler_main

        await scheduler_main()


if __name__ == "__main__":
    asyncio.run(main())
