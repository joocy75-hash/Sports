import asyncio
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.agents.data_collector import DataCollectorAgent
from src.config.settings import get_settings
from src.core.logging import setup_logging
from src.services.prediction_runner import run_predictions
from src.agents.kspo_collector import KSPODataCollector
from src.services.high_confidence_notifier import HighConfidenceProtoNotifier


async def fetch_today_fixtures():
    settings = get_settings()
    agent = DataCollectorAgent(settings)
    today = datetime.utcnow().date()
    await agent.fetch_and_store(today)
    await agent.api_client.close()


async def fetch_odds_only():
    settings = get_settings()
    agent = DataCollectorAgent(settings)
    today = datetime.utcnow().date()
    await agent.fetch_odds(today)
    await agent.api_client.close()


async def fetch_upcoming_lineups():
    settings = get_settings()
    agent = DataCollectorAgent(settings)
    await agent.fetch_lineups()
    await agent.api_client.close()


async def predictions_job():
    await run_predictions()


async def kspo_collection_job():
    """KSPO 전 종목 데이터 수집 작업"""
    collector = KSPODataCollector()
    await collector.collect_all_data()


async def high_confidence_notification_job():
    """프로토 승부식 고신뢰도 경기 알림"""
    notifier = HighConfidenceProtoNotifier(confidence_threshold=0.65)
    await notifier.send_notification(days_ahead=7, compact=False)


async def main():
    setup_logging()
    scheduler = AsyncIOScheduler()

    # Every 6 hours: refresh today's fixtures/odds
    scheduler.add_job(
        fetch_today_fixtures,
        "interval",
        hours=6,
        next_run_time=datetime.utcnow() + timedelta(seconds=2),
    )

    # Every 10 minutes: odds refresh
    scheduler.add_job(
        fetch_odds_only,
        "interval",
        minutes=10,
        next_run_time=datetime.utcnow() + timedelta(seconds=5),
    )

    # Every 10 minutes: lineup refresh
    scheduler.add_job(
        fetch_upcoming_lineups,
        "interval",
        minutes=10,
        next_run_time=datetime.utcnow() + timedelta(seconds=8),
    )

    # Every 5 minutes: live score refresh
    async def live_score_job():
        settings = get_settings()
        agent = DataCollectorAgent(settings)
        await agent.fetch_live_data()
        await agent.api_client.close()

    scheduler.add_job(
        live_score_job,
        "interval",
        minutes=5,
        next_run_time=datetime.utcnow() + timedelta(seconds=15),
    )

    # Every 10 minutes: run predictions to ensure fresh analysis
    scheduler.add_job(
        predictions_job,
        "interval",
        minutes=10,
        next_run_time=datetime.utcnow() + timedelta(seconds=10),
    )

    # Every 1 hour: KSPO Data Collection (Data First)
    scheduler.add_job(
        kspo_collection_job,
        "interval",
        hours=1,
        next_run_time=datetime.utcnow() + timedelta(seconds=20),
    )

    # Every 4 hours: High Confidence Proto Notification
    # 고신뢰도 경기 알림 (하루 6번: 6시, 10시, 14시, 18시, 22시, 2시)
    scheduler.add_job(
        high_confidence_notification_job,
        "interval",
        hours=4,
        next_run_time=datetime.utcnow() + timedelta(minutes=5),
    )

    # Bot setup
    from src.services.telegram_bot import create_bot_app, check_and_send_alerts

    bot_app = create_bot_app()
    if bot_app:
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        print("Telegram bot started")

        async def alerts_job():
            await check_and_send_alerts(bot_app.bot)

        scheduler.add_job(alerts_job, "interval", minutes=10)

    scheduler.start()

    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        if bot_app:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
