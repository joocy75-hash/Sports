"""
예측 추적 시스템 - 예측 저장 및 통계 관리

핵심 기능:
1. 분석 완료 후 예측 결과 저장
2. 회차별 적중률 조회
3. 누적 통계 계산
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)

# 상태 저장 경로
STATE_DIR = Path(__file__).parent.parent.parent / ".state"
PREDICTIONS_DIR = STATE_DIR / "predictions"
RESULTS_DIR = STATE_DIR / "results"
HIT_RATE_HISTORY_FILE = STATE_DIR / "hit_rate_history.json"


@dataclass
class GamePredictionRecord:
    """경기 예측 레코드 (저장용)"""
    game_number: int
    home_team: str
    away_team: str
    match_date: str
    match_time: str

    # 확률
    prob_home: float
    prob_draw: float  # 축구: 무승부, 농구: 5점 이내
    prob_away: float

    # 추천
    predicted: str           # "1", "X", "2" 또는 "승", "5", "패"
    confidence: float

    # 복식 정보
    is_multi: bool = False
    multi_selections: List[str] = field(default_factory=list)

    # AI 분석 정보
    ai_agreement: float = 0.0
    analysis_note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RoundPredictionRecord:
    """회차 예측 레코드 (저장용)"""
    round_number: int
    game_type: str           # "soccer_wdl" | "basketball_w5l"
    predicted_at: str
    deadline: Optional[str]

    predictions: List[GamePredictionRecord]

    # 복수 베팅 정보
    multi_games: List[int] = field(default_factory=list)  # 복수 경기 번호
    total_combinations: int = 1

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "game_type": self.game_type,
            "predicted_at": self.predicted_at,
            "deadline": self.deadline,
            "predictions": [p.to_dict() for p in self.predictions],
            "multi_games": self.multi_games,
            "total_combinations": self.total_combinations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoundPredictionRecord":
        predictions = []
        for p in data.get("predictions", []):
            # List 타입 필드 처리
            if "multi_selections" not in p:
                p["multi_selections"] = []
            predictions.append(GamePredictionRecord(**p))

        return cls(
            round_number=data["round_number"],
            game_type=data["game_type"],
            predicted_at=data["predicted_at"],
            deadline=data.get("deadline"),
            predictions=predictions,
            multi_games=data.get("multi_games", []),
            total_combinations=data.get("total_combinations", 1),
        )


@dataclass
class CumulativeStats:
    """누적 통계"""
    game_type: str
    total_rounds: int
    total_games: int
    total_correct: int
    avg_hit_rate: float
    best_round: int
    best_hit_rate: float
    worst_round: int
    worst_hit_rate: float

    # 복수 베팅 통계
    multi_hit_rate: float = 0.0

    # 최근 트렌드
    recent_5_avg: float = 0.0
    recent_10_avg: float = 0.0


class PredictionTracker:
    """예측 추적 시스템"""

    def __init__(self):
        # 디렉토리 생성
        PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (PREDICTIONS_DIR / "soccer_wdl").mkdir(exist_ok=True)
        (PREDICTIONS_DIR / "basketball_w5l").mkdir(exist_ok=True)

    def save_prediction(
        self,
        round_info,  # RoundInfo from round_manager
        predictions: List[dict],  # GamePrediction 목록 (dict 형태)
        multi_games: List[int] = None
    ) -> str:
        """
        예측 결과 저장

        Args:
            round_info: RoundInfo 객체
            predictions: 예측 목록 (GamePrediction 또는 dict)
            multi_games: 복수 베팅 경기 번호 목록

        Returns:
            저장된 파일 경로
        """
        game_type = round_info.game_type
        round_number = round_info.round_number

        # 예측 레코드 변환
        pred_records = []
        for pred in predictions:
            if hasattr(pred, '__dict__'):
                pred = pred.__dict__

            record = GamePredictionRecord(
                game_number=pred.get("game_number", 0),
                home_team=pred.get("home_team", ""),
                away_team=pred.get("away_team", ""),
                match_date=pred.get("match_date", getattr(round_info, 'match_date', '')),
                match_time=pred.get("match_time", ""),
                prob_home=pred.get("prob_home", 0.0),
                prob_draw=pred.get("prob_draw", 0.0),
                prob_away=pred.get("prob_away", 0.0),
                predicted=pred.get("recommended", pred.get("predicted", "")),
                confidence=pred.get("confidence", 0.0),
                is_multi=pred.get("is_multi", False),
                multi_selections=pred.get("multi_selections", []) or [],
                ai_agreement=pred.get("ai_agreement", 0.0),
                analysis_note=pred.get("analysis_note", ""),
            )
            pred_records.append(record)

        # 회차 레코드 생성
        deadline_str = None
        if hasattr(round_info, 'deadline') and round_info.deadline:
            deadline_str = round_info.deadline.isoformat() if hasattr(round_info.deadline, 'isoformat') else str(round_info.deadline)

        round_record = RoundPredictionRecord(
            round_number=round_number,
            game_type=game_type,
            predicted_at=datetime.now().isoformat(),
            deadline=deadline_str,
            predictions=pred_records,
            multi_games=multi_games if isinstance(multi_games, list) else [],
            total_combinations=2 ** len(multi_games) if isinstance(multi_games, list) and multi_games else 1,
        )

        # 저장
        file_path = PREDICTIONS_DIR / game_type / f"round_{round_number}.json"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(round_record.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"예측 저장: {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"예측 저장 실패: {e}")
            raise

    def get_prediction(
        self,
        round_number: int,
        game_type: str
    ) -> Optional[RoundPredictionRecord]:
        """특정 회차 예측 조회"""
        file_path = PREDICTIONS_DIR / game_type / f"round_{round_number}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return RoundPredictionRecord.from_dict(data)
        except Exception as e:
            logger.error(f"예측 로드 실패: {e}")
            return None

    def get_result(
        self,
        round_number: int,
        game_type: str
    ) -> Optional[dict]:
        """특정 회차 결과 조회"""
        file_path = RESULTS_DIR / f"{game_type}_{round_number}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"결과 로드 실패: {e}")
            return None

    def get_pending_rounds(self, game_type: str) -> List[int]:
        """
        결과 미수집 회차 목록 반환

        조건:
        - 예측 파일은 있지만 결과 파일이 없음
        """
        pending = []
        game_dir = PREDICTIONS_DIR / game_type

        if not game_dir.exists():
            return pending

        for pred_file in game_dir.glob("round_*.json"):
            if "_result" in pred_file.name:
                continue

            try:
                round_num = int(pred_file.stem.replace("round_", ""))
            except ValueError:
                continue

            result_file = RESULTS_DIR / f"{game_type}_{round_num}.json"
            if not result_file.exists():
                pending.append(round_num)

        return sorted(pending)

    def get_completed_rounds(self, game_type: str, limit: int = 50) -> List[int]:
        """결과 수집 완료된 회차 목록"""
        completed = []

        if not RESULTS_DIR.exists():
            return completed

        for result_file in RESULTS_DIR.glob(f"{game_type}_*.json"):
            try:
                round_num = int(result_file.stem.split('_')[-1])
                completed.append(round_num)
            except ValueError:
                continue

        return sorted(completed, reverse=True)[:limit]

    def get_cumulative_stats(
        self,
        game_type: str,
        last_n_rounds: int = 10
    ) -> Optional[CumulativeStats]:
        """
        누적 통계 조회

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"
            last_n_rounds: 최근 N회차 (0이면 전체)

        Returns:
            CumulativeStats 또는 None
        """
        completed = self.get_completed_rounds(game_type, limit=last_n_rounds if last_n_rounds > 0 else 100)

        if not completed:
            return None

        # 통계 계산
        total_games = 0
        total_correct = 0
        hit_rates = []
        multi_corrects = []

        best_round = 0
        best_hit_rate = 0.0
        worst_round = 0
        worst_hit_rate = 1.0

        for round_num in completed:
            result = self.get_result(round_num, game_type)
            if not result:
                continue

            summary = result.get("summary", {})
            games = summary.get("total_games", 14)
            correct = summary.get("correct_predictions", 0)
            hit_rate = summary.get("hit_rate", 0.0)

            total_games += games
            total_correct += correct
            hit_rates.append(hit_rate)

            # 최고/최저
            if hit_rate > best_hit_rate:
                best_hit_rate = hit_rate
                best_round = round_num
            if hit_rate < worst_hit_rate:
                worst_hit_rate = hit_rate
                worst_round = round_num

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

        return CumulativeStats(
            game_type=game_type,
            total_rounds=len(completed),
            total_games=total_games,
            total_correct=total_correct,
            avg_hit_rate=avg_hit_rate,
            best_round=best_round,
            best_hit_rate=best_hit_rate,
            worst_round=worst_round,
            worst_hit_rate=worst_hit_rate,
            multi_hit_rate=multi_hit_rate,
            recent_5_avg=sum(recent_5) / len(recent_5) if recent_5 else 0.0,
            recent_10_avg=sum(recent_10) / len(recent_10) if recent_10 else 0.0,
        )

    def save_hit_rate_history(self, game_type: str, round_number: int, hit_rate: float):
        """적중률 이력 저장"""
        try:
            history = {}
            if HIT_RATE_HISTORY_FILE.exists():
                with open(HIT_RATE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    history = json.load(f)

            if game_type not in history:
                history[game_type] = {}

            history[game_type][str(round_number)] = {
                "hit_rate": hit_rate,
                "updated_at": datetime.now().isoformat(),
            }

            with open(HIT_RATE_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"적중률 이력 저장 실패: {e}")


# 전역 인스턴스
prediction_tracker = PredictionTracker()


# 테스트
def test_prediction_tracker():
    """테스트"""
    tracker = PredictionTracker()

    print("=" * 60)
    print("축구 승무패 회차 목록:")
    print(f"  대기 중: {tracker.get_pending_rounds('soccer_wdl')}")
    print(f"  완료: {tracker.get_completed_rounds('soccer_wdl')}")

    print()
    print("농구 승5패 회차 목록:")
    print(f"  대기 중: {tracker.get_pending_rounds('basketball_w5l')}")
    print(f"  완료: {tracker.get_completed_rounds('basketball_w5l')}")


if __name__ == "__main__":
    test_prediction_tracker()
