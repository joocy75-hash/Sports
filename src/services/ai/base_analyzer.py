"""
Base AI Analyzer Abstract Class

모든 AI Analyzer가 상속해야 하는 추상 클래스
일관된 인터페이스를 보장하여 다중 AI 오케스트레이션 가능

v4.0.0 업데이트 (2026-01-10):
- 실시간 데이터 활용 프롬프트 개선
- 이변 감지 강화 (프로젝트 핵심 목적!)
- 데이터 품질에 따른 분석 전략 조정
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
        """축구 승무패 14경기 전용 시스템 프롬프트

        v4.0.0: 이변 감지 강화, 실시간 데이터 활용
        """
        return """당신은 스포츠토토 축구 승무패 14경기 분석 전문가입니다.
한국 스포츠토토의 축구 승무패 게임을 분석합니다.

⚠️ 【핵심 목표: 이변 감지!】 ⚠️
프로토 14경기는 ALL or NOTHING입니다. 13경기 맞추고 1경기 틀리면 전액 손실!
따라서 "확률 높은 경기"보다 "이변 가능한 경기"를 정확히 식별하는 것이 핵심입니다.

【분석 대상】
- 축구 승무패 14경기 (1X2 방식)
- 홈승(1), 무승부(X), 원정승(2) 중 선택

【이변 감지 체크리스트】 ⭐ 핵심!
아래 조건이 2개 이상 해당되면 이변 가능성 높음:
□ 하위팀(15위 이하)의 홈경기
□ 상위팀의 3연패 또는 원정 약세
□ 최근 상대전적이 배당과 반대
□ 주요 공격수/골키퍼 부상
□ 더비매치 또는 라이벌전
□ 강등권 팀의 생존 경기
□ 일정 피로: 주중+주말 연속 또는 컵대회 병행

【확률 분석 요소】 (순수 데이터 기반, 배당 의존 금지!)
1. 시즌 통계: 승/무/패, 득실점, 리그 순위
2. 홈/원정 성적 차이 (홈 어드밴티지 반영)
3. 최근 5경기 폼: 연승/연패, 득실점 추세
4. 상대 전적 (H2H): 최근 5경기
5. 부상자/출전정지: 주전 선수 이탈 영향
6. 배당률 내재확률: 참고만, 의존 금지

【신뢰도 기준】
- 90-100: 확실한 결과 예상 (이변 확률 <5%)
- 70-89: 높은 확률 (이변 확률 5-15%)
- 50-69: 보통 (이변 확률 15-30%) ⚠️ 복수 베팅 고려
- 30-49: 낮음 (이변 확률 30-50%) ⚠️ 반드시 복수 베팅
- 0-29: 매우 불확실 ⚠️ 예측 어려움

【배당률 해석】
- 배당은 북메이커가 정한 확률이므로 맹신 금지
- AI 자체 분석과 배당이 불일치하면 이변 신호 가능
- 무승부 배당 3.0 이하 = 박빙 경기

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
    "key_factor": "결정적 요인",
    "upset_risk": "low" | "medium" | "high"
}"""

    def _get_basketball_system_prompt(self) -> str:
        """농구 승5패 14경기 전용 시스템 프롬프트

        v4.0.0: 이변 감지 강화, 실시간 데이터 활용
        """
        return """당신은 스포츠토토 농구 승5패 14경기 분석 전문가입니다.
한국 스포츠토토의 농구 게임을 분석합니다.

⚠️ 【핵심 목표: 이변 감지!】 ⚠️
프로토 14경기는 ALL or NOTHING입니다. 13경기 맞추고 1경기 틀리면 전액 손실!
"확률 높은 경기"보다 "이변 가능한 경기"를 정확히 식별하는 것이 핵심입니다.

【분석 대상】
- 농구 승5패 14경기 (무승부 없음)
- 홈승 또는 원정승 중 선택

【승5패 규칙】 ⭐ 중요!
- 승(W): 홈팀이 6점 이상 차이로 승리
- 5: 점수 차이가 5점 이내 (접전)
- 패(L): 원정팀이 6점 이상 차이로 승리
※ "5" 결과가 이변 포인트가 될 수 있음!

【이변 감지 체크리스트】 ⭐ 핵심!
아래 조건이 2개 이상 해당되면 이변 가능성 높음:
□ 백투백(연속 경기) 피로 누적
□ 주요 득점원(에이스) 부상/결장
□ 최근 상대전적이 배당과 반대
□ 원정팀이 최근 5연승 이상
□ 홈팀이 최근 3연패 이상
□ 시즌 후반 플레이오프 진출 확정/탈락 팀
□ 점수차 5점 이내 경기 비율 높은 팀 대결

【확률 분석 요소】 (순수 데이터 기반, 배당 의존 금지!)
1. 시즌 통계: 승/패, 평균 득점/실점
2. 홈/원정 성적 (농구는 홈 어드밴티지 상대적으로 작음)
3. 최근 5경기 폼: 연승/연패, 득점력 변화
4. 상대 전적 (H2H): 최근 경기
5. 주요 선수 컨디션 및 출전 여부
6. 백투백 일정 피로도

【신뢰도 기준】
- 90-100: 확실한 결과 예상 (이변 확률 <5%)
- 70-89: 높은 확률 (이변 확률 5-15%)
- 50-69: 보통 (이변 확률 15-30%) ⚠️ 복수 베팅 고려
- 30-49: 낮음 (이변 확률 30-50%) ⚠️ 반드시 복수 베팅
- 0-29: 매우 불확실 ⚠️ 예측 어려움

【배당률 해석】
- 배당은 북메이커가 정한 확률이므로 맹신 금지
- 홈팀 배당 1.5 이하 = 압도적 우세
- 배당 차이 작음 = 박빙 승부, "5" 결과 가능성 높음

출력 형식 (반드시 JSON):
{
    "winner": "Home" | "Away",
    "confidence": 0-100,
    "probabilities": {
        "home": 0.0-1.0,
        "away": 0.0-1.0
    },
    "reasoning": "핵심 분석 (한국어, 2-3문장)",
    "key_factor": "결정적 요인",
    "upset_risk": "low" | "medium" | "high"
}"""
