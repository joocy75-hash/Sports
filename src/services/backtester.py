"""
A-04: 백테스팅 시스템
과거 예측 결과를 분석하여 모델 성능을 평가합니다.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from collections import defaultdict


class BetResult(Enum):
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"  # 무효
    PENDING = "pending"


@dataclass
class PredictionRecord:
    """예측 기록"""
    prediction_id: str
    match_id: int
    match_date: str
    home_team: str
    away_team: str
    league: str
    predicted_outcome: str  # "home", "draw", "away"
    predicted_probability: float
    confidence: float
    odds: float
    stake: float
    actual_result: Optional[str] = None
    bet_result: BetResult = BetResult.PENDING
    profit_loss: float = 0.0
    model_name: str = "ensemble"


@dataclass
class BacktestResult:
    """백테스트 결과"""
    total_bets: int
    wins: int
    losses: int
    pushes: int
    win_rate: float
    roi: float  # Return on Investment
    total_stake: float
    total_profit: float
    avg_odds: float
    avg_confidence: float
    profit_factor: float  # 총 이익 / 총 손실
    max_drawdown: float
    sharpe_ratio: float
    by_league: Dict[str, Dict[str, float]]
    by_confidence: Dict[str, Dict[str, float]]
    by_odds_range: Dict[str, Dict[str, float]]
    monthly_performance: Dict[str, Dict[str, float]]
    streak_analysis: Dict[str, Any]


class Backtester:
    """백테스팅 엔진"""

    def __init__(self):
        self.predictions: List[PredictionRecord] = []
        self._load_history()

    def _load_history(self):
        """저장된 예측 기록 로드"""
        try:
            with open("prediction_history.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.predictions = [
                    PredictionRecord(**p) for p in data
                ]
        except FileNotFoundError:
            self.predictions = []
        except Exception as e:
            print(f"[Backtester] 히스토리 로드 실패: {e}")
            self.predictions = []

    def _save_history(self):
        """예측 기록 저장"""
        try:
            data = [
                {
                    "prediction_id": p.prediction_id,
                    "match_id": p.match_id,
                    "match_date": p.match_date,
                    "home_team": p.home_team,
                    "away_team": p.away_team,
                    "league": p.league,
                    "predicted_outcome": p.predicted_outcome,
                    "predicted_probability": p.predicted_probability,
                    "confidence": p.confidence,
                    "odds": p.odds,
                    "stake": p.stake,
                    "actual_result": p.actual_result,
                    "bet_result": p.bet_result.value,
                    "profit_loss": p.profit_loss,
                    "model_name": p.model_name
                }
                for p in self.predictions
            ]
            with open("prediction_history.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Backtester] 히스토리 저장 실패: {e}")

    def record_prediction(
        self,
        match_id: int,
        match_date: str,
        home_team: str,
        away_team: str,
        league: str,
        predicted_outcome: str,
        predicted_probability: float,
        confidence: float,
        odds: float,
        stake: float = 10000,
        model_name: str = "ensemble"
    ) -> str:
        """예측 기록 추가"""
        prediction_id = f"{match_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        record = PredictionRecord(
            prediction_id=prediction_id,
            match_id=match_id,
            match_date=match_date,
            home_team=home_team,
            away_team=away_team,
            league=league,
            predicted_outcome=predicted_outcome,
            predicted_probability=predicted_probability,
            confidence=confidence,
            odds=odds,
            stake=stake,
            model_name=model_name
        )

        self.predictions.append(record)
        self._save_history()
        return prediction_id

    def update_result(
        self,
        prediction_id: str,
        actual_result: str
    ) -> Optional[PredictionRecord]:
        """실제 결과 업데이트"""
        for pred in self.predictions:
            if pred.prediction_id == prediction_id:
                pred.actual_result = actual_result

                if pred.predicted_outcome == actual_result:
                    pred.bet_result = BetResult.WIN
                    pred.profit_loss = (pred.odds - 1) * pred.stake
                else:
                    pred.bet_result = BetResult.LOSS
                    pred.profit_loss = -pred.stake

                self._save_history()
                return pred

        return None

    def update_result_by_match(
        self,
        match_id: int,
        actual_result: str
    ) -> List[PredictionRecord]:
        """경기 ID로 결과 업데이트"""
        updated = []
        for pred in self.predictions:
            if pred.match_id == match_id and pred.bet_result == BetResult.PENDING:
                pred.actual_result = actual_result

                if pred.predicted_outcome == actual_result:
                    pred.bet_result = BetResult.WIN
                    pred.profit_loss = (pred.odds - 1) * pred.stake
                else:
                    pred.bet_result = BetResult.LOSS
                    pred.profit_loss = -pred.stake

                updated.append(pred)

        if updated:
            self._save_history()
        return updated

    def run_backtest(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_confidence: float = 0,
        max_confidence: float = 100,
        leagues: Optional[List[str]] = None,
        model_name: Optional[str] = None
    ) -> BacktestResult:
        """백테스트 실행"""
        # 필터링
        filtered = [
            p for p in self.predictions
            if p.bet_result != BetResult.PENDING
        ]

        if start_date:
            filtered = [p for p in filtered if p.match_date >= start_date]
        if end_date:
            filtered = [p for p in filtered if p.match_date <= end_date]
        if min_confidence > 0:
            filtered = [p for p in filtered if p.confidence >= min_confidence]
        if max_confidence < 100:
            filtered = [p for p in filtered if p.confidence <= max_confidence]
        if leagues:
            filtered = [p for p in filtered if p.league in leagues]
        if model_name:
            filtered = [p for p in filtered if p.model_name == model_name]

        if not filtered:
            return self._empty_result()

        # 기본 통계
        wins = sum(1 for p in filtered if p.bet_result == BetResult.WIN)
        losses = sum(1 for p in filtered if p.bet_result == BetResult.LOSS)
        pushes = sum(1 for p in filtered if p.bet_result == BetResult.PUSH)
        total = len(filtered)

        total_stake = sum(p.stake for p in filtered)
        total_profit = sum(p.profit_loss for p in filtered)

        win_rate = wins / total * 100 if total > 0 else 0
        roi = total_profit / total_stake * 100 if total_stake > 0 else 0

        avg_odds = sum(p.odds for p in filtered) / total if total > 0 else 0
        avg_confidence = sum(p.confidence for p in filtered) / total if total > 0 else 0

        # Profit Factor
        total_wins = sum(p.profit_loss for p in filtered if p.profit_loss > 0)
        total_losses = abs(sum(p.profit_loss for p in filtered if p.profit_loss < 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Max Drawdown
        max_drawdown = self._calculate_max_drawdown(filtered)

        # Sharpe Ratio (일일 수익률 기준)
        sharpe_ratio = self._calculate_sharpe_ratio(filtered)

        # 리그별 분석
        by_league = self._analyze_by_group(filtered, lambda p: p.league)

        # 신뢰도별 분석
        by_confidence = self._analyze_by_confidence(filtered)

        # 배당률별 분석
        by_odds_range = self._analyze_by_odds(filtered)

        # 월별 성과
        monthly = self._analyze_monthly(filtered)

        # 연승/연패 분석
        streak = self._analyze_streaks(filtered)

        return BacktestResult(
            total_bets=total,
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=round(win_rate, 2),
            roi=round(roi, 2),
            total_stake=total_stake,
            total_profit=round(total_profit, 2),
            avg_odds=round(avg_odds, 2),
            avg_confidence=round(avg_confidence, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_drawdown, 2),
            sharpe_ratio=round(sharpe_ratio, 2),
            by_league=by_league,
            by_confidence=by_confidence,
            by_odds_range=by_odds_range,
            monthly_performance=monthly,
            streak_analysis=streak
        )

    def _empty_result(self) -> BacktestResult:
        """빈 결과 반환"""
        return BacktestResult(
            total_bets=0, wins=0, losses=0, pushes=0,
            win_rate=0, roi=0, total_stake=0, total_profit=0,
            avg_odds=0, avg_confidence=0, profit_factor=0,
            max_drawdown=0, sharpe_ratio=0,
            by_league={}, by_confidence={}, by_odds_range={},
            monthly_performance={}, streak_analysis={}
        )

    def _calculate_max_drawdown(self, predictions: List[PredictionRecord]) -> float:
        """최대 낙폭 계산"""
        if not predictions:
            return 0

        cumulative = 0
        peak = 0
        max_dd = 0

        sorted_preds = sorted(predictions, key=lambda p: p.match_date)
        for pred in sorted_preds:
            cumulative += pred.profit_loss
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd

    def _calculate_sharpe_ratio(self, predictions: List[PredictionRecord]) -> float:
        """샤프 비율 계산"""
        if len(predictions) < 2:
            return 0

        # 일별 수익률 계산
        daily_returns = defaultdict(float)
        for pred in predictions:
            daily_returns[pred.match_date] += pred.profit_loss

        returns = list(daily_returns.values())
        if not returns:
            return 0

        avg_return = sum(returns) / len(returns)
        if len(returns) < 2:
            return 0

        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5

        if std_dev == 0:
            return 0

        # 연율화 (252 거래일 가정)
        sharpe = (avg_return / std_dev) * (252 ** 0.5)
        return sharpe

    def _analyze_by_group(
        self,
        predictions: List[PredictionRecord],
        key_func
    ) -> Dict[str, Dict[str, float]]:
        """그룹별 분석"""
        groups = defaultdict(list)
        for pred in predictions:
            groups[key_func(pred)].append(pred)

        result = {}
        for group_name, group_preds in groups.items():
            wins = sum(1 for p in group_preds if p.bet_result == BetResult.WIN)
            total = len(group_preds)
            profit = sum(p.profit_loss for p in group_preds)
            stake = sum(p.stake for p in group_preds)

            result[group_name] = {
                "total": total,
                "wins": wins,
                "win_rate": round(wins / total * 100, 2) if total > 0 else 0,
                "profit": round(profit, 2),
                "roi": round(profit / stake * 100, 2) if stake > 0 else 0
            }

        return result

    def _analyze_by_confidence(
        self,
        predictions: List[PredictionRecord]
    ) -> Dict[str, Dict[str, float]]:
        """신뢰도별 분석"""
        ranges = [
            ("50-60%", 50, 60),
            ("60-70%", 60, 70),
            ("70-80%", 70, 80),
            ("80-90%", 80, 90),
            ("90-100%", 90, 100)
        ]

        def get_range(pred):
            for name, low, high in ranges:
                if low <= pred.confidence < high:
                    return name
            return "90-100%"

        return self._analyze_by_group(predictions, get_range)

    def _analyze_by_odds(
        self,
        predictions: List[PredictionRecord]
    ) -> Dict[str, Dict[str, float]]:
        """배당률별 분석"""
        ranges = [
            ("1.0-1.5", 1.0, 1.5),
            ("1.5-2.0", 1.5, 2.0),
            ("2.0-2.5", 2.0, 2.5),
            ("2.5-3.0", 2.5, 3.0),
            ("3.0+", 3.0, 100)
        ]

        def get_range(pred):
            for name, low, high in ranges:
                if low <= pred.odds < high:
                    return name
            return "3.0+"

        return self._analyze_by_group(predictions, get_range)

    def _analyze_monthly(
        self,
        predictions: List[PredictionRecord]
    ) -> Dict[str, Dict[str, float]]:
        """월별 성과 분석"""
        def get_month(pred):
            return pred.match_date[:7]  # YYYY-MM

        return self._analyze_by_group(predictions, get_month)

    def _analyze_streaks(
        self,
        predictions: List[PredictionRecord]
    ) -> Dict[str, Any]:
        """연승/연패 분석"""
        sorted_preds = sorted(predictions, key=lambda p: p.match_date)

        current_streak = 0
        current_type = None
        max_win_streak = 0
        max_loss_streak = 0
        streaks = []

        for pred in sorted_preds:
            if pred.bet_result == BetResult.WIN:
                if current_type == "win":
                    current_streak += 1
                else:
                    if current_type == "loss" and current_streak > 0:
                        streaks.append(("loss", current_streak))
                    current_streak = 1
                    current_type = "win"
                max_win_streak = max(max_win_streak, current_streak)

            elif pred.bet_result == BetResult.LOSS:
                if current_type == "loss":
                    current_streak += 1
                else:
                    if current_type == "win" and current_streak > 0:
                        streaks.append(("win", current_streak))
                    current_streak = 1
                    current_type = "loss"
                max_loss_streak = max(max_loss_streak, current_streak)

        if current_streak > 0:
            streaks.append((current_type, current_streak))

        return {
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "current_streak": current_streak,
            "current_streak_type": current_type,
            "avg_win_streak": self._avg_streak(streaks, "win"),
            "avg_loss_streak": self._avg_streak(streaks, "loss")
        }

    def _avg_streak(self, streaks: List[Tuple[str, int]], streak_type: str) -> float:
        """평균 연속 수 계산"""
        filtered = [s[1] for s in streaks if s[0] == streak_type]
        return round(sum(filtered) / len(filtered), 2) if filtered else 0

    def get_summary(self) -> Dict[str, Any]:
        """간단한 요약 정보"""
        result = self.run_backtest()
        return {
            "total_bets": result.total_bets,
            "win_rate": result.win_rate,
            "roi": result.roi,
            "total_profit": result.total_profit,
            "profit_factor": result.profit_factor,
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio
        }

    def to_dict(self, result: BacktestResult) -> Dict[str, Any]:
        """결과를 딕셔너리로 변환"""
        return {
            "total_bets": result.total_bets,
            "wins": result.wins,
            "losses": result.losses,
            "pushes": result.pushes,
            "win_rate": result.win_rate,
            "roi": result.roi,
            "total_stake": result.total_stake,
            "total_profit": result.total_profit,
            "avg_odds": result.avg_odds,
            "avg_confidence": result.avg_confidence,
            "profit_factor": result.profit_factor,
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio,
            "by_league": result.by_league,
            "by_confidence": result.by_confidence,
            "by_odds_range": result.by_odds_range,
            "monthly_performance": result.monthly_performance,
            "streak_analysis": result.streak_analysis
        }


# 싱글톤 인스턴스
_backtester: Optional[Backtester] = None


def get_backtester() -> Backtester:
    """싱글톤 백테스터 반환"""
    global _backtester
    if _backtester is None:
        _backtester = Backtester()
    return _backtester


# 테스트
if __name__ == "__main__":
    import random

    backtester = Backtester()

    # 테스트 데이터 생성
    print("\n[테스트 데이터 생성]")
    leagues = ["프리미어리그", "라리가", "분데스리가", "세리에A"]
    outcomes = ["home", "draw", "away"]

    for i in range(50):
        date = (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d")
        pred_id = backtester.record_prediction(
            match_id=10000 + i,
            match_date=date,
            home_team=f"HomeTeam{i}",
            away_team=f"AwayTeam{i}",
            league=random.choice(leagues),
            predicted_outcome=random.choice(outcomes),
            predicted_probability=random.uniform(40, 70),
            confidence=random.uniform(50, 90),
            odds=random.uniform(1.5, 3.0),
            stake=10000
        )

        # 결과 업데이트 (70% 승률 시뮬레이션)
        actual = random.choice(outcomes)
        backtester.update_result(pred_id, actual)

    # 백테스트 실행
    print("\n[백테스트 결과]")
    result = backtester.run_backtest()
    print(f"  총 베팅: {result.total_bets}")
    print(f"  승률: {result.win_rate}%")
    print(f"  ROI: {result.roi}%")
    print(f"  총 수익: {result.total_profit:,.0f}원")
    print(f"  Profit Factor: {result.profit_factor}")
    print(f"  Max Drawdown: {result.max_drawdown:,.0f}원")
    print(f"  Sharpe Ratio: {result.sharpe_ratio}")

    print("\n[신뢰도별 성과]")
    for conf_range, stats in result.by_confidence.items():
        print(f"  {conf_range}: 승률 {stats['win_rate']}%, ROI {stats['roi']}%")

    print("\n[연승/연패 분석]")
    print(f"  최대 연승: {result.streak_analysis['max_win_streak']}")
    print(f"  최대 연패: {result.streak_analysis['max_loss_streak']}")
