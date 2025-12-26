"""
AI Analysis Orchestrator

다중 AI 서비스를 관리하고 결과를 집계하는 중앙 서비스
- 병렬 AI 호출 (asyncio.gather)
- 결과 가중 평균 계산
- 신뢰도 및 컨센서스 산정
- 캐싱 및 에러 핸들링
"""

import asyncio
import logging
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .ai.base_analyzer import BaseAIAnalyzer
from .ai.gpt_analyzer import GPTAnalyzer
from .ai.kimi_analyzer import KimiAnalyzer
from .ai.claude_analyzer import ClaudeAnalyzer
from .ai.gemini_analyzer import GeminiAnalyzer
from .ai.deepseek_analyzer import DeepSeekAnalyzer
from .ai.models import (
    AIOpinion,
    AIAnalysisResult,
    ConsensusResult,
    MatchContext,
    WinnerType,
    ConfidenceLevel,
)

logger = logging.getLogger(__name__)


# AI 가중치 설정 (5개 AI 모델)
AI_WEIGHTS = {
    "gpt": 0.25,      # GPT-4o: OpenAI 주력 모델
    "claude": 0.25,   # Claude: Anthropic 논리적 추론
    "gemini": 0.20,   # Gemini: Google 빠른 분석
    "deepseek": 0.15, # DeepSeek: 심층 분석
    "kimi": 0.15,     # Kimi: 보조 분석
}


