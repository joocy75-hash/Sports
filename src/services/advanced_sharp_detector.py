# src/services/advanced_sharp_detector.py

"""
다층 Sharp Money 감지 시스템

- Steam Move (급격한 배당 변화)
- Reverse Line Movement (대중과 반대 방향 움직임)
- Sharp Bookmaker 선행 움직임
- 베팅 볼륨 이상 탐지
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import Match, OddsHistory


@dataclass
class SharpSignal:
    """Sharp Money 신호 데이터 클래스"""

    match_id: int
    signal_strength: float  # 0-100
    direction: str  # "home", "away", "draw"
    indicators: List[str]
    confidence: float  # 0-1
    detected_at: datetime
    odds_movement: Dict[str, float]


class AdvancedSharpDetector:
    """
    다중 지표 기반 Sharp Money 탐지기
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        # Sharp 북메이커: 전문가들이 먼저 베팅하는 곳
        self.sharp_bookmakers = ["Pinnacle", "Bookmaker.eu", "BetCRIS", "SBOBet"]
        # Public 북메이커: 일반인들이 주로 사용
        self.public_bookmakers = ["Bet365", "William Hill", "Ladbrokes", "888sport"]

    async def detect_sharp_action(
        self,
        match_id: int,
        historical_odds: List[dict],
        betting_volume: Optional[dict] = None,
    ) -> Optional[SharpSignal]:
        """
        Sharp Money 종합 감지

        Args:
            match_id: 경기 ID
            historical_odds: 시간순 배당 기록 (최소 10개 스냅샷)
            betting_volume: 베팅 볼륨 데이터 (선택)

        Returns:
            SharpSignal 또는 None
        """
        if len(historical_odds) < 3:
            return None

        indicators = []
        signal_strength = 0

        # 1. 🔥 Steam Move 감지 (급격한 배당 하락)
        steam_result = self._detect_steam_move(historical_odds)
        if steam_result["detected"]:
            indicators.append(f"Steam Move: {steam_result['description']}")
            signal_strength += 30

        # 2. 🔄 Reverse Line Movement (역방향 라인 움직임)
        if betting_volume:
            reverse_result = self._detect_reverse_line_movement(
                historical_odds, betting_volume
            )
            if reverse_result["detected"]:
                indicators.append(f"Reverse Line: {reverse_result['description']}")
                signal_strength += 35

        # 3. 📊 Sharp Bookmaker 선행 움직임
        sharp_lead = self._detect_sharp_bookmaker_lead(historical_odds)
        if sharp_lead["detected"]:
            indicators.append(f"Sharp Books Lead: {sharp_lead['description']}")
            signal_strength += 25

        # 4. 📈 베팅 볼륨 급증
        if betting_volume:
            volume_spike = self._detect_volume_spike(betting_volume)
            if volume_spike["detected"]:
                indicators.append(f"Volume Spike: {volume_spike['description']}")
                signal_strength += 10

        # 신호 강도가 충분히 높으면 반환
        if signal_strength >= 40:  # 임계값: 40점
            direction = self._determine_direction(historical_odds)
            odds_movement = self._calculate_odds_movement(historical_odds)

            return SharpSignal(
                match_id=match_id,
                signal_strength=min(signal_strength, 100),
                direction=direction,
                indicators=indicators,
                confidence=min(signal_strength / 100, 0.95),
                detected_at=datetime.utcnow(),
                odds_movement=odds_movement,
            )

        return None

    def _detect_steam_move(self, odds: List[dict]) -> dict:
        """
        Steam Move: 10분 이내 5% 이상의 급격한 배당 변화

        전문가들이 대량으로 베팅하면 북메이커가 급히 배당을 조정
        """
        if len(odds) < 3:
            return {"detected": False}

        # 최근 10분 데이터만 분석
        recent = odds[-5:]  # 최근 5개 스냅샷

        for outcome in ["home", "away", "draw"]:
            odds_key = f"{outcome}_odds"

            # 배당 변화율 계산
            first_odds = recent[0][odds_key]
            last_odds = recent[-1][odds_key]
            pct_change = abs((last_odds - first_odds) / first_odds * 100)

            # 시간 차이 계산
            time_diff = recent[-1]["timestamp"] - recent[0]["timestamp"]
            minutes = time_diff.total_seconds() / 60

            # Steam Move 조건: 10분 내 5% 이상 변화
            if pct_change >= 5 and minutes <= 10:
                direction = "down" if last_odds < first_odds else "up"
                return {
                    "detected": True,
                    "outcome": outcome,
                    "change_pct": round(pct_change, 2),
                    "minutes": round(minutes, 1),
                    "description": f"{outcome.upper()} odds moved {direction} {pct_change:.1f}% in {minutes:.0f}min",
                }

        return {"detected": False}

    def _detect_reverse_line_movement(self, odds: List[dict], volume: dict) -> dict:
        """
        Reverse Line Movement: 대중 베팅과 반대로 라인이 움직임

        예: 70%가 홈팀에 베팅했는데 홈 배당이 올라감
        → Sharp Money가 원정팀에 베팅 중!
        """
        for outcome in ["home", "away"]:
            # 대중 베팅 비율
            public_pct = volume.get(f"{outcome}_bets_pct", 50)

            # 배당 변화
            first_odds = odds[0][f"{outcome}_odds"]
            last_odds = odds[-1][f"{outcome}_odds"]
            odds_change = last_odds - first_odds

            # Reverse 조건 1: 높은 대중 지지 + 배당 상승
            if public_pct > 65 and odds_change > 0.10:
                return {
                    "detected": True,
                    "outcome": outcome,
                    "public_pct": public_pct,
                    "odds_change": odds_change,
                    "description": f"{public_pct:.0f}% public on {outcome.upper()} but odds RISING (sharp on opposite)",
                }

            # Reverse 조건 2: 낮은 대중 지지 + 배당 하락
            if public_pct < 35 and odds_change < -0.10:
                return {
                    "detected": True,
                    "outcome": outcome,
                    "public_pct": public_pct,
                    "odds_change": odds_change,
                    "description": f"Only {public_pct:.0f}% public on {outcome.upper()} but odds FALLING (sharp interest)",
                }

        return {"detected": False}

    def _detect_sharp_bookmaker_lead(self, odds: List[dict]) -> dict:
        """
        Sharp 북메이커가 먼저 움직이고 나머지가 따라가는 패턴

        Pinnacle이 먼저 배당을 바꾸면 다른 북메이커들이 뒤따름
        """
        # 북메이커별 배당 변화 타이밍 분석
        sharp_moves = []
        public_moves = []

        for i in range(1, len(odds)):
            current = odds[i]
            previous = odds[i - 1]

            # 각 북메이커의 움직임 기록
            for bookmaker in current.get("bookmakers", []):
                bm_name = bookmaker["name"]

                # 이전 스냅샷에서 같은 북메이커 찾기
                prev_bm = next(
                    (b for b in previous.get("bookmakers", []) if b["name"] == bm_name),
                    None,
                )

                if prev_bm:
                    # 배당 변화 확인
                    for outcome in ["home", "away"]:
                        current_odds = bookmaker.get(f"{outcome}_odds", 0)
                        prev_odds = prev_bm.get(f"{outcome}_odds", 0)

                        if abs(current_odds - prev_odds) > 0.05:
                            move_time = current["timestamp"]

                            if bm_name in self.sharp_bookmakers:
                                sharp_moves.append(
                                    {
                                        "time": move_time,
                                        "bookmaker": bm_name,
                                        "outcome": outcome,
                                    }
                                )
                            elif bm_name in self.public_bookmakers:
                                public_moves.append(
                                    {
                                        "time": move_time,
                                        "bookmaker": bm_name,
                                        "outcome": outcome,
                                    }
                                )

        # Sharp이 Public보다 평균적으로 먼저 움직였는지 확인
        if sharp_moves and public_moves:
            avg_sharp_time = np.mean([m["time"].timestamp() for m in sharp_moves])
            avg_public_time = np.mean([m["time"].timestamp() for m in public_moves])

            # Sharp이 평균 5분 이상 빠르게 움직임
            if avg_sharp_time < avg_public_time - 300:  # 300초 = 5분
                return {
                    "detected": True,
                    "time_diff_minutes": (avg_public_time - avg_sharp_time) / 60,
                    "description": f"Sharp books moved {(avg_public_time - avg_sharp_time) / 60:.0f}min before public",
                }

        return {"detected": False}

    def _detect_volume_spike(self, volume: dict) -> dict:
        """
        비정상적인 베팅 볼륨 증가 감지
        """
        avg_volume = volume.get("avg_volume_last_10_matches", 0)
        current_volume = volume.get("current_volume", 0)

        if current_volume > avg_volume * 2.5:  # 평균의 2.5배
            spike_pct = (current_volume - avg_volume) / avg_volume * 100
            return {
                "detected": True,
                "spike_pct": round(spike_pct, 1),
                "description": f"Volume spike: {spike_pct:.0f}% above average",
            }

        return {"detected": False}

    def _determine_direction(self, odds: List[dict]) -> str:
        """
        Sharp Money가 어느 쪽에 베팅 중인지 판단
        가장 큰 배당 하락 = Sharp Money 방향
        """
        first = odds[0]
        last = odds[-1]

        changes = {
            "home": (first["home_odds"] - last["home_odds"]) / first["home_odds"],
            "away": (first["away_odds"] - last["away_odds"]) / first["away_odds"],
            "draw": (first["draw_odds"] - last["draw_odds"]) / first["draw_odds"],
        }

        # 가장 큰 하락폭 = Sharp Money 방향
        return max(changes, key=changes.get)

    def _calculate_odds_movement(self, odds: List[dict]) -> Dict[str, float]:
        """배당 변화량 계산"""
        first = odds[0]
        last = odds[-1]

        return {
            "home_change": last["home_odds"] - first["home_odds"],
            "home_change_pct": (
                (last["home_odds"] - first["home_odds"]) / first["home_odds"] * 100
            ),
            "away_change": last["away_odds"] - first["away_odds"],
            "away_change_pct": (
                (last["away_odds"] - first["away_odds"]) / first["away_odds"] * 100
            ),
            "draw_change": last["draw_odds"] - first["draw_odds"],
            "draw_change_pct": (
                (last["draw_odds"] - first["draw_odds"]) / first["draw_odds"] * 100
            ),
        }

    async def get_all_sharp_signals_today(self) -> List[SharpSignal]:
        """
        오늘의 모든 Sharp Signal 조회
        """
        # DB에서 오늘의 경기들 가져오기
        today_matches = await self._get_today_matches()

        signals = []
        for match in today_matches:
            # 각 경기의 배당 히스토리 가져오기
            odds_history = await self._get_odds_history(match["id"])
            volume_data = await self._get_betting_volume(match["id"])

            # Sharp Signal 감지
            signal = await self.detect_sharp_action(
                match_id=match["id"],
                historical_odds=odds_history,
                betting_volume=volume_data,
            )

            if signal:
                signals.append(signal)

        # 신호 강도 순으로 정렬
        signals.sort(key=lambda x: x.signal_strength, reverse=True)

        return signals

    # ... (existing code) ...

    async def _get_today_matches(self):
        """오늘 경기 조회"""
        now = datetime.utcnow()
        # 24시간 이내 경기
        stmt = select(Match).where(
            Match.start_time >= now, Match.start_time <= now + timedelta(hours=24)
        )
        result = await self.db.execute(stmt)
        if result is None:
            return []
        matches = result.scalars().all()
        return [{"id": m.id} for m in matches]

    async def _get_odds_history(self, match_id: int):
        """배당 히스토리 조회"""
        stmt = (
            select(OddsHistory)
            .where(OddsHistory.match_id == match_id)
            .order_by(OddsHistory.captured_at.asc())
        )
        result = await self.db.execute(stmt)
        history = result.scalars().all()

        # Convert to list of dicts
        return [
            {
                "timestamp": h.captured_at,
                "home_odds": h.odds_home,
                "draw_odds": h.odds_draw,
                "away_odds": h.odds_away,
                "bookmakers": h.payload.get("bookmakers", []) if h.payload else [],
            }
            for h in history
        ]

    async def _get_betting_volume(self, match_id: int):
        """베팅 볼륨 조회"""
        # 현재는 데이터 소스가 없으므로 None 반환
        return None
