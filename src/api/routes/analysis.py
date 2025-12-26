"""
AI Analysis API Router

다중 AI 분석 엔드포인트
- 단일 경기 분석
- 라운드 일괄 분석
- AI 상세 분석
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.services.ai_orchestrator import AIOrchestrator
from src.services.ai.models import MatchContext
from src.api.middleware.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["AI Analysis"])

# Rate Limiter 인스턴스
limiter = Limiter(key_func=get_remote_address)

# 전역 오케스트레이터 인스턴스
orchestrator = AIOrchestrator()


# ============================================================================
# Request/Response Models
# ============================================================================

class MatchAnalysisRequest(BaseModel):
    """경기 분석 요청"""
    match_id: int
    home_team: str
    away_team: str
    league: str
    start_time: str
    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None
    home_form: Optional[List[str]] = None
    away_form: Optional[List[str]] = None


class AIOpinionResponse(BaseModel):
    """AI 의견 응답"""
    provider: str
    winner: str
    confidence: int
    reasoning: str
    key_factor: Optional[str] = None
    probabilities: Optional[dict] = None
    latency_ms: Optional[int] = None


class ConsensusResponse(BaseModel):
    """컨센서스 응답"""
    winner: str
    confidence: int
    confidence_level: str
    probabilities: dict
    agreement_rate: float
    recommendation: str


class MatchAnalysisResponse(BaseModel):
    """경기 분석 응답"""
    match_id: int
    consensus: ConsensusResponse
    ai_opinions: List[AIOpinionResponse]
    analyzed_at: str
    cached: bool
    total_latency_ms: Optional[int] = None


class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str
    active_analyzers: List[str]
    cache_size: int


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    AI 분석 서비스 헬스 체크

    활성화된 분석기와 캐시 상태 확인
    """
    return HealthResponse(
        status="healthy",
        active_analyzers=orchestrator.get_active_analyzers(),
        cache_size=len(orchestrator.cache),
    )