class AIOrchestrator:
    """
    다중 AI 분석 오케스트레이터

    여러 AI 서비스를 병렬로 호출하고 결과를 종합하여
    신뢰도 높은 컨센서스 결과를 생성
    """

    def __init__(self):
        self.analyzers: Dict[str, BaseAIAnalyzer] = {}
        self.cache: Dict[str, AIAnalysisResult] = {}  # 메모리 캐시 (실제로는 Redis 권장)
        self.cache_ttl = 3600  # 1시간 캐시

        self._init_analyzers()

    def _init_analyzers(self):
        """분석기 초기화 (5개 AI 모델)"""
        # 모든 AI 분석기 인스턴스 생성
        analyzers_config = [
            ("gpt", GPTAnalyzer(), "GPT-4o"),
            ("claude", ClaudeAnalyzer(), "Claude Sonnet"),
            ("gemini", GeminiAnalyzer(), "Gemini 1.5 Flash"),
            ("deepseek", DeepSeekAnalyzer(), "DeepSeek V3"),
            ("kimi", KimiAnalyzer(), "Kimi K2"),
        ]

        for name, analyzer, display_name in analyzers_config:
            if analyzer.is_available():
                self.analyzers[name] = analyzer
                logger.info(f"[Orchestrator] {display_name} Analyzer 활성화")
            else:
                logger.warning(f"[Orchestrator] {display_name} Analyzer 비활성 - API 키 없음")

        active_count = len(self.analyzers)
        if active_count == 0:
            logger.error("[Orchestrator] 활성화된 AI 분석기가 없습니다!")
        else:
            logger.info(f"[Orchestrator] 총 {active_count}개 AI 분석기 활성화")

    def get_active_analyzers(self) -> List[str]:
        """활성화된 분석기 목록"""
        return list(self.analyzers.keys())

    async def analyze_match(
        self,
        context: MatchContext,
        use_cache: bool = True,
    ) -> AIAnalysisResult:
        """
        단일 경기 분석

        Args:
            context: 경기 컨텍스트
            use_cache: 캐시 사용 여부

        Returns:
            AIAnalysisResult: 종합 분석 결과
        """
        start_time = time.time()
        cache_key = self._generate_cache_key(context)

        # 캐시 확인
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            cached.cached = True
            logger.info(f"[Orchestrator] 캐시 히트: match_id={context.match_id}")
            return cached

        # 병렬 AI 호출
        opinions = await self._call_all_analyzers(context)

        if not opinions:
            logger.error(f"[Orchestrator] 분석 실패: match_id={context.match_id}")
            return self._create_empty_result(context)

        # 컨센서스 계산
        consensus = self._calculate_consensus(opinions)

        # 결과 생성
        total_latency = int((time.time() - start_time) * 1000)
        result = AIAnalysisResult(
            match_id=context.match_id,
            consensus=consensus,
            ai_opinions=opinions,
            cached=False,
            cache_key=cache_key,
            total_latency_ms=total_latency,
        )

        # 캐시 저장
        if use_cache:
            self.cache[cache_key] = result

        logger.info(
            f"[Orchestrator] 분석 완료: match_id={context.match_id}, "
            f"consensus={consensus.winner.value}, "
            f"confidence={consensus.confidence}%, "
            f"latency={total_latency}ms"
        )

        return result

    async def analyze_batch(
        self,
        contexts: List[MatchContext],
        use_cache: bool = True,
        max_concurrent: int = 5,
    ) -> List[AIAnalysisResult]:
        """
        여러 경기 일괄 분석

        Args:
            contexts: 경기 컨텍스트 리스트
            use_cache: 캐시 사용 여부
            max_concurrent: 동시 처리 수

        Returns:
            List[AIAnalysisResult]: 분석 결과 리스트
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(ctx: MatchContext) -> AIAnalysisResult:
            async with semaphore:
                return await self.analyze_match(ctx, use_cache)

        tasks = [analyze_with_semaphore(ctx) for ctx in contexts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외 처리
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[Orchestrator] 배치 분석 오류: {result}")
                final_results.append(self._create_empty_result(contexts[i]))
            else:
                final_results.append(result)

        return final_results

    async def _call_all_analyzers(self, context: MatchContext) -> List[AIOpinion]:
        """모든 분석기 병렬 호출"""
        if not self.analyzers:
            return []

        tasks = {
            name: analyzer.analyze_match(context)
            for name, analyzer in self.analyzers.items()
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        opinions = []
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"[{name}] 분석 실패: {result}")
            elif result.confidence > 0:  # 유효한 결과만 포함
                opinions.append(result)
            else:
                logger.warning(f"[{name}] 분석 결과 무효 (confidence=0)")

        return opinions

    def _calculate_consensus(self, opinions: List[AIOpinion]) -> ConsensusResult:
        """
        다중 AI 의견 종합

        가중 평균 방식으로 확률 계산
        일치도에 따라 신뢰도 조정
        """
        if not opinions:
            return self._create_default_consensus()

        # 가중 확률 계산
        weighted_probs = {"home": 0.0, "draw": 0.0, "away": 0.0}
        total_weight = 0.0

        for opinion in opinions:
            weight = AI_WEIGHTS.get(opinion.provider, 0.5)
            confidence_factor = opinion.confidence / 100  # 신뢰도 반영

            if opinion.probabilities:
                for key in weighted_probs:
                    weighted_probs[key] += (
                        opinion.probabilities.get(key, 0.33) * weight * confidence_factor
                    )
                total_weight += weight * confidence_factor

        # 정규화
        if total_weight > 0:
            for key in weighted_probs:
                weighted_probs[key] /= total_weight

        # 승자 결정
        winner_key = max(weighted_probs, key=weighted_probs.get)
        winner_map = {"home": WinnerType.HOME, "draw": WinnerType.DRAW, "away": WinnerType.AWAY}
        winner = winner_map[winner_key]

        # 일치도 계산
        agreement_count = sum(1 for op in opinions if op.winner == winner)
        agreement_rate = agreement_count / len(opinions) if opinions else 0

        # 가중 신뢰도 계산
        weighted_confidence = 0.0
        weight_sum = 0.0
        for opinion in opinions:
            weight = AI_WEIGHTS.get(opinion.provider, 0.5)
            weighted_confidence += opinion.confidence * weight
            weight_sum += weight

        avg_confidence = int(weighted_confidence / weight_sum) if weight_sum > 0 else 50

        # 일치도에 따른 신뢰도 조정
        if agreement_rate == 1.0:  # 만장일치
            adjusted_confidence = min(avg_confidence + 10, 100)
        elif agreement_rate >= 0.5:  # 과반수 일치
            adjusted_confidence = avg_confidence
        else:  # 분산
            adjusted_confidence = max(avg_confidence - 10, 30)

        # 신뢰도 수준 결정
        if adjusted_confidence >= 80:
            confidence_level = ConfidenceLevel.HIGH
        elif adjusted_confidence >= 60:
            confidence_level = ConfidenceLevel.MEDIUM
        elif adjusted_confidence >= 40:
            confidence_level = ConfidenceLevel.LOW
        else:
            confidence_level = ConfidenceLevel.UNCERTAIN

        # 추천 메시지 생성
        recommendation = self._generate_recommendation(winner, adjusted_confidence, agreement_rate)

        return ConsensusResult(
            winner=winner,
            confidence=adjusted_confidence,
            confidence_level=confidence_level,
            probabilities=weighted_probs,
            agreement_rate=agreement_rate,
            recommendation=recommendation,
        )

    def _generate_recommendation(
        self, winner: WinnerType, confidence: int, agreement_rate: float
    ) -> str:
        """추천 메시지 생성"""
        winner_korean = {"Home": "홈 승리", "Draw": "무승부", "Away": "원정 승리"}
        winner_text = winner_korean.get(winner.value, "무승부")

        if agreement_rate == 1.0 and confidence >= 70:
            return f"🔥 강력 추천: {winner_text} (AI 만장일치, 신뢰도 {confidence}%)"
        elif agreement_rate >= 0.5 and confidence >= 60:
            return f"✅ 추천: {winner_text} (신뢰도 {confidence}%)"
        elif confidence >= 50:
            return f"⚠️ 참고: {winner_text} 예상 (신뢰도 {confidence}%)"
        else:
            return f"❓ 불확실: {winner_text} 약세 예상 (신뢰도 낮음)"

    def _generate_cache_key(self, context: MatchContext) -> str:
        """캐시 키 생성"""
        key_data = f"{context.match_id}_{context.home_team}_{context.away_team}_{datetime.now().strftime('%Y%m%d')}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _create_default_consensus(self) -> ConsensusResult:
        """기본 컨센서스 생성"""
        return ConsensusResult(
            winner=WinnerType.DRAW,
            confidence=0,
            confidence_level=ConfidenceLevel.UNCERTAIN,
            probabilities={"home": 0.33, "draw": 0.34, "away": 0.33},
            agreement_rate=0,
            recommendation="분석 불가",
        )

    def _create_empty_result(self, context: MatchContext) -> AIAnalysisResult:
        """빈 결과 생성"""
        return AIAnalysisResult(
            match_id=context.match_id,
            consensus=self._create_default_consensus(),
            ai_opinions=[],
            cached=False,
        )

    def clear_cache(self):
        """캐시 초기화"""
        self.cache.clear()
        logger.info("[Orchestrator] 캐시 초기화 완료")

    def get_cache_stats(self) -> Dict:
        """캐시 통계"""
        return {
            "size": len(self.cache),
            "keys": list(self.cache.keys())[:10],  # 최근 10개만
        }
