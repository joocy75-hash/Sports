"""
Base AI Analyzer Abstract Class

모든 AI Analyzer가 상속해야 하는 추상 클래스
일관된 인터페이스를 보장하여 다중 AI 오케스트레이션 가능
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import logging
import time

from .models import AIOpinion, MatchContext, WinnerType, SportType

logger = logging.getLogger(__name__)


class BaseAIAnalyzer(ABC):
    """
    AI Analyzer 추상 클래스

    모든 AI 서비스 (GPT, Kimi 등)는 이 클래스를 상속하여
    동일한 인터페이스로 분석 결과를 제공해야 함.
    """

    # 하위 클래스에서 오버라이드
    provider_name: str = "base"
    default_weight: float = 0.5

    def __init__(self):
        self._last_latency_ms: Optional[int] = None

    @abstractmethod
    async def analyze_match(self, context: MatchContext) -> AIOpinion:
        """
        단일 경기 분석

        Args:
            context: 경기 정보 및 통계 컨텍스트

        Returns:
            AIOpinion: AI의 분석 의견
        """
        pass

    async def analyze_batch(self, contexts: List[MatchContext]) -> List[AIOpinion]:
        """
        여러 경기 일괄 분석

        기본 구현: 순차 분석 (하위 클래스에서 병렬 처리 가능)

        Args:
            contexts: 경기 컨텍스트 리스트

        Returns:
            List[AIOpinion]: 분석 의견 리스트
        """
        results = []
        for ctx in contexts:
            try:
                result = await self.analyze_match(ctx)
                results.append(result)
            except Exception as e:
                logger.error(f"[{self.provider_name}] 배치 분석 오류 (match_id={ctx.match_id}): {e}")
                results.append(self._create_error_opinion(ctx, str(e)))
        return results

    def _create_error_opinion(self, context: MatchContext, error_msg: str) -> AIOpinion:
        """에러 발생 시 기본 응답 생성"""
        return AIOpinion(
            provider=self.provider_name,
            winner=WinnerType.DRAW,  # 불확실할 때 무승부
            confidence=0,
            reasoning=f"분석 오류: {error_msg}",
            key_factor="오류",
            probabilities={"home": 0.33, "draw": 0.34, "away": 0.33},
        )

    def _create_unavailable_opinion(self, context: MatchContext, reason: str) -> AIOpinion:
        """서비스 불가 시 기본 응답 생성"""
        return AIOpinion(
            provider=self.provider_name,
            winner=WinnerType.DRAW,
            confidence=0,
            reasoning=reason,
            key_factor="서비스 불가",
            probabilities={"home": 0.33, "draw": 0.34, "away": 0.33},
        )

    def _parse_winner(self, winner_str: str) -> WinnerType:
        """문자열을 WinnerType으로 변환"""
        winner_map = {
            "home": WinnerType.HOME,
            "홈": WinnerType.HOME,
            "승": WinnerType.HOME,
            "1": WinnerType.HOME,
            "draw": WinnerType.DRAW,
            "무": WinnerType.DRAW,
            "무승부": WinnerType.DRAW,
            "x": WinnerType.DRAW,
            "away": WinnerType.AWAY,
            "원정": WinnerType.AWAY,
            "패": WinnerType.AWAY,
            "2": WinnerType.AWAY,
        }
        return winner_map.get(winner_str.lower(), WinnerType.DRAW)

    def _measure_latency(self, start_time: float) -> int:
        """지연 시간 측정 (밀리초)"""
        self._last_latency_ms = int((time.time() - start_time) * 1000)
        return self._last_latency_ms

    @property
    def last_latency_ms(self) -> Optional[int]:
        """마지막 호출의 지연 시간"""
        return self._last_latency_ms

    def is_available(self) -> bool:
        """
        서비스 가용성 확인

        하위 클래스에서 API 키 존재 여부 등을 체크
        """
        return True

    def _get_sport_system_prompt(self, sport_type: SportType) -> str:
        """스포츠 타입별 시스템 프롬프트 반환"""
        if sport_type == SportType.BASKETBALL:
            return self._get_basketball_system_prompt()
        else:
            return self._get_soccer_system_prompt()

    def _get_soccer_system_prompt(self) -> str:
        """축구 승무패 14경기 전용 시스템 프롬프트"""
        return """당신은 스포츠토토 축구 승무패 14경기 분석 전문가입니다.
한국 스포츠토토의 축구 승무패 게임을 분석합니다.

【분석 대상】
- 축구 승무패 14경기 (1X2 방식)
- 홈승(1), 무승부(X), 원정승(2) 중 선택

【핵심 분석 요소】
1. 홈/원정 경기력 차이 (홈 어드밴티지 중요)
2. 최근 5경기 폼 및 득실점 추세
3. 상대 전적 (H2H)
4. 주요 선수 부상/출전 정지
5. 리그 순위 및 시즌 목표 (강등권/우승권)
6. 경기 일정 피로도 (주중/주말, 컵대회 병행)

【배당률 해석】
- 낮은 배당 = 시장의 예상 우세팀
- 무승부 배당 3.0 이하 = 박빙 경기 가능성
- 이변 발생 패턴 주의 (하위팀 홈경기, 더비매치)

출력 형식 (반드시 JSON):
{
    "winner": "Home" | "Draw" | "Away",
    "confidence": 0-100,
    "probabilities": {
        "home": 0.0-1.0,
        "draw": 0.0-1.0,
        "away": 0.0-1.0
    },
    "reasoning": "핵심 분석 (한국어, 2-3문장)",
    "key_factor": "결정적 요인"
}"""

    def _get_basketball_system_prompt(self) -> str:
        """농구 승5패 14경기 전용 시스템 프롬프트"""
        return """당신은 스포츠토토 농구 승5패 14경기 분석 전문가입니다.
한국 스포츠토토의 농구 게임을 분석합니다.

【분석 대상】
- 농구 승5패 14경기 (무승부 없음)
- 홈승 또는 원정승 중 선택

【핵심 분석 요소】
1. 최근 5경기 승패 및 득점력
2. 홈/원정 경기력 차이 (농구는 홈 어드밴티지 상대적으로 작음)
3. 공격/수비 효율성 (평균 득점, 실점)
4. 주요 선수 컨디션 및 출전 여부
5. 백투백(연속경기) 피로도
6. 상대 전적 및 매치업

【농구 특성】
- 점수 차가 크게 벌어지는 경기 많음
- 쿼터별 흐름 중요
- 3점슛 성공률 변동성 큼
- 후반 역전 가능성 항상 존재

【배당률 해석】
- 홈팀 배당 1.5 이하 = 압도적 우세
- 배당 차이 작음 = 박빙 승부 예상
- 원정팀 낮은 배당 = 전력 차이 큼

출력 형식 (반드시 JSON):
{
    "winner": "Home" | "Away",
    "confidence": 0-100,
    "probabilities": {
        "home": 0.0-1.0,
        "away": 0.0-1.0
    },
    "reasoning": "핵심 분석 (한국어, 2-3문장)",
    "key_factor": "결정적 요인"
}"""