@router.post("/match", response_model=MatchAnalysisResponse)
@limiter.limit("10/hour")
async def analyze_match(
    request: Request,
    data: MatchAnalysisRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    단일 경기 AI 분석

    다중 AI (o3 + Kimi-K2-Thinking)를 사용하여 경기 결과 예측

    Requires: Bearer token authentication
    Rate Limit: 10 requests per hour
    """
    try:
        # MatchContext 생성
        context = MatchContext(
            match_id=data.match_id,
            home_team=data.home_team,
            away_team=data.away_team,
            league=data.league,
            start_time=data.start_time,
            odds_home=data.odds_home,
            odds_draw=data.odds_draw,
            odds_away=data.odds_away,
            home_form=data.home_form,
            away_form=data.away_form,
        )

        # AI 분석 수행
        result = await orchestrator.analyze_match(context)

        # 응답 변환
        return MatchAnalysisResponse(
            match_id=result.match_id,
            consensus=ConsensusResponse(
                winner=result.consensus.winner.value,
                confidence=result.consensus.confidence,
                confidence_level=result.consensus.confidence_level.value,
                probabilities=result.consensus.probabilities,
                agreement_rate=result.consensus.agreement_rate,
                recommendation=result.consensus.recommendation,
            ),
            ai_opinions=[
                AIOpinionResponse(
                    provider=op.provider,
                    winner=op.winner.value,
                    confidence=op.confidence,
                    reasoning=op.reasoning,
                    key_factor=op.key_factor,
                    probabilities=op.probabilities,
                    latency_ms=op.latency_ms,
                )
                for op in result.ai_opinions
            ],
            analyzed_at=result.analyzed_at,
            cached=result.cached,
            total_latency_ms=result.total_latency_ms,
        )

    except Exception as e:
        logger.error(f"경기 분석 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/match/{match_id}", response_model=MatchAnalysisResponse)
async def get_match_analysis(
    match_id: int,
    home_team: str = Query(..., description="홈팀 이름"),
    away_team: str = Query(..., description="원정팀 이름"),
    league: str = Query(..., description="리그 이름"),
    start_time: str = Query(..., description="경기 시작 시간 (ISO 형식)"),
    odds_home: Optional[float] = Query(None, description="홈 배당률"),
    odds_draw: Optional[float] = Query(None, description="무승부 배당률"),
    odds_away: Optional[float] = Query(None, description="원정 배당률"),
):
    """
    경기 ID로 AI 분석 조회

    GET 방식으로 경기 정보를 전달하여 분석 수행
    """
    try:
        context = MatchContext(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            league=league,
            start_time=start_time,
            odds_home=odds_home,
            odds_draw=odds_draw,
            odds_away=odds_away,
        )

        result = await orchestrator.analyze_match(context)

        return MatchAnalysisResponse(
            match_id=result.match_id,
            consensus=ConsensusResponse(
                winner=result.consensus.winner.value,
                confidence=result.consensus.confidence,
                confidence_level=result.consensus.confidence_level.value,
                probabilities=result.consensus.probabilities,
                agreement_rate=result.consensus.agreement_rate,
                recommendation=result.consensus.recommendation,
            ),
            ai_opinions=[
                AIOpinionResponse(
                    provider=op.provider,
                    winner=op.winner.value,
                    confidence=op.confidence,
                    reasoning=op.reasoning,
                    key_factor=op.key_factor,
                    probabilities=op.probabilities,
                    latency_ms=op.latency_ms,
                )
                for op in result.ai_opinions
            ],
            analyzed_at=result.analyzed_at,
            cached=result.cached,
            total_latency_ms=result.total_latency_ms,
        )

    except Exception as e:
        logger.error(f"경기 분석 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
@limiter.limit("5/hour")
async def analyze_batch(
    request: Request,
    data: List[MatchAnalysisRequest],
    api_key: str = Depends(verify_api_key)
):
    """
    여러 경기 일괄 분석

    라운드 내 모든 경기를 한 번에 분석

    Requires: Bearer token authentication
    Rate Limit: 5 requests per hour
    """
    try:
        contexts = [
            MatchContext(
                match_id=req.match_id,
                home_team=req.home_team,
                away_team=req.away_team,
                league=req.league,
                start_time=req.start_time,
                odds_home=req.odds_home,
                odds_draw=req.odds_draw,
                odds_away=req.odds_away,
                home_form=req.home_form,
                away_form=req.away_form,
            )
            for req in data
        ]

        results = await orchestrator.analyze_batch(contexts)

        return {
            "success": True,
            "total": len(results),
            "analyses": [result.to_dict() for result in results],
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"배치 분석 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
async def clear_cache(api_key: str = Depends(verify_api_key)):
    """
    분석 캐시 초기화

    모든 캐시된 분석 결과 삭제

    Requires: Bearer token authentication
    """
    orchestrator.clear_cache()
    return {"success": True, "message": "캐시가 초기화되었습니다."}


@router.get("/cache/stats")
async def get_cache_stats():
    """
    캐시 통계 조회
    """
    return orchestrator.get_cache_stats()


# ============================================================================
# Proto 14-Match Analysis Endpoints
# ============================================================================

class ProtoMatchRequest(BaseModel):
    """프로토 단일 경기 정보"""
    match_id: str
    match_number: int
    home_team: str
    away_team: str
    league: str
    match_time: str
    home_form: Optional[List[str]] = None
    away_form: Optional[List[str]] = None
    home_rank: Optional[int] = None
    away_rank: Optional[int] = None


class ProtoRoundRequest(BaseModel):
    """프로토 회차 분석 요청"""
    round_id: str
    game_type: str = '승무패'  # '승무패' or '승5패'
    matches: List[ProtoMatchRequest]
    force_full_analysis: bool = False  # 강제 전체 분석 플래그


@router.post("/proto/round")
@limiter.limit("5/day")  # 3/day -> 5/day (캐싱으로 실제 비용은 더 낮음)
async def analyze_proto_round(
    http_request: Request,
    request: ProtoRoundRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    프로토 14경기 전체 분석 (비용 최적화 적용)

    공식 배당을 사용하지 않고 순수 AI 예측으로 확률 계산
    이변 가능성 높은 경기 4개 선정하여 복수 베팅 추천

    비용 절감 전략:
    - 추첨일 2일+ 전: 분석 스킵 (다음에 다시 요청 안내)
    - 추첨일 2일 전: 빠른 사전 분석 (저비용 모델)
    - 추첨일 1일 전~당일: 전체 심층 분석 (최상위 모델)
    - 6시간 내 동일 요청: 캐시 재사용 (비용 0)

    Requires: Bearer token authentication
    Rate Limit: 5 requests per day
    """
    try:
        from src.services.proto_analyzer import ProtoAnalyzer
        from src.services.proto_cost_optimizer import (
            cost_optimizer,
            ProtoSchedule,
            AnalysisMode
        )

        # 비용 최적화 모드 결정
        mode = cost_optimizer.get_recommended_mode(
            round_id=request.round_id,
            game_type=request.game_type,
            force_full=request.force_full_analysis
        )

        # 캐시된 결과 확인
        if mode == AnalysisMode.CACHED:
            cached_result = cost_optimizer.get_cached_result(request.round_id)
            if cached_result:
                logger.info(f"Returning cached result for {request.round_id}")
                return {
                    **cached_result,
                    "cached": True,
                    "cost_info": {
                        "mode": "cached",
                        "estimated_cost_usd": 0.0,
                        "savings": "100%"
                    }
                }

        # 추첨일까지 너무 많이 남은 경우
        days_left = ProtoSchedule.days_until_draw(request.game_type)
        if mode == AnalysisMode.QUICK and days_left > 2 and not request.force_full_analysis:
            next_draw = ProtoSchedule.get_next_draw_date(request.game_type)
            return {
                "message": f"추첨일이 {days_left}일 남았습니다. 분석은 추첨 2일 전부터 시작됩니다.",
                "next_draw_date": next_draw.isoformat(),
                "days_until_draw": days_left,
                "recommendation": "추첨 2일 전에 다시 요청해주세요. (force_full_analysis=true로 즉시 분석 가능)",
                "cost_info": cost_optimizer.estimate_cost(AnalysisMode.FULL, len(request.matches))
            }

        # 모델 설정 가져오기
        model_config = cost_optimizer.get_model_config(mode)

        analyzer = ProtoAnalyzer()

        # 각 경기에 대해 AI 분석 수행
        matches_data = []

        for match_req in request.matches:
            # MatchContext 생성
            context = MatchContext(
                match_id=int(match_req.match_id) if match_req.match_id.isdigit() else hash(match_req.match_id),
                home_team=match_req.home_team,
                away_team=match_req.away_team,
                league=match_req.league,
                start_time=match_req.match_time,
                home_form=match_req.home_form,
                away_form=match_req.away_form,
            )

            # AI 분석 수행
            ai_result = await orchestrator.analyze_match(context)

            # 모델별 예측 수집
            model_predictions = [
                {
                    'provider': op.provider,
                    'probabilities': op.probabilities if op.probabilities else {
                        'H': 0.33, 'D': 0.34, 'A': 0.33
                    }
                }
                for op in ai_result.ai_opinions
            ]

            # 팀 통계
            team_stats = {}
            if match_req.home_rank is not None or match_req.away_rank is not None:
                team_stats = {
                    'home': {'league_rank': match_req.home_rank} if match_req.home_rank else {},
                    'away': {'league_rank': match_req.away_rank} if match_req.away_rank else {}
                }

            # 최근 폼
            recent_form = {}
            if match_req.home_form or match_req.away_form:
                recent_form = {
                    'home': match_req.home_form or [],
                    'away': match_req.away_form or []
                }

            matches_data.append({
                'match_id': match_req.match_id,
                'match_number': match_req.match_number,
                'home_team': match_req.home_team,
                'away_team': match_req.away_team,
                'league': match_req.league,
                'match_time': match_req.match_time,
                'model_predictions': model_predictions,
                'team_stats': team_stats,
                'recent_form': recent_form
            })

        # 프로토 분석 수행
        result = analyzer.analyze_round(
            round_id=request.round_id,
            matches=matches_data,
            game_type=request.game_type
        )

        # 결과를 딕셔너리로 변환
        result_dict = analyzer.to_dict(result)

        # 비용 정보 추가
        cost_info = cost_optimizer.estimate_cost(mode, len(request.matches))
        result_dict['cost_info'] = {
            'mode': mode.value,
            'estimated_cost_usd': cost_info['total'],
            'breakdown': cost_info['breakdown'],
            'savings': cost_info['savings'],
            'days_until_draw': days_left,
            'model_config': model_config
        }
        result_dict['cached'] = False

        # 결과 캐싱
        cost_optimizer.cache_result(request.round_id, result_dict)

        # 오래된 캐시 정리
        cost_optimizer.clear_old_cache(max_age_hours=24)

        return result_dict

    except Exception as e:
        logger.error(f"프로토 회차 분석 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proto/round/text")
@limiter.limit("5/day")
async def analyze_proto_round_text(
    http_request: Request,
    request: ProtoRoundRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    프로토 14경기 분석 결과 (텍스트 포맷) - 비용 최적화 적용

    텔레그램 전송용 마킹 리스트 텍스트
    /proto/round와 동일한 비용 최적화 전략 적용

    Requires: Bearer token authentication
    Rate Limit: 5 requests per day
    """
    try:
        from src.services.proto_analyzer import ProtoAnalyzer
        from src.services.proto_cost_optimizer import (
            cost_optimizer,
            ProtoSchedule,
            AnalysisMode
        )

        # 비용 최적화 모드 결정
        mode = cost_optimizer.get_recommended_mode(
            round_id=request.round_id,
            game_type=request.game_type,
            force_full=request.force_full_analysis
        )

        # 캐시 확인
        if mode == AnalysisMode.CACHED:
            cached_result = cost_optimizer.get_cached_result(request.round_id)
            if cached_result and 'marking_text' in cached_result:
                logger.info(f"Returning cached text result for {request.round_id}")
                return {
                    "round_id": request.round_id,
                    "game_type": request.game_type,
                    "marking_text": cached_result['marking_text'],
                    "analyzed_at": cached_result.get('analyzed_at'),
                    "cached": True,
                    "cost_info": {
                        "mode": "cached",
                        "estimated_cost_usd": 0.0,
                        "savings": "100%"
                    }
                }

        # 추첨일 확인
        days_left = ProtoSchedule.days_until_draw(request.game_type)
        if mode == AnalysisMode.QUICK and days_left > 2 and not request.force_full_analysis:
            next_draw = ProtoSchedule.get_next_draw_date(request.game_type)
            return {
                "message": f"추첨일이 {days_left}일 남았습니다. 분석은 추첨 2일 전부터 시작됩니다.",
                "next_draw_date": next_draw.isoformat(),
                "days_until_draw": days_left,
                "recommendation": "추첨 2일 전에 다시 요청해주세요."
            }

        model_config = cost_optimizer.get_model_config(mode)

        analyzer = ProtoAnalyzer()

        # 각 경기 AI 분석
        matches_data = []

        for match_req in request.matches:
            context = MatchContext(
                match_id=int(match_req.match_id) if match_req.match_id.isdigit() else hash(match_req.match_id),
                home_team=match_req.home_team,
                away_team=match_req.away_team,
                league=match_req.league,
                start_time=match_req.match_time,
                home_form=match_req.home_form,
                away_form=match_req.away_form,
            )

            ai_result = await orchestrator.analyze_match(context)

            model_predictions = [
                {
                    'provider': op.provider,
                    'probabilities': op.probabilities if op.probabilities else {
                        'H': 0.33, 'D': 0.34, 'A': 0.33
                    }
                }
                for op in ai_result.ai_opinions
            ]

            team_stats = {}
            if match_req.home_rank is not None or match_req.away_rank is not None:
                team_stats = {
                    'home': {'league_rank': match_req.home_rank} if match_req.home_rank else {},
                    'away': {'league_rank': match_req.away_rank} if match_req.away_rank else {}
                }

            recent_form = {}
            if match_req.home_form or match_req.away_form:
                recent_form = {
                    'home': match_req.home_form or [],
                    'away': match_req.away_form or []
                }

            matches_data.append({
                'match_id': match_req.match_id,
                'match_number': match_req.match_number,
                'home_team': match_req.home_team,
                'away_team': match_req.away_team,
                'league': match_req.league,
                'match_time': match_req.match_time,
                'model_predictions': model_predictions,
                'team_stats': team_stats,
                'recent_form': recent_form
            })

        result = analyzer.analyze_round(
            round_id=request.round_id,
            matches=matches_data,
            game_type=request.game_type
        )

        # 텍스트 포맷 반환
        text = analyzer.format_marking_list(result)

        # 비용 정보 추가
        cost_info = cost_optimizer.estimate_cost(mode, len(request.matches))

        response = {
            "round_id": request.round_id,
            "game_type": request.game_type,
            "marking_text": text,
            "analyzed_at": result.analyzed_at,
            "cached": False,
            "cost_info": {
                'mode': mode.value,
                'estimated_cost_usd': cost_info['total'],
                'breakdown': cost_info['breakdown'],
                'savings': cost_info['savings'],
                'days_until_draw': days_left,
                'model_config': model_config
            }
        }

        # 결과 캐싱
        cost_optimizer.cache_result(request.round_id, response)

        return response

    except Exception as e:
        logger.error(f"프로토 텍스트 분석 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
