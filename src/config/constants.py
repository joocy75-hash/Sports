"""
스포츠 분석 시스템 상수 정의

이 파일은 시스템 전반에 걸쳐 사용되는 상수들을 중앙화하여 관리합니다.
수정 시 CLAUDE.md의 이변 감지 로직 설명도 함께 업데이트해야 합니다.

사용법:
    from src.config.constants import UpsetDetectionConstants, SystemConstants
    
    if prob_gap < UpsetDetectionConstants.PROB_GAP_VERY_HIGH:
        upset_score += UpsetDetectionConstants.SCORE_VERY_HIGH
"""

from typing import Final, Set


class UpsetDetectionConstants:
    """
    이변 감지 로직에서 사용하는 상수들
    
    핵심 원칙:
    - 프로토 14경기는 ALL or NOTHING → 이변 감지가 핵심
    - AI 간 불일치 = 이변 신호 (오류가 아님!)
    - 확률 분포가 애매할수록 이변 가능성 높음
    """
    
    # ==================== 확률 갭 임계값 ====================
    # 1위-2위 확률 차이 (prob_gap = probs[0] - probs[1])
    # 값이 작을수록 애매한 경기 = 이변 가능성 높음
    PROB_GAP_VERY_HIGH: Final[float] = 0.10  # 매우 애매함 (1위-2위 10% 이내)
    PROB_GAP_HIGH: Final[float] = 0.15       # 애매함
    PROB_GAP_MEDIUM: Final[float] = 0.20     # 보통
    PROB_GAP_LOW: Final[float] = 0.25        # 명확한 편
    PROB_GAP_VERY_LOW: Final[float] = 0.30   # 명확함
    
    # ==================== 확률 갭별 이변 점수 ====================
    PROB_GAP_SCORE_VERY_HIGH: Final[int] = 50  # prob_gap < 0.10
    PROB_GAP_SCORE_HIGH: Final[int] = 40       # prob_gap < 0.15
    PROB_GAP_SCORE_MEDIUM: Final[int] = 30     # prob_gap < 0.20
    PROB_GAP_SCORE_LOW: Final[int] = 20        # prob_gap < 0.25
    PROB_GAP_SCORE_VERY_LOW: Final[int] = 10   # prob_gap < 0.30
    
    # ==================== AI 신뢰도 임계값 ====================
    # AI가 반환하는 confidence 값 (0.0 ~ 1.0)
    # 낮을수록 AI도 확신하지 못함 = 이변 가능성 높음
    CONFIDENCE_VERY_LOW: Final[float] = 0.40
    CONFIDENCE_LOW: Final[float] = 0.45
    CONFIDENCE_MEDIUM: Final[float] = 0.50
    CONFIDENCE_HIGH: Final[float] = 0.55
    
    # ==================== 신뢰도별 이변 점수 ====================
    CONFIDENCE_SCORE_VERY_LOW: Final[int] = 40  # confidence < 0.40
    CONFIDENCE_SCORE_LOW: Final[int] = 30       # confidence < 0.45
    CONFIDENCE_SCORE_MEDIUM: Final[int] = 20    # confidence < 0.50
    CONFIDENCE_SCORE_HIGH: Final[int] = 10      # confidence < 0.55
    
    # ==================== AI 일치도 임계값 ====================
    # 5개 AI 모델 간 일치도 (0.0 ~ 1.0)
    # 낮을수록 AI들이 의견 불일치 = 이변 가능성 높음 (핵심!)
    AI_AGREEMENT_VERY_LOW: Final[float] = 0.40
    AI_AGREEMENT_LOW: Final[float] = 0.50
    AI_AGREEMENT_MEDIUM: Final[float] = 0.60
    AI_AGREEMENT_HIGH: Final[float] = 0.70
    
    # ==================== AI 일치도별 이변 점수 ====================
    AI_AGREEMENT_SCORE_VERY_LOW: Final[int] = 35  # agreement < 0.40
    AI_AGREEMENT_SCORE_LOW: Final[int] = 25       # agreement < 0.50
    AI_AGREEMENT_SCORE_MEDIUM: Final[int] = 15    # agreement < 0.60
    AI_AGREEMENT_SCORE_HIGH: Final[int] = 5       # agreement < 0.70
    
    # ==================== 무승부/5 확률 임계값 ====================
    # 무승부(축구) 또는 5점 이내(농구) 확률
    # 높을수록 접전 = 이변 가능성 높음
    DRAW_PROB_HIGH: Final[float] = 0.30
    DRAW_PROB_MEDIUM: Final[float] = 0.25
    DRAW_PROB_LOW: Final[float] = 0.20
    
    # ==================== 무승부/5 확률별 이변 점수 ====================
    DRAW_PROB_SCORE_HIGH: Final[int] = 25    # prob_draw >= 0.30
    DRAW_PROB_SCORE_MEDIUM: Final[int] = 15  # prob_draw >= 0.25
    DRAW_PROB_SCORE_LOW: Final[int] = 5      # prob_draw >= 0.20
    
    # ==================== 복수 베팅 설정 ====================
    DEFAULT_MULTI_GAMES: Final[int] = 4  # 기본 복수 베팅 경기 수


