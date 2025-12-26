"""
프로토 분석 비용 최적화 서비스

프로토 추첨 일정에 맞춰 AI 분석을 효율적으로 수행하여 비용 절감
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class AnalysisMode(Enum):
    """분석 모드"""
    FULL = "full"  # 최상위 모델로 전체 분석
    QUICK = "quick"  # 간단한 사전 분석
    CACHED = "cached"  # 캐시된 결과 사용


class ProtoSchedule:
    """프로토 추첨 일정 관리"""

    # 프로토 추첨일 (요일: 0=월요일, 5=토요일)
    DRAW_DAYS = {
        "승무패": [5],  # 토요일
        "승5패": [2, 5]  # 수요일, 토요일
    }

    @classmethod
    def get_next_draw_date(cls, game_type: str = "승무패") -> datetime:
        """다음 추첨일 조회"""
        now = datetime.now(timezone.utc)
        draw_days = cls.DRAW_DAYS.get(game_type, [5])

        # 다음 추첨일 찾기
        for i in range(7):
            future_date = now + timedelta(days=i)
            if future_date.weekday() in draw_days:
                # 추첨일 오후 8시로 설정
                return future_date.replace(hour=20, minute=0, second=0, microsecond=0)

        return now  # fallback

    @classmethod
    def days_until_draw(cls, game_type: str = "승무패") -> int:
        """추첨일까지 남은 일수"""
        now = datetime.now(timezone.utc)
        next_draw = cls.get_next_draw_date(game_type)
        delta = next_draw - now
        return delta.days

    @classmethod
    def should_analyze_now(cls, game_type: str = "승무패") -> bool:
        """현재 분석을 수행해야 하는지 판단

        추첨일 2일 전부터 분석 시작
        """
        days_left = cls.days_until_draw(game_type)
        return days_left <= 2


class CostOptimizer:
    """비용 최적화 전략"""

    def __init__(self):
        self.analysis_cache: Dict[str, dict] = {}  # round_id -> result
        self.analysis_timestamps: Dict[str, datetime] = {}

    def get_recommended_mode(
        self,
        round_id: str,
        game_type: str = "승무패",
        force_full: bool = False
    ) -> AnalysisMode:
        """권장 분석 모드 결정

        Args:
            round_id: 회차 ID
            game_type: 게임 타입
            force_full: 강제로 전체 분석 수행

        Returns:
            권장되는 분석 모드
        """
        if force_full:
            return AnalysisMode.FULL

        # 캐시 확인
        if round_id in self.analysis_cache:
            cached_time = self.analysis_timestamps.get(round_id)
            if cached_time:
                age_hours = (datetime.now(timezone.utc) - cached_time).total_seconds() / 3600
                # 6시간 이내 캐시는 재사용
                if age_hours < 6:
                    logger.info(f"Using cached analysis for {round_id} (age: {age_hours:.1f}h)")
                    return AnalysisMode.CACHED

        # 추첨일까지 남은 시간에 따라 결정
        days_left = ProtoSchedule.days_until_draw(game_type)

        if days_left > 2:
            logger.info(f"Draw is {days_left} days away - skipping analysis")
            return AnalysisMode.QUICK
        elif days_left == 2:
            logger.info(f"Draw is 2 days away - quick analysis mode")
            return AnalysisMode.QUICK
        else:  # 1일 전 또는 당일
            logger.info(f"Draw is {days_left} days away - full analysis mode")
            return AnalysisMode.FULL

    def cache_result(self, round_id: str, result: dict):
        """분석 결과 캐싱"""
        self.analysis_cache[round_id] = result
        self.analysis_timestamps[round_id] = datetime.now(timezone.utc)
        logger.info(f"Cached analysis for {round_id}")

    def get_cached_result(self, round_id: str) -> Optional[dict]:
        """캐시된 결과 조회"""
        return self.analysis_cache.get(round_id)

    def clear_old_cache(self, max_age_hours: int = 24):
        """오래된 캐시 정리"""
        now = datetime.now(timezone.utc)
        to_remove = []

        for round_id, timestamp in self.analysis_timestamps.items():
            age_hours = (now - timestamp).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_remove.append(round_id)

        for round_id in to_remove:
            del self.analysis_cache[round_id]
            del self.analysis_timestamps[round_id]
            logger.info(f"Removed old cache for {round_id}")

    def get_model_config(self, mode: AnalysisMode) -> Dict[str, any]:
        """분석 모드에 따른 AI 모델 설정

        Gemini 크레딧 활용 전략:
        - FULL 모드: Gemini를 데이터 수집/분석 기반으로 활용
        - QUICK 모드: Gemini로 빠른 사전 분석
        - 비용 부담 없이 대량 데이터 처리 가능

        Returns:
            model_config: {
                'primary': 주 분석 모델,
                'secondary': 보조 모델,
                'data_collector': 데이터 수집 모델,
                'iterations': 반복 횟수
            }
        """
        if mode == AnalysisMode.FULL:
            # 최상위 모델로 심층 분석 + Gemini로 데이터 수집
            return {
                'data_collector': 'gemini-pro',  # 💎 데이터 수집 전담 (크레딧 활용)
                'primary': 'o3',  # OpenAI o3 (최고 성능)
                'secondary': 'kimi-k2-thinking',  # Kimi K2 (추론 특화)
                'tertiary': 'claude-sonnet',  # Claude Sonnet (균형)
                'iterations': 1,
                'consensus_weight': {
                    'gemini-pro': 0.15,  # 데이터 기반 분석
                    'o3': 0.35,
                    'kimi-k2-thinking': 0.35,
                    'claude-sonnet': 0.15
                },
                'use_gemini_for_data': True  # Gemini로 상세 데이터 수집
            }
        elif mode == AnalysisMode.QUICK:
            # 빠른 사전 분석 - Gemini 단독 사용
            return {
                'data_collector': 'gemini-pro',  # 💎 크레딧 활용
                'primary': 'gemini-pro',  # 빠르고 비용 무료
                'secondary': None,
                'tertiary': None,
                'iterations': 1,
                'consensus_weight': {
                    'gemini-pro': 1.0
                },
                'use_gemini_for_data': True  # 대량 데이터 수집 가능
            }
        else:  # CACHED
            return {
                'data_collector': None,
                'primary': None,
                'secondary': None,
                'tertiary': None,
                'iterations': 0,
                'consensus_weight': {},
                'use_gemini_for_data': False
            }

    def estimate_cost(self, mode: AnalysisMode, num_matches: int = 14) -> Dict[str, float]:
        """예상 비용 계산

        Args:
            mode: 분석 모드
            num_matches: 경기 수

        Returns:
            비용 정보 딕셔너리
        """
        # 모델별 대략적인 비용 (1000 토큰당 USD)
        COSTS = {
            'o3': 0.06,  # 고비용
            'kimi-k2-thinking': 0.03,  # 중간
            'claude-sonnet': 0.015,  # 중간
            'claude-haiku': 0.00025,  # 매우 저렴
            'gemini-pro': 0.0,  # 💎 크레딧으로 무료 (140만원)
        }

        # 경기당 평균 토큰 사용량 (입력 + 출력)
        AVG_TOKENS_PER_MATCH = 3000

        config = self.get_model_config(mode)
        total_cost = 0.0
        breakdown = {}

        if mode == AnalysisMode.CACHED:
            return {'total': 0.0, 'breakdown': {}, 'savings': '100%', 'gemini_note': 'Using cache'}

        # 모든 모델 비용 계산 (data_collector 포함)
        for model_key in ['data_collector', 'primary', 'secondary', 'tertiary']:
            model = config.get(model_key)
            if model and model in COSTS:
                cost_per_match = (AVG_TOKENS_PER_MATCH / 1000) * COSTS[model]
                total = cost_per_match * num_matches * config['iterations']
                if total > 0:  # 비용이 있는 경우만 breakdown에 추가
                    breakdown[model] = round(total, 4)
                total_cost += total

        # 전체 분석 대비 절감률 계산
        if mode == AnalysisMode.FULL:
            # FULL 모드는 기준이므로 절감률 0%
            savings_pct = 0
            gemini_note = f'💎 Gemini 사용 (140만원 크레딧)'
        else:
            # FULL 모드 비용을 직접 계산 (재귀 방지)
            full_config = self.get_model_config(AnalysisMode.FULL)
            full_cost = 0.0
            for model_key in ['data_collector', 'primary', 'secondary', 'tertiary']:
                model = full_config.get(model_key)
                if model and model in COSTS:
                    cost_per_match = (AVG_TOKENS_PER_MATCH / 1000) * COSTS[model]
                    full_cost += cost_per_match * num_matches * full_config['iterations']

            savings_pct = ((full_cost - total_cost) / full_cost * 100) if full_cost > 0 else 0

            if mode == AnalysisMode.QUICK:
                gemini_note = '💎 Gemini 단독 사용 (무료)'
            else:
                gemini_note = None

        result = {
            'total': round(total_cost, 4),
            'breakdown': breakdown,
            'savings': f"{savings_pct:.1f}%"
        }

        if gemini_note:
            result['gemini_note'] = gemini_note

        return result


# 전역 인스턴스
cost_optimizer = CostOptimizer()
