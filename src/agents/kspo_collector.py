import asyncio
from datetime import datetime, timedelta
from src.agents.base import BaseAgent
from src.services.kspo_api_client import KSPOApiClient
from src.config.settings import get_settings


class KSPODataCollector(BaseAgent):
    """
    KSPO API 전용 데이터 수집 에이전트
    - Data First 원칙에 따라 베트맨 발매 경기를 최우선으로 수집
    - 전 종목(축구, 농구, 야구, 배구) 지원
    """

    def __init__(self, settings=None):
        if settings is None:
            settings = get_settings()
        super().__init__(settings=settings)
        self.kspo_client = KSPOApiClient()
        self.interval = 3600  # 1시간 주기로 실행

    async def run(self) -> None:
        """에이전트 메인 루프"""
        self.logger.info("KSPO Data Collector Agent 시작")

        while True:
            try:
                await self.collect_all_data()
            except Exception as e:
                self.logger.error(f"데이터 수집 중 오류 발생: {e}")

            self.logger.info(f"{self.interval}초 대기 후 다음 수집 시작...")
            await asyncio.sleep(self.interval)

    async def collect_all_data(self) -> None:
        """오늘부터 향후 5일간의 모든 경기 데이터 수집"""
        today = datetime.now()
        total_saved = 0

        self.logger.info("KSPO 데이터 수집 시작 (오늘 ~ 향후 14일)")

        for i in range(15):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            self.logger.info(f"[{target_date}] 경기 목록 조회 중...")

            matches = await self.kspo_client.get_match_list(match_ymd=target_date)
            if matches:
                count = await self.kspo_client.save_matches_to_db(matches)
                total_saved += count
                self.logger.info(f"[{target_date}] {count}개 경기 저장 완료")
            else:
                self.logger.info(f"[{target_date}] 조회된 경기 없음")

        self.logger.info(f"KSPO 데이터 수집 완료. 총 {total_saved}개 경기 처리됨.")


if __name__ == "__main__":
    # 단독 실행 테스트용
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    async def test():
        collector = KSPODataCollector()
        await collector.collect_all_data()

    asyncio.run(test())