class AIModelWeights:
    """
    AI 모델별 가중치 설정
    
    총합이 1.0이 되어야 함
    모델 성능에 따라 주기적으로 조정 필요
    """
    GPT: Final[float] = 0.25      # GPT-4o: OpenAI 주력 모델
    CLAUDE: Final[float] = 0.25   # Claude: Anthropic 논리적 추론
    GEMINI: Final[float] = 0.20   # Gemini: Google 빠른 분석
    DEEPSEEK: Final[float] = 0.15 # DeepSeek: 심층 분석
    KIMI: Final[float] = 0.15     # Kimi: 보조 분석
    
    @classmethod
    def get_weights_dict(cls) -> dict:
        """가중치 딕셔너리 반환 (ai_orchestrator.py 호환)"""
        return {
            "gpt": cls.GPT,
            "claude": cls.CLAUDE,
            "gemini": cls.GEMINI,
            "deepseek": cls.DEEPSEEK,
            "kimi": cls.KIMI,
        }


class SystemConstants:
    """시스템 전반에 사용되는 상수들"""
    
    # ==================== 캐시 설정 (초) ====================
    CACHE_TTL_SHORT: Final[int] = 300    # 5분 - 실시간 데이터
    CACHE_TTL_MEDIUM: Final[int] = 1800  # 30분 - 경기 정보
    CACHE_TTL_LONG: Final[int] = 3600    # 1시간 - AI 분석 결과
    
    # ==================== 경기 수 제한 ====================
    MAX_GAMES_PER_ROUND: Final[int] = 14  # 프로토 14경기 고정 (치명적!)
    
    # ==================== API 타임아웃 (초) ====================
    API_TIMEOUT_SHORT: Final[int] = 10   # 간단한 API 호출
    API_TIMEOUT_MEDIUM: Final[int] = 30  # AI 분석
    API_TIMEOUT_LONG: Final[int] = 60    # 크롤러
    
    # ==================== 스케줄러 설정 (시간) ====================
    SCHEDULER_INTERVAL_DEFAULT: Final[int] = 6  # 기본 스케줄러 간격
    
    # ==================== 회차 계산 기준 ====================
    # 축구 승무패 회차 계산 기준 (주기적 업데이트 필요)
    SOCCER_BASE_DATE: Final[str] = "2025-12-27"
    SOCCER_BASE_ROUND: Final[int] = 84
    
    # 농구 승5패 회차 계산 기준
    BASKETBALL_BASE_DATE: Final[str] = "2024-10-19"
    BASKETBALL_BASE_ROUND: Final[int] = 1


class GameTypeConstants:
    """게임 타입 관련 상수들"""
    
    SOCCER_WDL: Final[str] = "soccer_wdl"
    BASKETBALL_W5L: Final[str] = "basketball_w5l"
    
    VALID_GAME_TYPES: Final[Set[str]] = {SOCCER_WDL, BASKETBALL_W5L}
    
    # 축구 결과 코드
    SOCCER_HOME: Final[str] = "1"
    SOCCER_DRAW: Final[str] = "X"
    SOCCER_AWAY: Final[str] = "2"
    
    # 농구 결과 코드
    BASKETBALL_WIN: Final[str] = "승"
    BASKETBALL_CLOSE: Final[str] = "5"
    BASKETBALL_LOSE: Final[str] = "패"


class TelegramConstants:
    """텔레그램 알림 관련 상수들"""
    
    # 신뢰도 표시 아이콘
    ICON_HIGH_CONFIDENCE: Final[str] = "🔒"
    ICON_MEDIUM_CONFIDENCE: Final[str] = "📊"
    ICON_MULTI_BET: Final[str] = "⚠️"
    
    # 결과 아이콘
    ICON_CORRECT: Final[str] = "✅"
    ICON_WRONG: Final[str] = "❌"
    ICON_MULTI_CORRECT: Final[str] = "🔵"
    
    # 게임 아이콘
    ICON_SOCCER: Final[str] = "⚽"
    ICON_BASKETBALL: Final[str] = "🏀"
    
    # 신뢰도 임계값 (텔레그램 표시용)
    HIGH_CONFIDENCE_THRESHOLD_SOCCER: Final[float] = 0.55
    HIGH_CONFIDENCE_THRESHOLD_BASKETBALL: Final[float] = 0.50
