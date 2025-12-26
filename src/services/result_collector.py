"""
경기 결과 수집기 - KSPO API에서 경기 결과 수집

핵심 기능:
1. 특정 날짜의 경기 결과 수집 (match_end_val)
2. 예측 데이터와 경기 결과 매칭
3. 적중 여부 계산
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
import httpx

from src.config.settings import get_settings
from src.services.team_name_normalizer import team_normalizer

logger = logging.getLogger(__name__)

# 상태 저장 경로
STATE_DIR = Path(__file__).parent.parent.parent / ".state"
PREDICTIONS_DIR = STATE_DIR / "predictions"
RESULTS_DIR = STATE_DIR / "results"


@dataclass
class GameResult:
    """경기 결과"""
    game_number: int
    home_team: str
    away_team: str
    match_date: str
    match_time: str

    # 예측 정보
    predicted: str           # "1", "X", "2" 또는 "승", "5", "패"
    predicted_multi: List[str] = field(default_factory=list)
    confidence: float = 0.0

    # 실제 결과 (KSPO API에서)
    actual: str = ""         # 실제 결과
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    match_end_val: str = ""  # API 원본 값

    # 적중 여부
    is_correct: bool = False
    is_multi_correct: bool = False  # 복수 베팅 시

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoundResult:
    """회차 결과"""
    round_number: int
    game_type: str
    predicted_at: str
    collected_at: str

    results: List[GameResult]

    # 통계
    total_games: int = 14
    correct_predictions: int = 0
    hit_rate: float = 0.0
    single_hit: bool = False
    multi_combinations_hit: int = 0

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "game_type": self.game_type,
            "predicted_at": self.predicted_at,
            "collected_at": self.collected_at,
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total_games": self.total_games,
                "correct_predictions": self.correct_predictions,
                "hit_rate": self.hit_rate,
                "single_hit": self.single_hit,
                "multi_combinations_hit": self.multi_combinations_hit,
            }
        }


class ResultCollector:
    """KSPO API 경기 결과 수집기"""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.kspo_todz_api_key
        self.base_url = settings.kspo_todz_api_base_url

        # 디렉토리 생성
        PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (PREDICTIONS_DIR / "soccer_wdl").mkdir(exist_ok=True)
        (PREDICTIONS_DIR / "basketball_w5l").mkdir(exist_ok=True)

    async def collect_round_results(
        self,
        round_number: int,
        game_type: str = "soccer_wdl"
    ) -> Optional[RoundResult]:
        """
        특정 회차의 경기 결과 수집

        Args:
            round_number: 회차 번호
            game_type: "soccer_wdl" | "basketball_w5l"

        Returns:
            RoundResult: 결과 (없으면 None)
        """
        # 입력 검증
        if not isinstance(round_number, int) or round_number < 0:
            logger.error(f"유효하지 않은 회차 번호: {round_number}")
            return None

        if game_type not in ("soccer_wdl", "basketball_w5l"):
            logger.error(f"유효하지 않은 게임 타입: {game_type}")
            return None

        # 1. 저장된 예측 데이터 로드
        prediction_file = PREDICTIONS_DIR / game_type / f"round_{round_number}.json"

        if not prediction_file.exists():
            logger.warning(f"예측 데이터 없음: {prediction_file}")
            return None

        try:
            with open(prediction_file, 'r', encoding='utf-8') as f:
                prediction_data = json.load(f)
        except Exception as e:
            logger.error(f"예측 데이터 로드 실패: {e}")
            return None

        # 2. 예측의 경기 날짜 추출
        match_dates = set()
        for pred in prediction_data.get("predictions", []):
            date = pred.get("match_date", "")
            if date:
                # YYYYMMDD 형식으로 변환
                if "-" in date:
                    date = date.replace("-", "")
                match_dates.add(date)

        if not match_dates:
            logger.warning("경기 날짜 정보 없음")
            return None

        # 3. KSPO API에서 해당 날짜 경기 결과 조회
        api_results = []
        for date in match_dates:
            results = await self._fetch_results_by_date(date, game_type)
            api_results.extend(results)

        if not api_results:
            logger.warning(f"API 결과 없음 (날짜: {match_dates})")
            return None

        # 4. 예측과 결과 매칭
        game_results = self._match_results_with_predictions(
            prediction_data.get("predictions", []),
            api_results,
            game_type
        )

        # 5. 적중률 계산
        correct_count = sum(1 for r in game_results if r.is_correct)
        hit_rate = correct_count / len(game_results) if game_results else 0.0
        single_hit = correct_count == len(game_results)

        # 복수 베팅 적중 조합 계산
        multi_games = [r for r in game_results if r.predicted_multi]
        if multi_games:
            all_multi_correct = all(r.is_multi_correct for r in multi_games)
            multi_hit = 1 if all_multi_correct else 0
        else:
            multi_hit = 0

        result = RoundResult(
            round_number=round_number,
            game_type=game_type,
            predicted_at=prediction_data.get("predicted_at", datetime.now().isoformat()),
            collected_at=datetime.now().isoformat(),
            results=game_results,
            total_games=len(game_results),
            correct_predictions=correct_count,
            hit_rate=hit_rate,
            single_hit=single_hit,
            multi_combinations_hit=multi_hit,
        )

        # 6. 결과 저장
        result_file = RESULTS_DIR / f"{game_type}_{round_number}.json"
        try:
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"결과 저장: {result_file}")
        except Exception as e:
            logger.error(f"결과 저장 실패: {e}")

        return result

    async def _fetch_results_by_date(
        self,
        date_str: str,
        game_type: str
    ) -> List[Dict]:
        """특정 날짜의 경기 결과 조회"""
        endpoint = f"{self.base_url}/todz_api_tb_match_mgmt_i"
        params = {
            "serviceKey": self.api_key,
            "pageNo": 1,
            "numOfRows": 200,
            "resultType": "JSON",
            "match_ymd": date_str,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, params=params, timeout=15.0)

                if response.status_code != 200:
                    logger.error(f"API 오류: {response.status_code}")
                    return []

                data = response.json()

                # API 응답 구조 검증
                response_data = data.get("response")
                if not response_data or not isinstance(response_data, dict):
                    logger.error(f"유효하지 않은 API 응답 구조")
                    return []

                body = response_data.get("body", {})
                items_container = body.get("items", {})
                items = items_container.get("item", []) if items_container else []

                if isinstance(items, dict):
                    items = [items]

                # 종목 필터링
                sport = "축구" if game_type == "soccer_wdl" else "농구"
                filtered = [
                    m for m in items
                    if m.get("match_sport_han_nm") == sport
                    and m.get("match_end_val")  # 결과가 있는 경기만
                ]

                logger.info(f"{date_str}: {len(filtered)}개 결과 수집")
                return filtered

        except Exception as e:
            logger.error(f"API 요청 실패 ({date_str}): {e}")
            return []

    def _match_results_with_predictions(
        self,
        predictions: List[Dict],
        api_results: List[Dict],
        game_type: str
    ) -> List[GameResult]:
        """예측과 API 결과 매칭"""
        game_results = []

        for pred in predictions:
            home_team = pred.get("home_team", "")
            away_team = pred.get("away_team", "")

            # API 결과에서 해당 경기 찾기
            matched_result = self._find_matching_result(
                home_team, away_team, api_results
            )

            # 예측 결과
            predicted = pred.get("predicted", pred.get("recommended", ""))
            predicted_multi = pred.get("multi_selections", []) or []
            confidence = pred.get("confidence", 0.0)

            # 실제 결과
            actual = ""
            score_home = None
            score_away = None
            match_end_val = ""
            is_correct = False
            is_multi_correct = False

            if matched_result:
                match_end_val = matched_result.get("match_end_val", "")
                actual = self._parse_result(match_end_val, game_type, matched_result)
                score_home = matched_result.get("home_score")
                score_away = matched_result.get("away_score")

                # 적중 여부
                is_correct = (predicted == actual)

                # 복수 베팅 적중 여부
                if predicted_multi:
                    is_multi_correct = (actual in predicted_multi)

            game_result = GameResult(
                game_number=pred.get("game_number", 0),
                home_team=home_team,
                away_team=away_team,
                match_date=pred.get("match_date", ""),
                match_time=pred.get("match_time", ""),
                predicted=predicted,
                predicted_multi=predicted_multi,
                confidence=confidence,
                actual=actual,
                score_home=score_home,
                score_away=score_away,
                match_end_val=match_end_val,
                is_correct=is_correct,
                is_multi_correct=is_multi_correct,
            )
            game_results.append(game_result)

        return game_results

    def _find_matching_result(
        self,
        home_team: str,
        away_team: str,
        api_results: List[Dict]
    ) -> Optional[Dict]:
        """API 결과에서 해당 경기 찾기"""
        best_match = None
        best_score = 0.0

        for result in api_results:
            api_home = result.get("hteam_han_nm", "")
            api_away = result.get("ateam_han_nm", "")

            home_match = team_normalizer.match_team(home_team, api_home)
            away_match = team_normalizer.match_team(away_team, api_away)

            if home_match.confidence >= 0.6 and away_match.confidence >= 0.6:
                combined = (home_match.confidence + away_match.confidence) / 2
                if combined > best_score:
                    best_score = combined
                    best_match = result

        return best_match

    def _parse_result(self, match_end_val: str, game_type: str, api_result: Dict) -> str:
        """
        match_end_val을 결과 코드로 변환

        축구 승무패:
        - "승리", "홈승" → "1"
        - "무승부", "무" → "X"
        - "패배", "원정승" → "2"

        농구 승5패:
        - 홈팀 6점 이상 승 → "승"
        - 5점 이내 → "5"
        - 원정팀 6점 이상 승 → "패"
        """
        val = match_end_val.strip().lower() if match_end_val else ""

        if game_type == "soccer_wdl":
            if not val:
                return ""
            if val in ["승", "승리", "홈승", "1", "w"]:
                return "1"
            elif val in ["무", "무승부", "x", "d", "draw"]:
                return "X"
            elif val in ["패", "패배", "원정승", "2", "l"]:
                return "2"

        elif game_type == "basketball_w5l":
            # 점수 기반 판정 (우선)
            home_score = api_result.get("home_score", 0)
            away_score = api_result.get("away_score", 0)

            if home_score is not None and away_score is not None:
                try:
                    diff = int(home_score) - int(away_score)

                    if diff >= 6:
                        return "승"
                    elif diff <= -6:
                        return "패"
                    else:
                        return "5"
                except (ValueError, TypeError):
                    pass

            # 텍스트 기반 판정 (fallback)
            if val in ["승", "홈승", "w"]:
                return "승"
            elif val in ["5", "5점이내"]:
                return "5"
            elif val in ["패", "원정승", "l"]:
                return "패"

        return match_end_val

    async def check_pending_rounds(self, game_type: str) -> List[int]:
        """
        결과 미수집 회차 목록 반환

        조건:
        - 예측 파일은 있지만 결과 파일이 없음
        - deadline이 지남 (24시간 이상)
        """
        pending = []
        game_dir = PREDICTIONS_DIR / game_type

        if not game_dir.exists():
            return pending

        for pred_file in game_dir.glob("round_*.json"):
            if "_result" in pred_file.name:
                continue

            # 회차 번호 추출
            try:
                round_num = int(pred_file.stem.replace("round_", ""))
            except ValueError:
                continue

            # 결과 파일 존재 확인
            result_file = RESULTS_DIR / f"{game_type}_{round_num}.json"
            if result_file.exists():
                continue

            # deadline 확인
            try:
                with open(pred_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                deadline_str = data.get("deadline")
                if deadline_str:
                    deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
                    if deadline.tzinfo is not None:
                        deadline = deadline.replace(tzinfo=None)
                    if datetime.now() > deadline + timedelta(hours=24):
                        pending.append(round_num)
            except FileNotFoundError:
                logger.warning(f"예측 파일 없음: {pred_file}")
                continue
            except json.JSONDecodeError as e:
                logger.error(f"손상된 예측 파일: {pred_file}, {e}")
                pending.append(round_num)
            except (ValueError, KeyError) as e:
                logger.warning(f"유효하지 않은 deadline: {pred_file}, {e}")
                pending.append(round_num)

        return sorted(pending)

    async def collect_all_pending(self, game_type: str) -> Dict[int, bool]:
        """모든 미수집 회차 결과 수집"""
        pending = await self.check_pending_rounds(game_type)
        results = {}

        for round_num in pending:
            try:
                result = await self.collect_round_results(round_num, game_type)
                results[round_num] = (result is not None)
                await asyncio.sleep(1)  # API 호출 간격
            except Exception as e:
                logger.error(f"회차 {round_num} 수집 실패: {e}")
                results[round_num] = False

        return results


# 전역 인스턴스
result_collector = ResultCollector()


# 테스트
async def test_result_collector():
    """테스트 실행"""
    collector = ResultCollector()

    print("=" * 60)
    print("축구 승무패 미수집 회차:")
    pending = await collector.check_pending_rounds("soccer_wdl")
    print(f"  {pending}")

    print()
    print("농구 승5패 미수집 회차:")
    pending = await collector.check_pending_rounds("basketball_w5l")
    print(f"  {pending}")


if __name__ == "__main__":
    asyncio.run(test_result_collector())
