"""
예측 추적기 - 예측 저장/로드 및 누적 통계 관리

핵심 기능:
1. 예측 데이터 저장 (회차별 JSON)
2. 예측 데이터 로드
3. 결과 데이터 로드
4. 누적 통계 계산
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# 상태 저장 경로
STATE_DIR = Path(__file__).parent.parent.parent / ".state"
PREDICTIONS_DIR = STATE_DIR / "predictions"
RESULTS_DIR = STATE_DIR / "results"


@dataclass
class GamePredictionRecord:
    """개별 경기 예측 기록"""
    game_number: int
    home_team: str
    away_team: str
    match_date: str
    match_time: str
    predicted: str           # "1", "X", "2" 또는 "승", "5", "패"
    confidence: float
    multi_selections: List[str]  # 복수 베팅 선택


@dataclass
class RoundPredictionRecord:
    """회차 예측 기록"""
    round_number: int
    game_type: str
    predicted_at: str
    deadline: str
    predictions: List[GamePredictionRecord]
    multi_games: List[int]   # 복수 베팅 경기 번호 리스트
    total_combinations: int  # 총 조합 수 (2^복수경기수)


@dataclass
class CumulativeStats:
    """누적 통계"""
    game_type: str
    total_rounds: int
    completed_rounds: int
    avg_hit_rate: float
    best_hit_rate: float
    best_round: int
    worst_hit_rate: float
    worst_round: int
    single_hits: int         # 단식 전체 적중 횟수
    multi_hit_rate: float    # 복수 베팅 적중률
    recent_5_avg: float      # 최근 5회차 평균
    recent_10_avg: float     # 최근 10회차 평균


class PredictionTracker:
    """예측 추적기"""

    def __init__(self):
        # 디렉토리 생성
        PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (PREDICTIONS_DIR / "soccer_wdl").mkdir(exist_ok=True)
        (PREDICTIONS_DIR / "basketball_w5l").mkdir(exist_ok=True)

    def save_prediction(
        self,
        round_info: Any,
        predictions: List[Dict],
        multi_games: Optional[List[int]] = None,
        game_type: str = "soccer_wdl"
    ) -> bool:
        """
        예측 데이터 저장

        Args:
            round_info: 회차 정보 객체 (round_number, deadline 등)
            predictions: 예측 리스트
            multi_games: 복수 베팅 경기 번호 리스트
            game_type: "soccer_wdl" | "basketball_w5l"

        Returns:
            bool: 저장 성공 여부
        """
        try:
            # RoundInfo 객체에서 필드 추출
            round_number = getattr(round_info, 'round_number', 0)
            deadline_obj = getattr(round_info, 'deadline', None)
            deadline_str = deadline_obj
            if hasattr(deadline_str, 'isoformat'):
                deadline_str = deadline_str.isoformat()

            # 예측 레코드 생성
            pred_records = []
            for pred in predictions:
                record = GamePredictionRecord(
                    game_number=pred.get("game_number", 0),
                    home_team=pred.get("home_team", ""),
                    away_team=pred.get("away_team", ""),
                    match_date=pred.get("match_date", getattr(round_info, 'match_date', '')),
                    match_time=pred.get("match_time", ""),
                    predicted=pred.get("predicted", pred.get("recommended", "")),
                    confidence=pred.get("confidence", 0.0),
                    multi_selections=pred.get("multi_selections", []) or [],
                )
                pred_records.append(record)

            # 회차 레코드 생성
            multi_games_list = multi_games if isinstance(multi_games, list) else []
            round_record = RoundPredictionRecord(
                round_number=round_number,
                game_type=game_type,
                predicted_at=datetime.now().isoformat(),
                deadline=deadline_str,
                predictions=pred_records,
                multi_games=multi_games_list,
                total_combinations=2 ** len(multi_games_list) if multi_games_list else 1,
            )

            # 저장
            file_path = PREDICTIONS_DIR / game_type / f"round_{round_number}.json"
            data = {
                "round_number": round_record.round_number,
                "game_type": round_record.game_type,
                "predicted_at": round_record.predicted_at,
                "deadline": round_record.deadline,
                "predictions": [asdict(p) for p in round_record.predictions],
                "multi_games": round_record.multi_games,
                "total_combinations": round_record.total_combinations,
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"예측 저장: {file_path}")
            return True

        except Exception as e:
            logger.error(f"예측 저장 실패: {e}")
            return False

    def get_prediction(
        self,
        round_number: int,
        game_type: str = "soccer_wdl"
    ) -> Optional[RoundPredictionRecord]:
        """예측 데이터 로드"""
        file_path = PREDICTIONS_DIR / game_type / f"round_{round_number}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            predictions = []
            for p in data.get("predictions", []):
                record = GamePredictionRecord(
                    game_number=p.get("game_number", 0),
                    home_team=p.get("home_team", ""),
                    away_team=p.get("away_team", ""),
                    match_date=p.get("match_date", ""),
                    match_time=p.get("match_time", ""),
                    predicted=p.get("predicted", ""),
                    confidence=p.get("confidence", 0.0),
                    multi_selections=p.get("multi_selections", []) or [],
                )
                predictions.append(record)

            return RoundPredictionRecord(
                round_number=data.get("round_number", round_number),
                game_type=data.get("game_type", game_type),
                predicted_at=data.get("predicted_at", ""),
                deadline=data.get("deadline", ""),
                predictions=predictions,
                multi_games=data.get("multi_games", []),
                total_combinations=data.get("total_combinations", 1),
            )

        except Exception as e:
            logger.error(f"예측 로드 실패: {e}")
            return None

    def get_result(
        self,
        round_number: int,
        game_type: str = "soccer_wdl"
    ) -> Optional[Dict]:
        """결과 데이터 로드"""
        file_path = RESULTS_DIR / f"{game_type}_{round_number}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"결과 로드 실패: {e}")
            return None

    def get_all_rounds(self, game_type: str = "soccer_wdl") -> List[int]:
        """모든 예측 회차 번호 반환"""
        game_dir = PREDICTIONS_DIR / game_type
        rounds = []

        if not game_dir.exists():
            return rounds

        for file_path in game_dir.glob("round_*.json"):
            try:
                round_num = int(file_path.stem.replace("round_", ""))
                rounds.append(round_num)
            except ValueError:
                continue

        return sorted(rounds, reverse=True)

    def get_completed_rounds(self, game_type: str = "soccer_wdl") -> List[int]:
        """결과가 있는 회차 번호 반환"""
        completed = []

        for file_path in RESULTS_DIR.glob(f"{game_type}_*.json"):
            try:
                round_num = int(file_path.stem.replace(f"{game_type}_", ""))
                completed.append(round_num)
            except ValueError:
                continue

        return sorted(completed, reverse=True)

    def get_cumulative_stats(self, game_type: str = "soccer_wdl") -> Optional[CumulativeStats]:
        """누적 통계 계산"""
        all_rounds = self.get_all_rounds(game_type)
        completed = self.get_completed_rounds(game_type)

        if not completed:
            return None

        hit_rates = []
        single_hits = 0
        multi_corrects = []
        round_hit_rates = {}

        for round_num in completed:
            result = self.get_result(round_num, game_type)
            if not result:
                continue

            summary = result.get("summary", {})
            hit_rate = summary.get("hit_rate", 0.0)
            hit_rates.append(hit_rate)
            round_hit_rates[round_num] = hit_rate

            if summary.get("single_hit"):
                single_hits += 1

            # 복수 베팅
            multi_hit = summary.get("multi_combinations_hit", 0)
            multi_corrects.append(multi_hit)

        if not hit_rates:
            return None

        avg_hit_rate = sum(hit_rates) / len(hit_rates)

        # 복수 베팅 적중률 계산 (실제 multi_games 수 기반)
        total_multi_games = 0
        for round_num in completed:
            pred = self.get_prediction(round_num, game_type)
            if pred and pred.multi_games:
                total_multi_games += len(pred.multi_games)
        multi_hit_rate = sum(multi_corrects) / total_multi_games if total_multi_games > 0 else 0.0

        # 최근 트렌드
        recent_5 = hit_rates[:5] if len(hit_rates) >= 5 else hit_rates
        recent_10 = hit_rates[:10] if len(hit_rates) >= 10 else hit_rates

        # 최고/최저 회차 찾기
        best_round = max(round_hit_rates, key=round_hit_rates.get)
        worst_round = min(round_hit_rates, key=round_hit_rates.get)

        return CumulativeStats(
            game_type=game_type,
            total_rounds=len(all_rounds),
            completed_rounds=len(completed),
            avg_hit_rate=avg_hit_rate,
            best_hit_rate=round_hit_rates[best_round],
            best_round=best_round,
            worst_hit_rate=round_hit_rates[worst_round],
            worst_round=worst_round,
            single_hits=single_hits,
            multi_hit_rate=multi_hit_rate,
            recent_5_avg=sum(recent_5) / len(recent_5) if recent_5 else 0.0,
            recent_10_avg=sum(recent_10) / len(recent_10) if recent_10 else 0.0,
        )


# 전역 인스턴스
prediction_tracker = PredictionTracker()


# 테스트
def test_prediction_tracker():
    """테스트 실행"""
    tracker = PredictionTracker()

    print("=" * 60)
    print("축구 승무패 회차:")
    all_rounds = tracker.get_all_rounds("soccer_wdl")
    print(f"  전체: {all_rounds[:10]}...")
    completed = tracker.get_completed_rounds("soccer_wdl")
    print(f"  완료: {completed[:10]}...")

    print()
    stats = tracker.get_cumulative_stats("soccer_wdl")
    if stats:
        print("누적 통계:")
        print(f"  총 회차: {stats.total_rounds}")
        print(f"  완료 회차: {stats.completed_rounds}")
        print(f"  평균 적중률: {stats.avg_hit_rate * 100:.1f}%")
        print(f"  최고: {stats.best_hit_rate * 100:.1f}% ({stats.best_round}회차)")
        print(f"  최저: {stats.worst_hit_rate * 100:.1f}% ({stats.worst_round}회차)")


if __name__ == "__main__":
    test_prediction_tracker()
