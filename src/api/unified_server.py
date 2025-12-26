"""
통합 API 서버
- 대시보드 API
- AI 분석 API
- 프로토 분석 API
- 라인업 모니터링 API
- 채팅 API
"""

import logging
import asyncio
import os
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict

from fastapi import (
    FastAPI,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    WebSocketDisconnect,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

# Database
from src.db.session import get_session, async_session
from src.db.models import Match, Team, League, TeamStats, PredictionLog, OddsHistory

# Services
from src.services.enhanced_chat_service import EnhancedChatService
from src.services.prediction_runner import PredictionRunner
from src.services.websocket_manager import manager as ws_manager
from src.services.odds_monitor import initialize_odds_monitor
from src.services.toto_analyzer import TotoAnalyzer
from src.config.settings import get_settings
from src.models.chat_models import ChatRequest, ChatResponse, ChatHistoryResponse
from src.services.toto_service import TotoService, TotoGame

# API Routes
from src.api.routes.analysis import router as analysis_router
from src.api.routes.scheduler import router as scheduler_router

# 로깅 설정
logger = logging.getLogger(__name__)

# AI Engine (optional - creating placeholder classes if module doesn't exist)
try:
    from src.ai_engine.core_analyzer import (
        AIOddsGenerator,
        ProtoAnalyzer,
        MatchAnalysis,
        TeamAnalysis,
        EnvironmentalFactors,
        MatchOutcome,
    )
    from src.ai_engine.lineup_monitor import LineupMonitor, ScheduledMatch, MatchStatus
except ImportError:
    # Placeholder classes to prevent ImportError
    logger.warning("ai_engine module not found, using placeholders")

    class AIOddsGenerator:
        def analyze_match(self, analysis):
            return analysis

    class ProtoAnalyzer:
        def analyze_proto_matches(self, matches):
            return {"results": []}

    class LineupMonitor:
        def __init__(self):
            self.matches = {}

        async def add_match(self, match):
            pass

        async def monitor_matches(self):
            pass

    # Placeholder for data classes
    MatchAnalysis = dict
    TeamAnalysis = dict
    EnvironmentalFactors = dict
    MatchOutcome = dict
    ScheduledMatch = dict

    class MatchStatus:
        SCHEDULED = "scheduled"
        LINEUP_PENDING = "lineup_pending"
        LINEUP_CONFIRMED = "lineup_confirmed"
        IN_PLAY = "in_play"
        FINISHED = "finished"


# Settings
settings = get_settings()

# FastAPI App
app = FastAPI(
    title="스포츠 분석 AI 통합 API",
    description="자체 배당 생성, 프로토 분석, 대시보드를 통합한 완전한 백엔드 API",
    version="3.0.0",
)

# Rate Limiting 설정
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS 설정 (환경 변수 기반)
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://localhost:5173,http://localhost:5174,http://localhost:5175",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# AI Analysis Router 등록
app.include_router(analysis_router)
# Auto Scheduler Router 등록
app.include_router(scheduler_router)

# 전역 인스턴스
ai_odds_generator = AIOddsGenerator()
proto_analyzer = ProtoAnalyzer()
lineup_monitor = LineupMonitor()
enhanced_chat_service = EnhancedChatService()  # Function Calling 지원
prediction_runner = PredictionRunner()
toto_analyzer = TotoAnalyzer()

# 모니터링 태스크
monitoring_task = None
odds_monitor = None  # 실시간 배당 모니터
kspo_sync_task = None  # KSPO 데이터 동기화 태스크
last_kspo_sync: datetime = datetime.min  # 마지막 동기화 시간


# ============================================================================
# Pydantic Models
# ============================================================================


class TeamAnalysisRequest(BaseModel):
    """팀 분석 요청"""

    team_id: int
    team_name: str
    attack_strength: float = 0.5
    defense_strength: float = 0.5
    recent_form: float = 0.5
    home_advantage: float = 0.1
    key_players: List[str] = []
    injuries: List[str] = []
    momentum: float = 0.5


class MatchAnalysisRequest(BaseModel):
    """경기 분석 요청"""

    match_id: int
    home_team: TeamAnalysisRequest
    away_team: TeamAnalysisRequest
    lineup_available: bool = False
    environmental_factors: Optional[Dict] = None
    head_to_head: Dict[str, float] = {"home_win": 0.4, "draw": 0.3, "away_win": 0.3}
    match_time: datetime


class ProtoAnalysisRequest(BaseModel):
    """프로토 분석 요청"""

    matches: List[MatchAnalysisRequest]
    analysis_type: str = "full"


class TotoAnalysisRequest(BaseModel):
    """승무패 분석 요청"""

    raw_text: str


class LineupMonitoringRequest(BaseModel):
    """라인업 모니터링 요청"""

    match_id: int
    home_team: str
    away_team: str
    league: str
    match_time: datetime


# ============================================================================
# Health & Root
# ============================================================================


@app.get("/")
async def root():
    """API 루트"""
    return {
        "service": "스포츠 분석 AI 통합 API",
        "version": "3.0.0",
        "description": "자체 배당 생성, 프로토 분석, 대시보드 통합 시스템",
        "endpoints": {
            "health": "/health",
            "dashboard": "/api/v1/dashboard",
            "matches": "/api/v1/matches",
            "ai_analysis": "/api/v1/analyze/*",
            "proto": "/api/v1/proto/*",
            "toto": "/api/v1/toto/*",
            "chat": "/api/v1/chat",
            "monitor": "/api/v1/monitor/*",
        },
    }


@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "ai_odds_generator": "active",
            "proto_analyzer": "active",
            "lineup_monitor": "active" if monitoring_task else "inactive",
            "kspo_sync": "active" if kspo_sync_task else "inactive",
            "database": "connected",  # TODO: 실제 DB 연결 확인
        },
        "last_kspo_sync": last_kspo_sync.isoformat()
        if last_kspo_sync != datetime.min
        else None,
        "provider": settings.provider,
    }


@app.post("/api/v1/games/sync")
async def sync_games_data():
    """KSPO API에서 최신 경기 데이터 수동 동기화"""
    try:
        count = await sync_kspo_data()
        return {
            "success": True,
            "message": f"KSPO 데이터 동기화 완료: {count}개 경기 처리",
            "synced_count": count,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"수동 동기화 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/toto/analyze")
async def analyze_toto(request: TotoAnalysisRequest):
    """승무패 14경기 분석"""
    try:
        report = await toto_analyzer.analyze_14_games(request.raw_text)
        return {"report": report}
    except Exception as e:
        logger.error(f"승무패 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze/round/{round_number}")
async def analyze_round(round_number: int, category: str = "축구 승무패"):
    """
    회차 전체 AI 분석 (베트맨 스타일)

    - 14경기 확률 계산 + 마킹 전략 결정
    - 기본 추천 14개 (파란색) + 복수선택 4개 (주황색)
    - 단통/투마킹/지우개 자동 결정
    """
    try:
        from src.services.soccer_analyzer import SoccerAnalyzer

        analyzer = SoccerAnalyzer()
        result = await analyzer.analyze_round(round_number, category)

        return {
            "success": True,
            "data": {
                "round_number": result.round_number,
                "category": result.category,
                "analyzed_at": result.analyzed_at,
                "matches": result.matches,
                "summary": result.summary,
            },
        }
    except Exception as e:
        logger.error(f"회차 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/toto/fetch-current-round")
async def fetch_toto_round():
    """KSPO API를 통해 현재 승무패 회차 경기 정보 가져오기"""
    try:
        from src.services.kspo_api_client import KSPOApiClient

        kspo_client = KSPOApiClient()

        # 최근 7일간의 경기 중 '승무패' 상품 검색
        # API 특성상 날짜별로 조회해야 하므로, 오늘 기준 전후 며칠을 스캔
        matches = []
        today = datetime.now()

        # 오늘부터 5일 뒤까지 조회 (발매 기간 고려)
        for i in range(6):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            daily_matches = await kspo_client.get_match_list(match_ymd=target_date)
            if daily_matches:
                matches.extend(daily_matches)

        # '승무패' 또는 '축구토토' 필터링
        toto_matches = [m for m in matches if "승무패" in m.get("obj_prod_nm", "")]

        # 중복 제거 (row_num 기준)
        unique_matches = {m["row_num"]: m for m in toto_matches}.values()

        # 텍스트 포맷팅
        formatted_text = ""
        for idx, m in enumerate(unique_matches, 1):
            home = m.get("hteam_han_nm", "")
            away = m.get("ateam_han_nm", "")
            formatted_text += f"{idx}. {home} vs {away}\n"

        if not formatted_text:
            return {
                "matches_text": "현재 발매 중인 승무패 대상 경기를 찾을 수 없습니다. (API 응답 없음)"
            }

        return {"matches_text": formatted_text}

    except Exception as e:
        logger.error(f"토토 경기 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/proto/list")
async def fetch_proto_list():
    """KSPO API를 통해 현재 프로토(승부식) 대상 경기 리스트 가져오기"""
    try:
        from src.services.kspo_api_client import KSPOApiClient

        kspo_client = KSPOApiClient()

        matches = await kspo_client.get_proto_matches()

        # 프론트엔드에서 사용하기 편하게 데이터 가공
        # Betman 스타일: [번호] [대회명] [시간] [홈팀] [원정팀]
        formatted_matches = []
        for m in matches:
            formatted_matches.append(
                {
                    "id": m.get("row_num"),
                    "date": m.get("match_ymd"),
                    "time": m.get("match_tm"),
                    "league": m.get("leag_han_nm"),
                    "home": m.get("hteam_han_nm"),
                    "away": m.get("ateam_han_nm"),
                    "sport": m.get("match_sport_han_nm"),
                    "status": m.get("match_end_val", "진행전"),
                }
            )

        return {"matches": formatted_matches}

    except Exception as e:
        logger.error(f"프로토 경기 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/proto/analyze-all")
async def analyze_all_proto():
    """현재 발매 중인 모든 프로토 경기를 일괄 분석"""
    try:
        from src.services.kspo_api_client import KSPOApiClient

        kspo_client = KSPOApiClient()

        # 1. 경기 리스트 가져오기
        matches = await kspo_client.get_proto_matches()

        if not matches:
            return {"message": "분석할 경기가 없습니다.", "results": []}

        # 2. 일괄 분석 실행
        results = await toto_analyzer.analyze_batch(matches)

        return {"results": results}

    except Exception as e:
        logger.error(f"프로토 일괄 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/games/active-rounds")
async def fetch_active_rounds():
    """현재 구매 가능한 게임 회차 정보 조회 (베트맨 스타일)"""
    try:
        from src.services.kspo_api_client import KSPOApiClient
        from datetime import datetime, timedelta

        kspo_client = KSPOApiClient()
        today = datetime.now()

        # 1주일치 데이터 조회
        all_matches = []
        for i in range(7):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            matches = await kspo_client.get_match_list(match_ymd=target_date)
            all_matches.extend(matches)

        # 회차별 그룹화
        rounds = {}
        for m in all_matches:
            # 키: (상품명, 회차)
            key = (m.get("obj_prod_nm"), m.get("turn_no"))
            if not key[0] or not key[1]:
                continue

            if key not in rounds:
                rounds[key] = {
                    "game_type": m.get("match_sport_han_nm", "기타"),
                    "game_name": key[0],
                    "round": key[1],
                    "deadline": m.get("match_tm"),  # 임시로 첫 경기 시간을 마감으로
                    "count": 0,
                }

            # 마감시간 업데이트 (가장 빠른 경기 시간)
            # 날짜까지 고려해야 하므로 실제로는 match_ymd + match_tm 비교 필요
            # 여기서는 단순화를 위해 리스트의 첫 경기 시간을 유지하거나 갱신

            rounds[key]["count"] += 1

        # 리스트로 변환 및 정렬
        result = []
        for r in rounds.values():
            result.append(r)

        # 정렬: 마감 임박 순 (여기서는 단순 정렬)
        return {"rounds": result}

    except Exception as e:
        logger.error(f"구매 가능 게임 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/games/rounds")
async def fetch_game_rounds(category: Optional[str] = None):
    """
    베트맨 스타일 회차 목록 조회

    Args:
        category: 게임 카테고리 (예: "프로토 승부식", "농구 승5패")

    Returns:
        카테고리별 회차 정보 (round_number, deadline, match_count)
    """
    try:
        async with get_session() as session:
            # 기본 쿼리: KSPO 데이터만 (league_id = 9999)
            query = (
                select(
                    Match.category_name,
                    Match.round_number,
                    Match.sport_type,
                    func.count(Match.id).label("match_count"),
                    func.min(Match.start_time).label("first_match_time"),
                    func.max(Match.start_time).label("last_match_time"),
                )
                .where(Match.league_id == 9999)
                .where(Match.category_name.isnot(None))
                .where(Match.round_number.isnot(None))
                .where(
                    Match.start_time >= datetime.now(timezone.utc) - timedelta(hours=24)
                )  # 최근 및 미래 경기
            )

            # 카테고리 필터
            if category:
                if category == "프로토":
                    query = query.where(Match.category_name.like("프로토%"))
                else:
                    query = query.where(Match.category_name == category)

            # 그룹화 및 정렬
            query = query.group_by(
                Match.category_name, Match.round_number, Match.sport_type
            ).order_by(
                Match.category_name,
                func.min(Match.start_time),  # 마감 임박 순
            )

            result = await session.execute(query)
            rounds_data = result.all()

            # 카테고리별 회차 그룹화
            categories_map = {}
            proto_rounds = []

            for row in rounds_data:
                cat_name = row.category_name

                # 마감 시간 계산 (첫 경기 시작 10분 전)
                deadline = (
                    row.first_match_time - timedelta(minutes=10)
                    if row.first_match_time
                    else None
                )

                round_info = {
                    "round_number": row.round_number,
                    "round_label": f"{row.round_number}회차",
                    "match_count": row.match_count,
                    "category_name": cat_name,
                    "deadline": deadline.isoformat() if deadline else None,
                    "first_match_time": row.first_match_time.isoformat()
                    if row.first_match_time
                    else None,
                    "last_match_time": row.last_match_time.isoformat()
                    if row.last_match_time
                    else None,
                }

                if cat_name.startswith("프로토"):
                    proto_rounds.append(round_info)

                if cat_name not in categories_map:
                    categories_map[cat_name] = {
                        "category_name": cat_name,
                        "sport_type": row.sport_type,
                        "rounds": [],
                    }
                categories_map[cat_name]["rounds"].append(round_info)

            # 특정 카테고리 요청 처리
            if category:
                requested_rounds = []
                if category == "프로토":
                    requested_rounds = proto_rounds
                elif category in categories_map:
                    requested_rounds = categories_map[category]["rounds"]

                # 회차 번호 및 마감 시간순 정렬
                requested_rounds.sort(
                    key=lambda x: (x["deadline"] or "", x["round_number"])
                )

                return {
                    "success": True,
                    "category": category,
                    "rounds": requested_rounds,
                    "total_rounds": len(requested_rounds),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }

            # 전체 카테고리 반환 (AllGameRounds용)
            # 그룹화 정의
            group_definitions = {
                "프로토": ["프로토 승부식"],
                "토토": ["축구 승무패", "농구 승5패"],
            }

            final_groups = []

            # 1. 프로토 그룹 처리
            proto_items = []
            # 승부식 통합
            if proto_rounds:
                seen_rounds = set()
                unique_proto_rounds = []
                for r in sorted(
                    proto_rounds, key=lambda x: (x["deadline"] or "", x["round_number"])
                ):
                    if r["round_number"] not in seen_rounds:
                        unique_proto_rounds.append(r)
                        seen_rounds.add(r["round_number"])

                proto_items.append(
                    {
                        "name": "프로토 승부식",
                        "display_name": "승부식",
                        "sport_type": "프로토",
                        "sport_emoji": "⚽",
                        "rounds": unique_proto_rounds,
                    }
                )

            if proto_items:
                final_groups.append({"group_name": "프로토", "items": proto_items})

            # 2. 토토 그룹 처리
            toto_items = []
            for cat_name in group_definitions["토토"]:
                if cat_name in categories_map:
                    cat_data = categories_map[cat_name]
                    display_name = cat_name.replace("축구 ", "").replace("농구 ", "")
                    sport_type = "축구" if "축구" in cat_name else "농구"

                    toto_items.append(
                        {
                            "name": cat_name,
                            "display_name": display_name,
                            "sport_type": sport_type,
                            "sport_emoji": "⚽" if sport_type == "축구" else "🏀",
                            "rounds": cat_data["rounds"],
                        }
                    )

            if toto_items:
                # 회차 마감 시간순 정렬
                toto_items.sort(
                    key=lambda x: (x["rounds"][0]["deadline"] if x["rounds"] else "")
                )
                final_groups.append({"group_name": "토토", "items": toto_items})

            return {
                "success": True,
                "groups": final_groups,
                "total_rounds": len(rounds_data),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in fetch_game_rounds: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/games/rounds/{round_number}")
async def fetch_round_matches(round_number: int, category: Optional[str] = None):
    """
    특정 회차의 경기 목록 조회 (AI 예측 포함)

    Args:
        round_number: 회차 번호 (예: 20251217)
        category: 게임 카테고리 필터 (선택)

    Returns:
        해당 회차의 모든 경기 정보 + AI 예측 결과
    """
    try:
        async with get_session() as session:
            # 경기 조회
            query = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                )
                .where(Match.league_id == 9999)
                .where(Match.round_number == round_number)
            )

            if category:
                if category in ["프로토", "프로토 승부식"]:
                    query = query.where(Match.category_name.like("프로토 %"))
                else:
                    query = query.where(Match.category_name == category)

            query = query.order_by(Match.start_time)

            result = await session.execute(query)
            matches = result.scalars().unique().all()

            if not matches:
                raise HTTPException(
                    status_code=404,
                    detail=f"회차 {round_number}의 경기를 찾을 수 없습니다",
                )

            # SoccerAnalyzer를 사용하여 일관된 분석 결과 제공
            from src.services.soccer_analyzer import SoccerAnalyzer

            analyzer = SoccerAnalyzer()
            analysis = await analyzer.analyze_round(
                round_number, category or matches[0].category_name
            )

            # 분석 결과를 경기 목록 형식으로 변환
            match_list = []
            for match in matches:
                # 해당 경기의 분석 데이터 찾기
                m_analysis = next(
                    (m for m in analysis.matches if m["match_id"] == match.id), None
                )

                # 기본 데이터 구성
                match_data = {
                    "id": match.id,
                    "home_team": match.home_team.name if match.home_team else "Unknown",
                    "home_team_logo": match.home_team.logo_url
                    if (match.home_team and match.home_team.logo_url)
                    else None,
                    "away_team": match.away_team.name if match.away_team else "Unknown",
                    "away_team_logo": match.away_team.logo_url
                    if (match.away_team and match.away_team.logo_url)
                    else None,
                    "league_name": match.league.name if match.league else "Unknown",
                    "start_time": match.start_time.isoformat(),
                    "status": match.status,
                    "sport_type": match.sport_type,
                    "category_name": match.category_name,
                    "round_number": match.round_number,
                    "odds": {
                        "home": float(match.odds_home) if match.odds_home else 2.0,
                        "draw": float(match.odds_draw) if match.odds_draw else 3.0,
                        "away": float(match.odds_away) if match.odds_away else 3.0,
                    },
                }

                # AI 분석 결과 추가
                if m_analysis:
                    match_data["prediction"] = {
                        "home_prob": round(
                            m_analysis["probabilities"]["home"] * 100, 1
                        ),
                        "draw_prob": round(
                            m_analysis["probabilities"]["draw"] * 100, 1
                        ),
                        "away_prob": round(
                            m_analysis["probabilities"]["away"] * 100, 1
                        ),
                        "recommended": m_analysis["primary_pick"],
                        "strategy": m_analysis["strategy"],
                        "is_bonus": m_analysis["is_bonus_pick"],
                        "confidence": m_analysis["confidence"],
                    }

                match_list.append(match_data)

            return {
                "success": True,
                "round_number": round_number,
                "category": category or matches[0].category_name,
                "sport_type": matches[0].sport_type,
                "total_matches": len(match_list),
                "matches": match_list,
                "summary": analysis.summary,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"회차 경기 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/games/list")
async def fetch_games_list(refresh: bool = False):
    """
    베트맨 스타일 경기 목록 (종목별 그룹화)

    Args:
        refresh: True이면 KSPO API에서 최신 데이터를 먼저 동기화
    """
    try:
        # 강제 동기화 요청 또는 마지막 동기화 후 30분 이상 경과 시 자동 동기화
        global last_kspo_sync
        time_since_sync = (datetime.now(timezone.utc) - last_kspo_sync).total_seconds()

        if refresh or time_since_sync > 1800:  # 30분
            await sync_kspo_data()

        async with get_session() as session:
            now = datetime.now(timezone.utc)

            # KSPO 데이터 조회 (league_id = 9999)
            # 조건: 시작시간이 현재 시간 이후 또는 현재 시간 기준 2시간 이내에 시작한 경기
            # (2시간 이상 지난 경기는 대부분 종료됨)
            result = await session.execute(
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                )
                .where(Match.league_id == 9999)
                .where(
                    Match.start_time >= now - timedelta(hours=2)
                )  # 2시간 이내 시작한 경기 + 미래 경기
                .order_by(Match.start_time)
            )
            matches = result.scalars().unique().all()

            # 카테고리별 그룹화 (product_name + sport_type)
            categories = {}

            for match in matches:
                # 카테고리 키 생성
                category_name = match.category_name or "기타"

                # 허용된 카테고리 필터링 (사용자 요청에 따라 조정 가능)
                if any(
                    x in category_name
                    for x in ["야구 승1패", "토토 기록식", "언더오버"]
                ):
                    continue

                product = match.product_name or "기타"
                sport = match.sport_type or "기타"

                if category_name not in categories:
                    categories[category_name] = {
                        "name": category_name,
                        "product_name": product,
                        "sport_type": sport,
                        "count": 0,
                        "matches": [],
                    }

                # 마감 시간 계산 (경기 시작 10분 전)
                deadline = match.start_time - timedelta(minutes=10)
                now = datetime.now(timezone.utc)
                time_until_deadline = (deadline - now).total_seconds()
                time_until_start = (match.start_time - now).total_seconds()

                # 마감 임박 여부 판단 (30분 이내)
                is_deadline_soon = 0 < time_until_deadline < 1800

                # 실시간 상태 계산
                if time_until_deadline < 0:
                    # 마감 시간 지남 - 더 이상 구매 불가
                    if time_until_start < 0:
                        # 경기 시작 시간 지남
                        if time_until_start < -7200:  # 2시간 지남 (경기 종료 가정)
                            calculated_status = "종료"
                        else:
                            calculated_status = "진행중"
                    else:
                        calculated_status = "마감"
                else:
                    calculated_status = "예정"

                # 구매 불가능한 경기는 목록에서 제외 (마감, 진행중, 종료)
                if calculated_status in ["종료", "진행중", "마감"]:
                    continue

                # 경기 정보 추가
                match_data = {
                    "id": match.id,
                    "home_team": match.home_team.name,
                    "home_team_logo": match.home_team.logo_url
                    if (match.home_team and match.home_team.logo_url)
                    else f"https://api.dicebear.com/7.x/initials/svg?seed={match.home_team.name}&backgroundColor=005BAC&fontFamily=Arial&fontWeight=700"
                    if match.home_team
                    else None,
                    "away_team": match.away_team.name,
                    "away_team_logo": match.away_team.logo_url
                    if (match.away_team and match.away_team.logo_url)
                    else f"https://api.dicebear.com/7.x/initials/svg?seed={match.away_team.name}&backgroundColor=6B7280&fontFamily=Arial&fontWeight=700"
                    if match.away_team
                    else None,
                    "league_name": match.league.name,
                    "start_time": match.start_time.isoformat(),
                    "deadline": deadline.isoformat(),
                    "is_deadline_soon": is_deadline_soon,
                    "status": calculated_status,
                    "sport_type": sport,
                    "product_name": product,
                    "round_number": match.round_number,
                    "odds_home": match.odds_home,
                    "odds_draw": match.odds_draw,
                    "odds_away": match.odds_away,
                    "category_name": category_name,
                }

                categories[category_name]["matches"].append(match_data)
                categories[category_name]["count"] += 1

            # 리스트로 변환 및 정렬
            categories_list = sorted(
                categories.values(), key=lambda x: (x["product_name"], x["sport_type"])
            )

            # 전체 통계
            total_matches = sum(cat["count"] for cat in categories_list)

            return {
                "success": True,
                "total_matches": total_matches,
                "categories": categories_list,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"경기 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dashboard API
# ============================================================================


@app.get("/api/v1/dashboard")
async def get_dashboard():
    """대시보드 데이터"""
    try:
        async with get_session() as session:
            # 오늘의 경기 수
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            today_matches_count = await session.scalar(
                select(func.count(Match.id))
                .where(Match.start_time >= today)
                .where(Match.start_time < tomorrow)
            )

            # Value Bet 개수
            value_bets_count = await session.scalar(
                select(func.count(Match.id)).where(Match.recommendation.like("%VALUE%"))
            )

            # 최근 경기 목록
            stmt = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                )
                .where(Match.start_time >= today)
                .order_by(Match.start_time)
                .limit(10)
            )
            result = await session.execute(stmt)
            matches = result.unique().scalars().all()

            fixtures = [
                {
                    "id": m.id,
                    "home_team": m.home_team.name if m.home_team else "Unknown",
                    "away_team": m.away_team.name if m.away_team else "Unknown",
                    "start_time": m.start_time.isoformat(),
                    "league": m.league.name if m.league else "Unknown",
                    "status": m.status,
                }
                for m in matches
            ]

            # Value Picks
            value_stmt = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                )
                .where(Match.recommendation.like("%VALUE%"))
                .order_by(Match.recommended_stake_pct.desc())
                .limit(5)
            )
            value_result = await session.execute(value_stmt)
            value_matches = value_result.unique().scalars().all()

            picks = [
                {
                    "id": m.id,
                    "home_team": m.home_team.name if m.home_team else "Unknown",
                    "away_team": m.away_team.name if m.away_team else "Unknown",
                    "recommendation": m.recommendation,
                    "stake_pct": m.recommended_stake_pct,
                }
                for m in value_matches
            ]

            return {
                "total_matches_today": today_matches_count,
                "value_bets_count": value_bets_count,
                "active_leagues": 7,
                "fixtures": fixtures,
                "picks": picks,
            }

    except Exception as e:
        logger.error(f"대시보드 조회 오류: {e}")
        # Fallback 데이터
        return {
            "total_matches_today": 0,
            "value_bets_count": 0,
            "active_leagues": 7,
            "fixtures": [],
            "picks": [],
        }


@app.get("/api/v1/matches")
async def get_matches(
    league: Optional[str] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 50,
):
    """경기 목록 조회"""
    try:
        async with get_session() as session:
            stmt = select(Match).options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league),
            )

            # 필터링
            if league:
                stmt = stmt.join(League).where(League.name == league)
            if status:
                stmt = stmt.where(Match.status == status)
            if date:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
                stmt = stmt.where(
                    Match.start_time >= target_date,
                    Match.start_time < target_date + timedelta(days=1),
                )

            stmt = stmt.order_by(Match.start_time).limit(limit)
            result = await session.execute(stmt)
            matches = result.unique().scalars().all()

            return {
                "matches": [
                    {
                        "id": m.id,
                        "home_team": m.home_team.name if m.home_team else "Unknown",
                        "away_team": m.away_team.name if m.away_team else "Unknown",
                        "start_time": m.start_time.isoformat(),
                        "status": m.status,
                        "league": m.league.name if m.league else "Unknown",
                        "recommendation": m.recommendation,
                        "stake_pct": m.recommended_stake_pct,
                    }
                    for m in matches
                ],
                "count": len(matches),
            }

    except Exception as e:
        logger.error(f"경기 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/matches/today")
async def get_today_matches():
    """당일 경기 목록 (리그별 그룹화)"""
    try:
        async with get_session() as session:
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            # 오늘의 모든 경기 조회
            stmt = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                )
                .where(Match.start_time >= today)
                .where(Match.start_time < tomorrow)
                .order_by(Match.league_id, Match.start_time)
            )
            result = await session.execute(stmt)
            matches = result.unique().scalars().all()

            # 리그별 그룹화
            leagues_data = {}
            for match in matches:
                league_name = match.league.name if match.league else "Unknown"
                league_country = match.league.country if match.league else None
                league_key = f"{league_name}_{match.league_id if match.league else 0}"

                if league_key not in leagues_data:
                    leagues_data[league_key] = {
                        "league_id": match.league_id,
                        "league_name": league_name,
                        "league_country": league_country,
                        "sport": match.sport,
                        "matches": [],
                    }

                # 최신 오즈 조회
                odds_stmt = (
                    select(OddsHistory)
                    .where(OddsHistory.match_id == match.id)
                    .order_by(OddsHistory.captured_at.desc())
                    .limit(1)
                )
                odds = await session.scalar(odds_stmt)

                leagues_data[league_key]["matches"].append(
                    {
                        "id": match.id,
                        "home_team": match.home_team.name
                        if match.home_team
                        else "Unknown",
                        "away_team": match.away_team.name
                        if match.away_team
                        else "Unknown",
                        "start_time": match.start_time.isoformat(),
                        "status": match.status,
                        "odds": {
                            "home": odds.odds_home if odds else match.odds_home,
                            "draw": odds.odds_draw if odds else match.odds_draw,
                            "away": odds.odds_away if odds else match.odds_away,
                        },
                        "xg": {"home": match.xg_home, "away": match.xg_away}
                        if match.xg_home
                        else None,
                    }
                )

            # 리스트로 변환
            leagues_list = sorted(
                leagues_data.values(), key=lambda x: len(x["matches"]), reverse=True
            )

            return {
                "date": today.isoformat(),
                "total_matches": len(matches),
                "total_leagues": len(leagues_list),
                "leagues": leagues_list,
            }

    except Exception as e:
        logger.error(f"당일 경기 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/matches/{match_id}")
async def get_match_detail(match_id: int):
    """경기 상세 정보"""
    try:
        async with get_session() as session:
            # Eager loading으로 Match와 관련 엔티티를 한 번에 로드
            stmt = (
                select(Match)
                .options(
                    joinedload(Match.home_team),
                    joinedload(Match.away_team),
                    joinedload(Match.league),
                )
                .where(Match.id == match_id)
            )
            result = await session.execute(stmt)
            match = result.unique().scalar_one_or_none()

            if not match:
                raise HTTPException(status_code=404, detail="경기를 찾을 수 없습니다")

            # 최신 배당
            odds_stmt = (
                select(OddsHistory)
                .where(OddsHistory.match_id == match_id)
                .order_by(OddsHistory.captured_at.desc())
                .limit(1)
            )
            odds = await session.scalar(odds_stmt)

            # 예측 로그
            pred_stmt = (
                select(PredictionLog)
                .where(PredictionLog.match_id == match_id)
                .order_by(PredictionLog.created_at.desc())
                .limit(1)
            )
            prediction = await session.scalar(pred_stmt)

            return {
                "id": match.id,
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "start_time": match.start_time.isoformat(),
                "league": match.league.name if match.league else "Unknown",
                "status": match.status,
                "odds": {
                    "home": odds.odds_home if odds else None,
                    "draw": odds.odds_draw if odds else None,
                    "away": odds.odds_away if odds else None,
                }
                if odds
                else None,
                "prediction": {
                    "probabilities": {
                        "home": prediction.prob_home,
                        "draw": prediction.prob_draw,
                        "away": prediction.prob_away,
                    },
                    "expected_score": {
                        "home": prediction.expected_score_home,
                        "away": prediction.expected_score_away,
                    },
                    "values": {
                        "home": prediction.value_home,
                        "draw": prediction.value_draw,
                        "away": prediction.value_away,
                    },
                }
                if prediction
                else None,
                "recommendation": match.recommendation,
                "stake_pct": match.recommended_stake_pct,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"경기 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/matches/{match_id}/analysis")
async def get_match_analysis(match_id: int):
    """
    경기 상세 AI 분석 (베트맨 스타일)

    Returns:
        - prediction: 승/무/패 예측 확률 (0-100)
        - confidence: 예측 신뢰도 (0-100)
        - recommended_bet: 추천 배팅 옵션
        - key_factors: 주요 분석 포인트
        - analysis_text: AI 생성 상세 분석
    """
    try:
        async with get_session() as session:
            # 경기 정보 조회 (relationships를 옵션으로 처리)
            stmt = select(Match).where(Match.id == match_id)
            result = await session.execute(stmt)
            match = result.scalar_one_or_none()

            if not match:
                raise HTTPException(status_code=404, detail="경기를 찾을 수 없습니다")

            # 관계 객체 로드 (KSPO 경기는 없을 수 있음)
            home_team_name = "Unknown"
            away_team_name = "Unknown"
            league_name = "Unknown"

            if match.home_team_id:
                home_team = await session.get(Team, match.home_team_id)
                if home_team:
                    home_team_name = home_team.name

            if match.away_team_id:
                away_team = await session.get(Team, match.away_team_id)
                if away_team:
                    away_team_name = away_team.name

            if match.league_id:
                league = await session.get(League, match.league_id)
                if league:
                    league_name = league.name

            # 최신 배당
            odds_stmt = (
                select(OddsHistory)
                .where(OddsHistory.match_id == match_id)
                .order_by(OddsHistory.captured_at.desc())
                .limit(1)
            )
            odds = await session.scalar(odds_stmt)

            # 예측 로그
            pred_stmt = (
                select(PredictionLog)
                .where(PredictionLog.match_id == match_id)
                .order_by(PredictionLog.created_at.desc())
                .limit(1)
            )
            prediction = await session.scalar(pred_stmt)

            # 팀 통계 조회
            home_stats_stmt = (
                select(TeamStats)
                .where(TeamStats.team_id == match.home_team_id)
                .where(TeamStats.season == match.season)
                .order_by(TeamStats.updated_at.desc())
                .limit(1)
            )
            home_stats = await session.scalar(home_stats_stmt)

            away_stats_stmt = (
                select(TeamStats)
                .where(TeamStats.team_id == match.away_team_id)
                .where(TeamStats.season == match.season)
                .order_by(TeamStats.updated_at.desc())
                .limit(1)
            )
            away_stats = await session.scalar(away_stats_stmt)

            # 분석 설명 생성
            analysis_notes = []

            # AI 예측 분석
            if prediction:
                prob_home = prediction.prob_home or 0
                prob_draw = prediction.prob_draw or 0
                prob_away = prediction.prob_away or 0

                # 가장 높은 확률 찾기
                max_prob = max(prob_home, prob_draw, prob_away)
                if max_prob == prob_home:
                    analysis_notes.append(
                        {
                            "type": "prediction",
                            "title": "AI 예측: 홈 승리 우세",
                            "description": f"AI 모델은 {home_team_name}의 승리 확률을 {prob_home * 100:.1f}%로 예측했습니다.",
                            "confidence": prob_home,
                        }
                    )
                elif max_prob == prob_away:
                    analysis_notes.append(
                        {
                            "type": "prediction",
                            "title": "AI 예측: 원정 승리 우세",
                            "description": f"AI 모델은 {away_team_name}의 승리 확률을 {prob_away * 100:.1f}%로 예측했습니다.",
                            "confidence": prob_away,
                        }
                    )
                else:
                    analysis_notes.append(
                        {
                            "type": "prediction",
                            "title": "AI 예측: 무승부 가능성 높음",
                            "description": f"AI 모델은 무승부 확률을 {prob_draw * 100:.1f}%로 예측했습니다.",
                            "confidence": prob_draw,
                        }
                    )

                # Expected Goals 분석
                if prediction.expected_score_home and prediction.expected_score_away:
                    xg_diff = (
                        prediction.expected_score_home - prediction.expected_score_away
                    )
                    if abs(xg_diff) > 0.5:
                        favored_team = home_team_name if xg_diff > 0 else away_team_name
                        analysis_notes.append(
                            {
                                "type": "xg",
                                "title": "예상 득점 (xG)",
                                "description": f"{favored_team}이(가) 예상 득점에서 {'%.1f' % abs(xg_diff)}골 앞서며 공격력 우위를 보일 것으로 예상됩니다.",
                                "data": {
                                    "home_xg": round(prediction.expected_score_home, 2),
                                    "away_xg": round(prediction.expected_score_away, 2),
                                },
                            }
                        )

            # 팀 통계 분석
            if home_stats and away_stats:
                # 모멘텀 비교
                home_momentum = home_stats.momentum or 0.5
                away_momentum = away_stats.momentum or 0.5

                if abs(home_momentum - away_momentum) > 0.15:
                    better_form = (
                        home_team_name
                        if home_momentum > away_momentum
                        else away_team_name
                    )
                    analysis_notes.append(
                        {
                            "type": "form",
                            "title": "최근 경기력",
                            "description": f"{better_form}이(가) 최근 경기에서 더 좋은 폼을 보이고 있습니다.",
                            "data": {
                                "home_momentum": round(home_momentum, 2),
                                "away_momentum": round(away_momentum, 2),
                            },
                        }
                    )

                # xG 통계 비교
                if home_stats.xg and away_stats.xg:
                    home_attack = home_stats.xg
                    away_attack = away_stats.xg
                    analysis_notes.append(
                        {
                            "type": "stats",
                            "title": "시즌 공격력",
                            "description": f"시즌 평균 예상 득점 - {home_team_name}: {home_attack:.2f}, {away_team_name}: {away_attack:.2f}",
                            "data": {
                                "home_xg_season": round(home_attack, 2),
                                "away_xg_season": round(away_attack, 2),
                            },
                        }
                    )

            # 배당 vs AI 확률 비교
            if odds and prediction:
                # 내재 확률 계산 (마진 제거)
                if odds.odds_home and odds.odds_draw and odds.odds_away:
                    implied_home = 1 / odds.odds_home
                    implied_draw = 1 / odds.odds_draw
                    implied_away = 1 / odds.odds_away
                    total_implied = implied_home + implied_draw + implied_away

                    # 마진 제거된 실제 확률
                    true_implied_home = implied_home / total_implied
                    true_implied_away = implied_away / total_implied

                    # AI 예측과 비교
                    home_diff = (prediction.prob_home or 0) - true_implied_home
                    away_diff = (prediction.prob_away or 0) - true_implied_away

                    if abs(home_diff) > 0.10 or abs(away_diff) > 0.10:
                        if home_diff > 0.10:
                            analysis_notes.append(
                                {
                                    "type": "value",
                                    "title": "가치 발견: 홈 승리",
                                    "description": f"AI는 홈 승리 확률을 {(prediction.prob_home or 0) * 100:.1f}%로 보지만, 시장 배당은 {true_implied_home * 100:.1f}%만 반영하고 있습니다. ({home_diff * 100:.1f}%p 차이)",
                                    "edge": round(home_diff * 100, 1),
                                }
                            )
                        elif away_diff > 0.10:
                            analysis_notes.append(
                                {
                                    "type": "value",
                                    "title": "가치 발견: 원정 승리",
                                    "description": f"AI는 원정 승리 확률을 {(prediction.prob_away or 0) * 100:.1f}%로 보지만, 시장 배당은 {true_implied_away * 100:.1f}%만 반영하고 있습니다. ({away_diff * 100:.1f}%p 차이)",
                                    "edge": round(away_diff * 100, 1),
                                }
                            )

            # 샤프 머니 감지
            if match.sharp_detected:
                analysis_notes.append(
                    {
                        "type": "sharp",
                        "title": "샤프 머니 감지",
                        "description": f"프로 베터들의 큰 움직임이 {match.sharp_direction} 방향으로 감지되었습니다. 배당이 급격히 변동했습니다.",
                        "direction": match.sharp_direction,
                    }
                )

            # 라인업 정보
            injuries_info = "부상자 정보 없음"
            if match.lineup_confirmed_at:
                injuries_info = (
                    f"라인업 {match.lineup_confirmed_at.strftime('%H:%M')}에 발표됨"
                )

            # key_factors 구조화
            key_factors = {
                "recent_form": "",
                "head_to_head": "",
                "home_away_form": "",
                "injuries": injuries_info,
                "odds_analysis": "",
            }

            # analysis_notes에서 key_factors 추출
            for note in analysis_notes:
                if note.get("type") == "form":
                    key_factors["recent_form"] = note.get("description", "")
                elif note.get("type") == "stats":
                    key_factors["home_away_form"] = note.get("description", "")
                elif note.get("type") == "value":
                    key_factors["odds_analysis"] = note.get("description", "")

            # confidence 계산 (예측 확률 중 최대값을 신뢰도로 사용)
            prob_home = (prediction.prob_home or 0) if prediction else 0.33
            prob_draw = (prediction.prob_draw or 0) if prediction else 0.33
            prob_away = (prediction.prob_away or 0) if prediction else 0.34
            confidence = max(prob_home, prob_draw, prob_away) * 100

            # recommended_bet 계산
            if prob_home > prob_draw and prob_home > prob_away:
                recommended_bet = "home"
            elif prob_away > prob_draw and prob_away > prob_home:
                recommended_bet = "away"
            else:
                recommended_bet = "draw"

            # NEXT_STEPS.md 형식에 맞는 응답 반환
            return {
                "match_id": match.id,
                "match_info": {
                    "home_team": home_team_name,
                    "away_team": away_team_name,
                    "league": league_name,
                    "start_time": match.start_time.isoformat(),
                    "status": match.status,
                },
                "prediction": {
                    "home_win_prob": round(prob_home * 100, 1),
                    "draw_prob": round(prob_draw * 100, 1),
                    "away_win_prob": round(prob_away * 100, 1),
                },
                "confidence": round(confidence, 1),
                "recommended_bet": recommended_bet,
                "key_factors": key_factors,
                # 프론트엔드 MatchAnalysisModal 형식에 맞춘 응답
                "match": {
                    "id": match.id,
                    "home_team": home_team_name,
                    "away_team": away_team_name,
                    "league": league_name,
                    "start_time": match.start_time.isoformat(),
                    "status": match.status or "예정",
                    "lineup_status": "확정" if match.lineup_confirmed_at else "미확정",
                },
                "odds": {
                    "home": float(odds.odds_home)
                    if odds and odds.odds_home
                    else float(match.odds_home)
                    if match.odds_home
                    else None,
                    "draw": float(odds.odds_draw)
                    if odds and odds.odds_draw
                    else float(match.odds_draw)
                    if match.odds_draw
                    else None,
                    "away": float(odds.odds_away)
                    if odds and odds.odds_away
                    else float(match.odds_away)
                    if match.odds_away
                    else None,
                    "captured_at": odds.captured_at.isoformat()
                    if odds and odds.captured_at
                    else None,
                },
                "ai_prediction": {
                    "probabilities": {
                        "home": round(prob_home * 100, 1),
                        "draw": round(prob_draw * 100, 1),
                        "away": round(prob_away * 100, 1),
                    },
                    "expected_score": {
                        "home": round(prediction.expected_score_home, 2)
                        if prediction and prediction.expected_score_home
                        else None,
                        "away": round(prediction.expected_score_away, 2)
                        if prediction and prediction.expected_score_away
                        else None,
                    },
                },
                "team_stats": {
                    "home": {
                        "xg_per_game": round(home_stats.xg, 2)
                        if home_stats and home_stats.xg
                        else None,
                        "xga_per_game": round(home_stats.xga, 2)
                        if home_stats and home_stats.xga
                        else None,
                        "momentum": round(home_stats.momentum, 2)
                        if home_stats and home_stats.momentum
                        else None,
                    }
                    if home_stats
                    else None,
                    "away": {
                        "xg_per_game": round(away_stats.xg, 2)
                        if away_stats and away_stats.xg
                        else None,
                        "xga_per_game": round(away_stats.xga, 2)
                        if away_stats and away_stats.xga
                        else None,
                        "momentum": round(away_stats.momentum, 2)
                        if away_stats and away_stats.momentum
                        else None,
                    }
                    if away_stats
                    else None,
                },
                "analysis_notes": analysis_notes,
                "sharp_detected": bool(match.sharp_detected)
                if hasattr(match, "sharp_detected")
                else False,
                "sharp_direction": match.sharp_direction
                if hasattr(match, "sharp_direction")
                else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"경기 분석 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AI Analysis API
# ============================================================================


@app.post("/api/v1/analyze/match")
async def analyze_match(request: MatchAnalysisRequest):
    """단일 경기 AI 분석"""
    try:
        # 팀 분석 객체 생성
        home_team = TeamAnalysis(
            team_id=request.home_team.team_id,
            team_name=request.home_team.team_name,
            attack_strength=request.home_team.attack_strength,
            defense_strength=request.home_team.defense_strength,
            recent_form=request.home_team.recent_form,
            home_advantage=request.home_team.home_advantage,
            key_players=request.home_team.key_players,
            injuries=request.home_team.injuries,
            momentum=request.home_team.momentum,
        )

        away_team = TeamAnalysis(
            team_id=request.away_team.team_id,
            team_name=request.away_team.team_name,
            attack_strength=request.away_team.attack_strength,
            defense_strength=request.away_team.defense_strength,
            recent_form=request.away_team.recent_form,
            home_advantage=request.away_team.home_advantage,
            key_players=request.away_team.key_players,
            injuries=request.away_team.injuries,
            momentum=request.away_team.momentum,
        )

        # 환경 요인
        env_factors = EnvironmentalFactors(
            venue=request.environmental_factors.get("venue", "Unknown")
            if request.environmental_factors
            else "Unknown",
            weather=request.environmental_factors.get("weather", "Clear")
            if request.environmental_factors
            else "Clear",
            temperature=request.environmental_factors.get("temperature", 20.0)
            if request.environmental_factors
            else 20.0,
            humidity=request.environmental_factors.get("humidity", 60.0)
            if request.environmental_factors
            else 60.0,
            travel_distance=request.environmental_factors.get("travel_distance", 0.0)
            if request.environmental_factors
            else 0.0,
            rest_days=request.environmental_factors.get("rest_days", 4)
            if request.environmental_factors
            else 4,
        )

        # 경기 분석 객체 생성
        match_analysis = MatchAnalysis(
            match_id=request.match_id,
            home_team=home_team,
            away_team=away_team,
            lineup_analysis=None,
            environmental_factors=env_factors,
            head_to_head=request.head_to_head,
            predicted_probabilities={},
            own_odds={},
            confidence_score=0.0,
            analyzed_at=datetime.now(),
            match_time=request.match_time,
        )

        # AI 분석 실행
        result = ai_odds_generator.analyze_match(match_analysis)

        # 응답 생성
        response = {
            "match_id": result.match_id,
            "home_team": result.home_team.team_name,
            "away_team": result.away_team.team_name,
            "analysis_time": result.analyzed_at.isoformat(),
            "predicted_probabilities": {
                k.value: round(v, 4) for k, v in result.predicted_probabilities.items()
            },
            "own_odds": {k.value: round(v, 2) for k, v in result.own_odds.items()},
            "confidence_score": round(result.confidence_score, 3),
            "lineup_used": False,
            "recommendation": generate_recommendation(result),
        }

        return response

    except Exception as e:
        logger.error(f"경기 분석 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Proto Analysis API
# ============================================================================


@app.get("/api/v1/proto/today")
async def get_today_proto_matches():
    """오늘의 프로토 후보 경기 (14경기)"""
    try:
        async with get_session() as session:
            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)

            # 주요 리그의 오늘 경기 조회
            stmt = (
                select(Match)
                .join(League)
                .where(Match.start_time >= today)
                .where(Match.start_time < tomorrow)
                .where(
                    League.name.in_(
                        [
                            "Premier League",
                            "La Liga",
                            "Bundesliga",
                            "Serie A",
                            "Ligue 1",
                            "NBA",
                            "MLB",
                        ]
                    )
                )
                .order_by(Match.start_time)
                .limit(14)
            )

            result = await session.execute(stmt)
            matches = result.scalars().all()

            return {
                "matches": [
                    {
                        "id": m.id,
                        "home_team": m.home_team.name if m.home_team else "Unknown",
                        "away_team": m.away_team.name if m.away_team else "Unknown",
                        "start_time": m.start_time.isoformat(),
                        "league": m.league.name if m.league else "Unknown",
                    }
                    for m in matches
                ],
                "count": len(matches),
                "date": today.isoformat(),
            }

    except Exception as e:
        logger.error(f"프로토 경기 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/proto/analyze")
async def analyze_proto(request: ProtoAnalysisRequest):
    """프로토 14경기 AI 분석"""
    try:
        if len(request.matches) != 14:
            raise HTTPException(
                status_code=400, detail="프로토 분석은 정확히 14경기가 필요합니다"
            )

        # 경기 분석 객체 리스트 생성
        match_analyses = []

        for match_req in request.matches:
            home_team = TeamAnalysis(
                team_id=match_req.home_team.team_id,
                team_name=match_req.home_team.team_name,
                attack_strength=match_req.home_team.attack_strength,
                defense_strength=match_req.home_team.defense_strength,
                recent_form=match_req.home_team.recent_form,
                home_advantage=match_req.home_team.home_advantage,
                key_players=match_req.home_team.key_players,
                injuries=match_req.home_team.injuries,
                momentum=match_req.home_team.momentum,
            )

            away_team = TeamAnalysis(
                team_id=match_req.away_team.team_id,
                team_name=match_req.away_team.team_name,
                attack_strength=match_req.away_team.attack_strength,
                defense_strength=match_req.away_team.defense_strength,
                recent_form=match_req.away_team.recent_form,
                home_advantage=match_req.away_team.home_advantage,
                key_players=match_req.away_team.key_players,
                injuries=match_req.away_team.injuries,
                momentum=match_req.away_team.momentum,
            )

            env_factors = EnvironmentalFactors(
                venue=match_req.environmental_factors.get("venue", "Unknown")
                if match_req.environmental_factors
                else "Unknown",
                weather=match_req.environmental_factors.get("weather", "Clear")
                if match_req.environmental_factors
                else "Clear",
                temperature=match_req.environmental_factors.get("temperature", 20.0)
                if match_req.environmental_factors
                else 20.0,
                humidity=match_req.environmental_factors.get("humidity", 60.0)
                if match_req.environmental_factors
                else 60.0,
                travel_distance=match_req.environmental_factors.get(
                    "travel_distance", 0.0
                )
                if match_req.environmental_factors
                else 0.0,
                rest_days=match_req.environmental_factors.get("rest_days", 4)
                if match_req.environmental_factors
                else 4,
            )

            match_analysis = MatchAnalysis(
                match_id=match_req.match_id,
                home_team=home_team,
                away_team=away_team,
                lineup_analysis=None,
                environmental_factors=env_factors,
                head_to_head=match_req.head_to_head,
                predicted_probabilities={},
                own_odds={},
                confidence_score=0.0,
                analyzed_at=datetime.now(),
                match_time=match_req.match_time,
            )

            match_analyses.append(match_analysis)

        # 프로토 분석 실행
        analysis_result = proto_analyzer.analyze_proto_matches(match_analyses)

        return {
            "analysis_id": f"proto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "analysis_time": datetime.now().isoformat(),
            "analysis_type": request.analysis_type,
            "total_matches": 14,
            **analysis_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프로토 분석 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Chat API
# ============================================================================


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_agent(request: ChatRequest):
    """
    AI 채팅 에이전트 (Enhanced with Function Calling)

    Features:
    - OpenAI GPT-4o Function Calling
    - 자동 DB 쿼리 실행
    - 대화 히스토리 유지
    """
    try:
        # 세션 ID 생성 (없으면) - Pydantic v2 Optional 필드 처리
        session_id = (
            getattr(request, "session_id", None)
            or f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        # DB 세션과 함께 채팅
        async with get_session() as db_session:
            response = await enhanced_chat_service.chat(
                query=request.query,
                session_id=session_id,
                db_session=db_session,
                context=request.context,
            )

        return response

    except Exception as e:
        logger.error(f"채팅 처리 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/chat/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str):
    """
    대화 히스토리 조회

    Args:
        session_id: 세션 ID

    Returns:
        ChatHistoryResponse: 대화 내역
    """
    try:
        messages = enhanced_chat_service.get_session_history(session_id)
        session_info = enhanced_chat_service.get_session_info(session_id)

        return ChatHistoryResponse(
            session_id=session_id,
            messages=messages,
            message_count=len(messages),
            last_activity=session_info.get("last_activity") if session_info else None,
        )

    except Exception as e:
        logger.error(f"히스토리 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/chat/session/{session_id}")
async def delete_chat_session(session_id: str):
    """
    세션 삭제

    Args:
        session_id: 세션 ID

    Returns:
        dict: 삭제 결과
    """
    try:
        success = enhanced_chat_service.delete_session(session_id)
        if success:
            return {"message": "Session deleted successfully", "session_id": session_id}
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Lineup Monitoring API
# ============================================================================


@app.post("/api/v1/monitor/add")
async def add_to_monitoring(
    request: LineupMonitoringRequest, background_tasks: BackgroundTasks
):
    """라인업 모니터링에 경기 추가"""
    try:
        match = ScheduledMatch(
            match_id=request.match_id,
            home_team=request.home_team,
            away_team=request.away_team,
            league=request.league,
            match_time=request.match_time,
            status=MatchStatus.SCHEDULED,
        )

        await lineup_monitor.add_match(match)

        # 모니터링 태스크 시작 (아직 시작되지 않았다면)
        global monitoring_task
        if monitoring_task is None:
            monitoring_task = asyncio.create_task(start_monitoring())

        return {
            "status": "added",
            "match_id": request.match_id,
            "home_team": request.home_team,
            "away_team": request.away_team,
            "match_time": request.match_time.isoformat(),
            "monitoring_started": monitoring_task is not None,
        }

    except Exception as e:
        logger.error(f"모니터링 추가 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/monitor/status")
async def get_monitoring_status():
    """모니터링 상태 확인"""
    try:
        matches_status = []
        for match_id, match in lineup_monitor.matches.items():
            matches_status.append(
                {
                    "match_id": match.match_id,
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "league": match.league,
                    "match_time": match.match_time.isoformat(),
                    "status": match.status.value,
                    "last_checked": match.last_checked.isoformat()
                    if match.last_checked
                    else None,
                    "has_lineup": match.lineup_data is not None,
                    "has_analysis": match.analysis_result is not None,
                }
            )

        return {
            "monitoring_active": monitoring_task is not None
            and not monitoring_task.done(),
            "total_matches": len(lineup_monitor.matches),
            "matches": matches_status,
            "last_updated": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"모니터링 상태 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/monitor/results/{match_id}")
async def get_monitoring_results(match_id: int):
    """모니터링 결과 조회"""
    try:
        match = lineup_monitor.matches.get(match_id)
        if not match:
            raise HTTPException(status_code=404, detail="경기를 찾을 수 없습니다")

        if not match.analysis_result:
            return {
                "match_id": match_id,
                "status": match.status.value,
                "analysis_available": False,
                "message": "아직 분석이 완료되지 않았습니다",
            }

        return {
            "match_id": match_id,
            "status": match.status.value,
            "analysis_available": True,
            "analysis_result": match.analysis_result,
            "lineup_data": {
                "announced_at": match.lineup_data.announced_at.isoformat()
                if match.lineup_data
                else None,
                "source": match.lineup_data.source if match.lineup_data else None,
            }
            if match.lineup_data
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"결과 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Additional APIs (Predictions, Sharp, Arbitrage, Portfolio, Live)
# ============================================================================


@app.get("/api/v1/predictions")
async def get_predictions(min_confidence: float = 0.6, limit: int = 20, skip: int = 0):
    """
    AI 예측 목록 조회

    Args:
        min_confidence: 최소 신뢰도 (홈 승률 기준, 0.0~1.0)
        limit: 최대 반환 개수
        skip: 건너뛸 개수 (페이지네이션)

    Returns:
        List: 예측 목록
    """
    try:
        async with get_session() as session:
            # PredictionLog와 Match를 조인하여 팀 정보 가져오기
            stmt = (
                select(PredictionLog, Match)
                .join(Match, PredictionLog.match_id == Match.id)
                .options(
                    joinedload(PredictionLog.match).joinedload(Match.home_team),
                    joinedload(PredictionLog.match).joinedload(Match.away_team),
                    joinedload(PredictionLog.match).joinedload(Match.league),
                )
                .where(
                    # 홈 승률이 최소 신뢰도 이상인 경기
                    (PredictionLog.prob_home >= min_confidence)
                    | (PredictionLog.prob_away >= min_confidence)
                )
                .order_by(PredictionLog.created_at.desc())
                .offset(skip)
                .limit(limit)
            )

            result = await session.execute(stmt)
            rows = result.unique().all()

            predictions = []
            for pred, match in rows:
                # 가장 높은 확률의 결과 찾기
                probs = {
                    "home": pred.prob_home,
                    "draw": pred.prob_draw,
                    "away": pred.prob_away,
                }
                predicted_outcome = max(probs, key=probs.get)
                confidence = probs[predicted_outcome]

                # 예상 Edge 계산 (value가 있으면)
                values = {
                    "home": pred.value_home or 0.0,
                    "draw": pred.value_draw or 0.0,
                    "away": pred.value_away or 0.0,
                }
                edge = values.get(predicted_outcome, 0.0)

                predictions.append(
                    {
                        "id": pred.id,
                        "match_id": pred.match_id,
                        "home_team": match.home_team.name
                        if match.home_team
                        else "Unknown",
                        "away_team": match.away_team.name
                        if match.away_team
                        else "Unknown",
                        "league": match.league.name if match.league else "Unknown",
                        "match_time": match.start_time.isoformat()
                        if match.start_time
                        else None,
                        "predicted_outcome": predicted_outcome,
                        "probabilities": {
                            "home": round(pred.prob_home, 3),
                            "draw": round(pred.prob_draw, 3),
                            "away": round(pred.prob_away, 3),
                        },
                        "confidence": round(confidence, 3),
                        "expected_scores": {
                            "home": round(pred.expected_score_home, 2)
                            if pred.expected_score_home
                            else None,
                            "away": round(pred.expected_score_away, 2)
                            if pred.expected_score_away
                            else None,
                        },
                        "edge": round(edge, 3),
                        "created_at": pred.created_at.isoformat()
                        if pred.created_at
                        else None,
                    }
                )

            return predictions

    except Exception as e:
        logger.error(f"예측 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sharp")
async def get_sharp_signals(limit: int = 10):
    """
    Sharp Money (전문가 자금) 신호 조회

    Returns:
        List: Sharp Money 신호 목록
    """
    try:
        # 실제로는 advanced_sharp_detector 서비스를 사용해야 함
        # 여기서는 간단한 구현으로 배당 급변동을 감지
        async with get_session() as session:
            # 최근 24시간 배당 히스토리에서 급변동 탐지
            from datetime import timedelta

            cutoff_time = datetime.now() - timedelta(hours=24)

            stmt = (
                select(OddsHistory)
                .where(OddsHistory.timestamp >= cutoff_time)
                .order_by(OddsHistory.timestamp.desc())
                .limit(100)
            )

            result = await session.execute(stmt)
            odds_history = result.scalars().all()

            # 간단한 급변동 감지 (실제로는 더 정교한 로직 필요)
            sharp_signals = []
            for odds in odds_history[:limit]:
                sharp_signals.append(
                    {
                        "match_id": odds.match_id,
                        "bookmaker": odds.bookmaker,
                        "home_odds": float(odds.home_odds) if odds.home_odds else None,
                        "draw_odds": float(odds.draw_odds) if odds.draw_odds else None,
                        "away_odds": float(odds.away_odds) if odds.away_odds else None,
                        "timestamp": odds.captured_at.isoformat()
                        if odds.captured_at
                        else None,
                        "signal_type": "RAPID_MOVE",  # 실제로는 감지 로직 필요
                    }
                )

            return sharp_signals

    except Exception as e:
        logger.error(f"Sharp 신호 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/arbitrage")
async def get_arbitrage_opportunities(min_profit: float = 0.02, limit: int = 10):
    """
    재정거래 (Arbitrage) 기회 조회

    Args:
        min_profit: 최소 이익률 (기본 2%)
        limit: 최대 반환 개수

    Returns:
        List: Arbitrage 기회 목록
    """
    try:
        # 실제로는 arbitrage_detector 서비스 사용
        # 여기서는 간단한 더미 응답
        return [
            {
                "match_id": 1,
                "home_team": "Manchester City",
                "away_team": "Arsenal",
                "arbitrage_profit": 0.035,
                "bookmakers": {
                    "home": {"name": "Pinnacle", "odds": 1.95},
                    "away": {"name": "Bet365", "odds": 2.20},
                },
                "detected_at": datetime.now().isoformat(),
            }
        ]

    except Exception as e:
        logger.error(f"Arbitrage 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio")
async def get_portfolio(user_id: Optional[str] = None):
    """
    포트폴리오 통계 조회

    Returns:
        Dict: 포트폴리오 정보
    """
    try:
        # 실제로는 User, Bet 테이블에서 조회
        # 여기서는 더미 데이터
        return {
            "total_bets": 342,
            "winning_bets": 212,
            "losing_bets": 130,
            "win_rate": 0.62,
            "total_profit": 8450.50,
            "roi": 0.085,
            "average_odds": 2.15,
            "current_streak": 3,
            "best_bet": {
                "match": "Liverpool vs Chelsea",
                "odds": 2.80,
                "profit": 450.00,
            },
        }

    except Exception as e:
        logger.error(f"Portfolio 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/matches/live")
async def get_live_matches():
    """
    라이브 경기 목록 조회

    Returns:
        List: 현재 진행 중인 경기 목록
    """
    try:
        async with get_session() as session:
            stmt = (
                select(Match)
                .where(Match.status.in_(["LIVE", "IN_PLAY", "HT"]))
                .order_by(Match.start_time)
                .limit(20)
            )

            result = await session.execute(stmt)
            matches = result.scalars().all()

            return [
                {
                    "id": match.id,
                    "home_team": match.home_team,
                    "away_team": match.away_team,
                    "score": f"{match.home_score}-{match.away_score}"
                    if match.home_score is not None
                    else "0-0",
                    "minute": match.minute,
                    "status": match.status,
                    "league": match.league,
                }
                for match in matches
            ]

    except Exception as e:
        logger.error(f"라이브 경기 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket Endpoints
# ============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 실시간 통신 엔드포인트

    클라이언트는 다음 형식으로 메시지를 보낼 수 있습니다:
    {
        "action": "subscribe" | "unsubscribe" | "ping",
        "channel": "odds" | "scores" | "predictions" | "alerts"
    }
    """
    # 고유 연결 ID 생성
    connection_id = str(uuid.uuid4())

    try:
        # WebSocket 연결 수락
        await ws_manager.connect(websocket, connection_id)

        # 메시지 수신 루프
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")
                channel = message.get("channel")

                if action == "subscribe" and channel:
                    success = ws_manager.subscribe(connection_id, channel)
                    await ws_manager.send_personal_message(
                        {
                            "type": "subscription",
                            "status": "success" if success else "failed",
                            "channel": channel,
                            "message": f"Subscribed to {channel}"
                            if success
                            else f"Unknown channel: {channel}",
                        },
                        websocket,
                    )

                elif action == "unsubscribe" and channel:
                    success = ws_manager.unsubscribe(connection_id, channel)
                    await ws_manager.send_personal_message(
                        {
                            "type": "subscription",
                            "status": "success" if success else "failed",
                            "channel": channel,
                            "message": f"Unsubscribed from {channel}",
                        },
                        websocket,
                    )

                elif action == "ping":
                    await ws_manager.send_personal_message(
                        {"type": "pong", "timestamp": datetime.now().isoformat()},
                        websocket,
                    )

                else:
                    await ws_manager.send_personal_message(
                        {
                            "type": "error",
                            "message": "Unknown action or missing channel",
                        },
                        websocket,
                    )

            except json.JSONDecodeError:
                await ws_manager.send_personal_message(
                    {"type": "error", "message": "Invalid JSON format"}, websocket
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(connection_id)


@app.post("/api/v1/broadcast/{channel}")
async def broadcast_message(channel: str, message: dict):
    """
    특정 채널에 메시지 브로드캐스트 (관리자용 또는 내부 서비스용)

    Args:
        channel: odds, scores, predictions, alerts
        message: 브로드캐스트할 메시지 (dict)

    Returns:
        성공 여부
    """
    try:
        # Redis를 통해 메시지 발행 (다른 서버 인스턴스에도 전파)
        await ws_manager.publish_to_redis(channel, message)

        # 현재 인스턴스의 클라이언트들에게도 즉시 브로드캐스트
        await ws_manager.broadcast(channel, message)

        return {"status": "success", "channel": channel, "message": "Broadcast sent"}

    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Helper Functions
# ============================================================================


def generate_recommendation(analysis_result: MatchAnalysis) -> Dict:
    """분석 결과 기반 추천 생성"""
    probs = analysis_result.predicted_probabilities
    best_outcome = max(probs.items(), key=lambda x: x[1])

    # Kelly Criterion 기반 베팅 금액 계산
    edge = best_outcome[1] - (1 / 2.5)  # 가정: 시장 배당 2.50
    if edge <= 0:
        stake_percentage = 0.0
    else:
        kelly_fraction = edge / 2.5
        stake_percentage = min(
            0.05, max(0.01, kelly_fraction * analysis_result.confidence_score)
        )

    return {
        "predicted_outcome": best_outcome[0].value,
        "probability": round(best_outcome[1], 4),
        "recommended_odds": round(analysis_result.own_odds[best_outcome[0]], 2),
        "confidence": round(analysis_result.confidence_score, 3),
        "suggested_stake_percentage": round(stake_percentage, 4),
        "suggested_stake_amount": f"{stake_percentage * 100:.1f}% of bankroll",
        "value_detected": edge > 0,
        "edge_percentage": round(edge * 100, 2) if edge > 0 else 0.0,
    }


async def start_monitoring():
    """모니터링 시작"""
    try:
        await lineup_monitor.monitor_matches()
    except asyncio.CancelledError:
        logger.info("모니터링 종료")
    except Exception as e:
        logger.error(f"모니터링 중 오류: {e}")


# ============================================================================
# Startup & Shutdown Events
# ============================================================================


async def sync_kspo_data():
    """KSPO API에서 최신 경기 데이터 동기화"""
    global last_kspo_sync
    try:
        from src.services.kspo_api_client import KSPOApiClient

        kspo_client = KSPOApiClient()
        today = datetime.now()
        total_saved = 0

        # 오늘부터 향후 7일간 경기 동기화
        for i in range(8):
            target_date = (today + timedelta(days=i)).strftime("%Y%m%d")
            matches = await kspo_client.get_match_list(match_ymd=target_date)
            if matches:
                count = await kspo_client.save_matches_to_db(matches)
                total_saved += count

        last_kspo_sync = datetime.now(timezone.utc)
        logger.info(f"✅ KSPO 데이터 동기화 완료: {total_saved}개 경기 처리")
        return total_saved
    except Exception as e:
        logger.error(f"KSPO 데이터 동기화 실패: {e}")
        return 0


async def kspo_sync_loop():
    """KSPO 데이터 주기적 동기화 (1시간 간격)"""
    while True:
        try:
            await asyncio.sleep(3600)  # 1시간 대기
            await sync_kspo_data()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"KSPO 동기화 루프 오류: {e}")
            await asyncio.sleep(60)  # 오류 시 1분 후 재시도


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행"""
    global odds_monitor, kspo_sync_task

    logger.info("=" * 60)
    logger.info("스포츠 분석 AI 통합 API 서버 시작")
    logger.info("=" * 60)
    logger.info("✅ AI 배당 생성 시스템 활성화")
    logger.info("✅ 프로토 분석 시스템 활성화")
    logger.info("✅ 대시보드 API 활성화")
    logger.info("✅ 채팅 에이전트 활성화")

    # 서버 시작 시 KSPO 데이터 즉시 동기화
    try:
        await sync_kspo_data()
        logger.info("✅ KSPO 경기 데이터 초기 동기화 완료")
    except Exception as e:
        logger.warning(f"⚠️  KSPO 초기 동기화 실패: {e}")

    # KSPO 주기적 동기화 태스크 시작
    kspo_sync_task = asyncio.create_task(kspo_sync_loop())
    logger.info("✅ KSPO 자동 동기화 활성화 (1시간 간격)")

    # WebSocket & Redis 초기화
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        await ws_manager.initialize_redis(redis_url)
        logger.info("✅ WebSocket & Redis Pub/Sub 활성화")
    except Exception as e:
        logger.warning(f"⚠️  Redis 초기화 실패 (선택사항): {e}")

    # 실시간 배당 모니터 초기화 및 시작
    try:
        poll_interval = int(os.getenv("ODDS_POLL_INTERVAL", "30"))
        odds_monitor = initialize_odds_monitor(async_session, poll_interval)
        await odds_monitor.start()
        logger.info(f"✅ 실시간 배당 모니터 활성화 (폴링 간격: {poll_interval}초)")
    except Exception as e:
        logger.warning(f"⚠️  배당 모니터 초기화 실패: {e}")

    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 실행"""
    logger.info("스포츠 분석 AI 통합 API 서버 종료")

    # 모니터링 태스크 종료
    if monitoring_task:
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass

    # KSPO 동기화 태스크 종료
    if kspo_sync_task:
        kspo_sync_task.cancel()
        try:
            await kspo_sync_task
        except asyncio.CancelledError:
            pass
        logger.info("✅ KSPO 동기화 태스크 종료")

    # 배당 모니터 종료
    if odds_monitor:
        await odds_monitor.stop()
        logger.info("✅ 배당 모니터 종료")

    # WebSocket 매니저 종료
    await ws_manager.shutdown()


# ============================================================================
# Toto Game API (토토 게임 - 14경기 패키지)
# ============================================================================

toto_service = TotoService()


@app.get("/api/v1/toto/soccer")
async def get_toto_soccer(round_number: Optional[int] = None):
    """
    축구 승무패 (14경기 패키지)

    Query Parameters:
        round_number: 회차 번호 (None이면 최신 회차)
    """
    try:
        async with get_session() as session:
            result = await toto_service.get_toto_package(
                session=session,
                game_type=TotoGame.SOCCER_WDL,
                round_number=round_number,
            )
            return result
    except Exception as e:
        logger.error(f"축구 승무패 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/toto/basketball")
async def get_toto_basketball(round_number: Optional[int] = None):
    """
    농구 승5패 (14경기 패키지)

    Query Parameters:
        round_number: 회차 번호 (None이면 최신 회차)
    """
    try:
        async with get_session() as session:
            result = await toto_service.get_toto_package(
                session=session,
                game_type=TotoGame.BASKETBALL_W5L,
                round_number=round_number,
            )
            return result
    except Exception as e:
        logger.error(f"농구 승5패 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/toto/baseball")
async def get_toto_baseball(round_number: Optional[int] = None):
    """
    야구 승1패 (14경기 패키지)

    Query Parameters:
        round_number: 회차 번호 (None이면 최신 회차)
    """
    try:
        async with get_session() as session:
            result = await toto_service.get_toto_package(
                session=session,
                game_type=TotoGame.BASEBALL_W1L,
                round_number=round_number,
            )
            return result
    except Exception as e:
        logger.error(f"야구 승1패 조회 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Perplexity AI API - 실시간 스포츠 정보 검색
# ============================================================================


class PerplexityRequest(BaseModel):
    """Perplexity AI 요청 모델"""

    query: str
    sport: Optional[str] = "soccer"  # soccer, basketball, baseball


class PerplexityMatchPreviewRequest(BaseModel):
    """경기 프리뷰 요청 모델"""

    home_team: str
    away_team: str
    sport: Optional[str] = "soccer"
    league: Optional[str] = None


class PerplexityOddsAnalysisRequest(BaseModel):
    """배당 분석 요청 모델"""

    home_team: str
    away_team: str
    odds: Dict[str, float]  # {"home": 2.10, "draw": 3.40, "away": 3.20}
    sport: Optional[str] = "soccer"


@app.post("/api/v1/perplexity/ask")
async def perplexity_ask(request: PerplexityRequest):
    """
    Perplexity AI에 스포츠 관련 질문

    실시간 웹 검색 + AI 분석으로 최신 스포츠 정보 제공
    """
    try:
        from src.clients.perplexity import create_perplexity_client

        client = create_perplexity_client(settings.perplexity_api_key)
        response = await client.ask(request.query)

        return {
            "success": True,
            "data": {
                "content": response.content,
                "citations": response.citations,
                "model": response.model,
            },
        }
    except Exception as e:
        logger.error(f"Perplexity AI 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/perplexity/team-news")
async def perplexity_team_news(team_name: str, sport: str = "soccer"):
    """
    팀 최신 뉴스 조회

    Parameters:
        team_name: 팀 이름 (예: "Manchester United", "LA Lakers")
        sport: 종목 (soccer, basketball, baseball)
    """
    try:
        from src.clients.perplexity import create_perplexity_client

        client = create_perplexity_client(settings.perplexity_api_key)
        response = await client.get_team_news(team_name, sport)

        return {
            "success": True,
            "data": {
                "team": team_name,
                "sport": sport,
                "news": response.content,
                "citations": response.citations,
            },
        }
    except Exception as e:
        logger.error(f"팀 뉴스 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/perplexity/match-preview")
async def perplexity_match_preview(request: PerplexityMatchPreviewRequest):
    """
    경기 프리뷰 (양팀 분석, 상대 전적, 부상자 등)
    """
    try:
        from src.clients.perplexity import create_perplexity_client

        client = create_perplexity_client(settings.perplexity_api_key)
        response = await client.get_match_preview(
            home_team=request.home_team,
            away_team=request.away_team,
            sport=request.sport,
            league=request.league,
        )

        return {
            "success": True,
            "data": {
                "home_team": request.home_team,
                "away_team": request.away_team,
                "preview": response.content,
                "citations": response.citations,
            },
        }
    except Exception as e:
        logger.error(f"경기 프리뷰 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/perplexity/odds-analysis")
async def perplexity_odds_analysis(request: PerplexityOddsAnalysisRequest):
    """
    배당 가치 분석

    현재 배당률과 실제 확률을 비교하여 가치 베팅 기회 분석
    """
    try:
        from src.clients.perplexity import create_perplexity_client

        client = create_perplexity_client(settings.perplexity_api_key)
        response = await client.analyze_odds_value(
            home_team=request.home_team,
            away_team=request.away_team,
            odds=request.odds,
            sport=request.sport,
        )

        return {
            "success": True,
            "data": {
                "home_team": request.home_team,
                "away_team": request.away_team,
                "odds": request.odds,
                "analysis": response.content,
                "citations": response.citations,
            },
        }
    except Exception as e:
        logger.error(f"배당 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AI 신뢰도 및 마킹 최적화 API
# ============================================================================


class MarkingOptimizeRequest(BaseModel):
    """마킹 최적화 요청"""

    matches: List[Dict]  # 예측 결과 리스트
    budget: int = 100000  # 예산 (기본 10만원)
    strategy: str = "balanced"  # aggressive, balanced, conservative


class TeamStatsRequest(BaseModel):
    """팀 통계 요청"""

    team_name: str
    league_id: int = 39  # 기본: 프리미어리그


@app.get("/api/v1/analysis/confidence/{match_id}")
async def get_match_confidence(match_id: int):
    """
    경기 예측 신뢰도 점수 조회

    Returns:
        - total_score: 종합 신뢰도 (0-100)
        - model_agreement: 모델 일치도
        - data_quality: 데이터 품질
        - probability_clarity: 확률 명확성
        - form_consistency: 폼 일관성
        - confidence_level: 높음/중간/낮음
        - recommendation_strength: 강력추천/추천/보류/회피
    """
    try:
        from src.services.confidence_scorer import ConfidenceScorer
        from src.services.predictor import AdvancedStatisticalPredictor

        async with get_session() as session:
            # 경기 조회
            result = await session.execute(
                select(Match)
                .options(joinedload(Match.home_team), joinedload(Match.away_team))
                .where(Match.id == match_id)
            )
            match = result.scalar()

            if not match:
                raise HTTPException(status_code=404, detail="경기를 찾을 수 없습니다")

            # 예측 수행
            predictor = AdvancedStatisticalPredictor()

            home_stats = {
                "goals_scored_avg": 1.5,
                "goals_conceded_avg": 1.0,
                "momentum": 0.7,
            }
            away_stats = {
                "goals_scored_avg": 1.2,
                "goals_conceded_avg": 1.2,
                "momentum": 0.5,
            }

            prediction = predictor.predict_score_probabilities(home_stats, away_stats)

            # 신뢰도 계산
            scorer = ConfidenceScorer()
            confidence = scorer.calculate(
                prediction, home_stats=home_stats, away_stats=away_stats
            )

            return {
                "success": True,
                "match_id": match_id,
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "prediction": prediction,
                "confidence": {
                    "total_score": confidence.total_score,
                    "model_agreement": confidence.model_agreement,
                    "data_quality": confidence.data_quality,
                    "probability_clarity": confidence.probability_clarity,
                    "form_consistency": confidence.form_consistency,
                    "confidence_level": confidence.confidence_level,
                    "recommendation_strength": confidence.recommendation_strength,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"신뢰도 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/toto/optimize-marking")
async def optimize_toto_marking(request: MarkingOptimizeRequest):
    """
    토토 14경기 마킹 최적화

    예산 내에서 최적의 단통/복수/지우개 조합 생성

    Args:
        matches: 14경기 예측 정보
        budget: 예산 (원)
        strategy: 전략 유형 (aggressive, balanced, conservative)

    Returns:
        - strategy: 경기별 마킹 정보
        - total_combinations: 총 조합 수
        - total_cost: 총 투자 금액
        - expected_probability: 예상 적중률
        - budget_status: 예산 상태
    """
    try:
        from src.services.marking_optimizer import generate_toto_strategy

        result, report = generate_toto_strategy(
            matches=request.matches, budget=request.budget, strategy=request.strategy
        )

        return {
            "success": True,
            "optimization": {
                "total_combinations": result.total_combinations,
                "total_cost": result.total_cost,
                "expected_probability": result.expected_probability,
                "expected_roi": result.expected_roi,
                "budget_status": result.budget_status,
                "optimization_applied": result.optimization_applied,
            },
            "matches": [
                {
                    "match_index": m.match_index,
                    "home_team": m.home_team,
                    "away_team": m.away_team,
                    "marking_type": m.marking_type,
                    "selections": m.selections,
                    "icon": m.icon,
                    "reason": m.reason,
                    "confidence": m.confidence,
                }
                for m in result.matches
            ],
            "report": report,
        }

    except Exception as e:
        logger.error(f"마킹 최적화 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/team/stats")
async def get_team_statistics(request: TeamStatsRequest):
    """
    팀 통계 조회

    API-Football에서 팀 시즌 통계, 최근 경기 결과, 폼/모멘텀 반환
    """
    try:
        from src.services.team_stats_collector import get_team_stats

        stats = await get_team_stats(
            team_name=request.team_name, league_id=request.league_id, use_api=True
        )

        return {
            "success": True,
            "team": stats.team_name,
            "statistics": {
                "matches_played": stats.matches_played,
                "wins": stats.wins,
                "draws": stats.draws,
                "losses": stats.losses,
                "goals_scored": stats.goals_scored,
                "goals_conceded": stats.goals_conceded,
                "goals_scored_avg": stats.goals_scored_avg,
                "goals_conceded_avg": stats.goals_conceded_avg,
                "home_record": {
                    "wins": stats.home_wins,
                    "draws": stats.home_draws,
                    "losses": stats.home_losses,
                },
                "away_record": {
                    "wins": stats.away_wins,
                    "draws": stats.away_draws,
                    "losses": stats.away_losses,
                },
                "xg": stats.xg,
                "xga": stats.xga,
                "recent_form": stats.recent_form,
                "momentum": stats.momentum,
            },
        }

    except Exception as e:
        logger.error(f"팀 통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/toto/round/{round_number}/strategy")
async def get_round_strategy(
    round_number: int, budget: int = 100000, strategy: str = "balanced"
):
    """
    특정 회차의 AI 마킹 전략 조회

    회차 번호로 경기 목록을 가져와서 자동으로 최적 마킹 전략 생성
    """
    try:
        from src.services.soccer_analyzer import SoccerAnalyzer
        from src.services.marking_optimizer import generate_toto_strategy
        from src.services.confidence_scorer import ConfidenceScorer

        # 1. 회차 경기 분석
        analyzer = SoccerAnalyzer()
        analysis = await analyzer.analyze_round(round_number)

        # 2. 마킹 최적화용 데이터 준비
        matches_for_optimization = []
        scorer = ConfidenceScorer()

        for match in analysis.matches:
            probs = match.get(
                "probabilities", {"home": 0.33, "draw": 0.33, "away": 0.33}
            )

            # 신뢰도 계산
            confidence_result = scorer.calculate({"probabilities": probs})

            matches_for_optimization.append(
                {
                    "home": match.get("home"),
                    "away": match.get("away"),
                    "prediction": probs,
                    "confidence": confidence_result.total_score,
                }
            )

        # 3. 마킹 최적화
        result, report = generate_toto_strategy(
            matches=matches_for_optimization, budget=budget, strategy=strategy
        )

        return {
            "success": True,
            "round_number": round_number,
            "category": analysis.category,
            "optimization": {
                "total_combinations": result.total_combinations,
                "total_cost": result.total_cost,
                "expected_probability": result.expected_probability,
                "budget_status": result.budget_status,
            },
            "matches": [
                {
                    "match_index": m.match_index,
                    "home_team": m.home_team,
                    "away_team": m.away_team,
                    "marking_type": m.marking_type,
                    "selections": m.selections,
                    "icon": m.icon,
                    "reason": m.reason,
                    "confidence": m.confidence,
                }
                for m in result.matches
            ],
            "summary": analysis.summary,
            "report": report,
        }

    except Exception as e:
        logger.error(f"회차 전략 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 새로 추가된 분석 모듈 API (D-02, D-03, A-02, G-01~G-05, I-01, A-04)
# ============================================================================

# Import new modules (with fallback)
try:
    from src.services.recent_matches_collector import get_recent_matches_collector
    from src.services.h2h_collector import get_h2h_collector
    from src.services.ensemble_model import get_ensemble_model
    from src.services.market_predictor import get_market_predictor
    from src.services.sport_predictors import (
        get_baseball_predictor,
        get_basketball_predictor,
        get_record_predictor,
    )
    from src.services.backtester import get_backtester
    from src.services.cache import get_cache_manager
except ImportError as e:
    logger.warning(f"New modules import failed: {e}")


# D-02: 최근 경기 결과 API
@app.get("/api/v1/team/{team_id}/recent-matches")
async def get_team_recent_matches(team_id: int, count: int = 5):
    """팀의 최근 경기 결과 조회"""
    try:
        collector = get_recent_matches_collector()
        matches = await collector.get_team_recent_matches(team_id, count)
        form = collector.analyze_form(matches)

        return {
            "success": True,
            "team_id": team_id,
            "matches": [
                {
                    "date": m.date,
                    "opponent": m.opponent,
                    "home_score": m.home_score,
                    "away_score": m.away_score,
                    "result": m.result.value,
                    "is_home": m.is_home,
                    "league": m.league,
                }
                for m in matches
            ],
            "form_analysis": {
                "form_string": form.form_string,
                "points": form.points,
                "wins": form.wins,
                "draws": form.draws,
                "losses": form.losses,
                "goals_scored": form.goals_scored,
                "goals_conceded": form.goals_conceded,
                "avg_goals_scored": form.avg_goals_scored,
                "avg_goals_conceded": form.avg_goals_conceded,
                "clean_sheets": form.clean_sheets,
                "trend": form.trend,
            },
            "chart_data": collector.to_chart_data(form),
        }
    except Exception as e:
        logger.error(f"최근 경기 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# D-03: 상대전적 H2H API
@app.get("/api/v1/h2h/{home_team_id}/{away_team_id}")
async def get_h2h_analysis(
    home_team_id: int,
    away_team_id: int,
    home_team_name: str = "Home",
    away_team_name: str = "Away",
    limit: int = 10,
):
    """두 팀 간 상대전적 분석"""
    try:
        collector = get_h2h_collector()
        result = await collector.get_full_h2h_analysis(
            home_team_id, away_team_id, home_team_name, away_team_name, limit
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"상대전적 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# A-02: 앙상블 예측 API
class EnsemblePredictionRequest(BaseModel):
    home_avg_goals: float = 1.5
    away_avg_goals: float = 1.3
    home_avg_conceded: float = 1.0
    away_avg_conceded: float = 1.2
    home_elo: float = 1500
    away_elo: float = 1500
    home_form: str = ""
    away_form: str = ""
    h2h_home_wins: int = 0
    h2h_away_wins: int = 0
    h2h_draws: int = 0


@app.post("/api/v1/predict/ensemble")
async def ensemble_prediction(request: EnsemblePredictionRequest):
    """앙상블 ML 모델 예측"""
    try:
        model = get_ensemble_model()
        prediction = model.predict(
            home_avg_goals=request.home_avg_goals,
            away_avg_goals=request.away_avg_goals,
            home_avg_conceded=request.home_avg_conceded,
            away_avg_conceded=request.away_avg_conceded,
            home_elo=request.home_elo,
            away_elo=request.away_elo,
            home_form=request.home_form,
            away_form=request.away_form,
            h2h_home_wins=request.h2h_home_wins,
            h2h_away_wins=request.h2h_away_wins,
            h2h_draws=request.h2h_draws,
        )
        return {"success": True, **model.to_dict(prediction)}
    except Exception as e:
        logger.error(f"앙상블 예측 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# G-01/G-02: 핸디캡/언더오버 예측 API
class MarketPredictionRequest(BaseModel):
    expected_home_goals: float
    expected_away_goals: float
    handicap_line: float = -0.5
    over_under_line: float = 2.5


@app.post("/api/v1/predict/markets")
async def market_prediction(request: MarketPredictionRequest):
    """핸디캡/언더오버 마켓 예측"""
    try:
        predictor = get_market_predictor()
        prediction = predictor.predict_all_markets(
            request.expected_home_goals,
            request.expected_away_goals,
            request.handicap_line,
            request.over_under_line,
        )
        return {"success": True, **predictor.to_dict(prediction)}
    except Exception as e:
        logger.error(f"마켓 예측 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# G-03: 야구 승1패 예측 API
class BaseballPredictionRequest(BaseModel):
    home_team: str
    away_team: str
    home_pitcher_era: float = 4.00
    away_pitcher_era: float = 4.00
    home_team_ops: float = 0.750
    away_team_ops: float = 0.750
    home_last10: str = "5-5"
    away_last10: str = "5-5"


@app.post("/api/v1/predict/baseball")
async def baseball_prediction(request: BaseballPredictionRequest):
    """야구 승1패 예측"""
    try:
        predictor = get_baseball_predictor()
        result = predictor.predict(
            home_team=request.home_team,
            away_team=request.away_team,
            home_pitcher_era=request.home_pitcher_era,
            away_pitcher_era=request.away_pitcher_era,
            home_team_ops=request.home_team_ops,
            away_team_ops=request.away_team_ops,
            home_last10=request.home_last10,
            away_last10=request.away_last10,
        )
        return {
            "success": True,
            "home_win_prob": result.home_win_prob,
            "away_win_prob": result.away_win_prob,
            "recommended": result.recommended,
            "confidence": result.confidence,
            "run_line": result.run_line,
            "over_under_line": result.over_under_line,
            "over_prob": result.over_prob,
            "under_prob": result.under_prob,
            "expected_home_runs": result.expected_home_runs,
            "expected_away_runs": result.expected_away_runs,
            "reasoning": result.reasoning,
        }
    except Exception as e:
        logger.error(f"야구 예측 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# G-04: 농구 승5패 예측 API
class BasketballPredictionRequest(BaseModel):
    home_team: str
    away_team: str
    home_off_rating: float = 110.0
    away_off_rating: float = 110.0
    home_def_rating: float = 110.0
    away_def_rating: float = 110.0
    home_last10: str = "5-5"
    away_last10: str = "5-5"
    spread: float = 0.0
    total_line: float = 210.0


@app.post("/api/v1/predict/basketball")
async def basketball_prediction(request: BasketballPredictionRequest):
    """농구 승5패 예측"""
    try:
        predictor = get_basketball_predictor()
        result = predictor.predict(
            home_team=request.home_team,
            away_team=request.away_team,
            home_off_rating=request.home_off_rating,
            away_off_rating=request.away_off_rating,
            home_def_rating=request.home_def_rating,
            away_def_rating=request.away_def_rating,
            home_last10=request.home_last10,
            away_last10=request.away_last10,
            spread=request.spread,
            total_line=request.total_line,
        )
        return {
            "success": True,
            "home_win_prob": result.home_win_prob,
            "away_win_prob": result.away_win_prob,
            "recommended": result.recommended,
            "confidence": result.confidence,
            "spread": result.spread,
            "spread_home_prob": result.spread_home_prob,
            "spread_away_prob": result.spread_away_prob,
            "total_line": result.total_line,
            "over_prob": result.over_prob,
            "under_prob": result.under_prob,
            "expected_home_score": result.expected_home_score,
            "expected_away_score": result.expected_away_score,
            "quarter_predictions": result.quarter_predictions,
            "reasoning": result.reasoning,
        }
    except Exception as e:
        logger.error(f"농구 예측 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# G-05: 기록식 예측 API
class RecordPredictionRequest(BaseModel):
    record_type: str  # "corners" or "cards"
    home_team: str
    away_team: str
    home_avg_for: float = 5.0
    home_avg_against: float = 4.5
    away_avg_for: float = 5.0
    away_avg_against: float = 4.5
    line: float = 10.5
    league: str = "default"


@app.post("/api/v1/predict/record")
async def record_prediction(request: RecordPredictionRequest):
    """기록식 예측 (코너킥/카드)"""
    try:
        predictor = get_record_predictor()

        if request.record_type == "corners":
            result = predictor.predict_corners(
                home_team=request.home_team,
                away_team=request.away_team,
                home_corners_for=request.home_avg_for,
                home_corners_against=request.home_avg_against,
                away_corners_for=request.away_avg_for,
                away_corners_against=request.away_avg_against,
                league=request.league,
                line=request.line,
            )
        elif request.record_type == "cards":
            result = predictor.predict_cards(
                home_team=request.home_team,
                away_team=request.away_team,
                home_cards_for=request.home_avg_for,
                home_cards_against=request.home_avg_against,
                away_cards_for=request.away_avg_for,
                away_cards_against=request.away_avg_against,
                league=request.league,
                line=request.line,
            )
        else:
            raise HTTPException(
                status_code=400, detail="Invalid record_type. Use 'corners' or 'cards'"
            )

        return {
            "success": True,
            "record_type": result.record_type,
            "line": result.line,
            "over_prob": result.over_prob,
            "under_prob": result.under_prob,
            "recommended": result.recommended,
            "confidence": result.confidence,
            "expected_value": result.expected_value,
            "reasoning": result.reasoning,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"기록식 예측 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# A-04: 백테스팅 API
@app.get("/api/v1/backtest/summary")
async def get_backtest_summary():
    """백테스팅 요약"""
    try:
        backtester = get_backtester()
        summary = backtester.get_summary()
        return {"success": True, **summary}
    except Exception as e:
        logger.error(f"백테스팅 요약 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BacktestFilterRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_confidence: float = 0
    max_confidence: float = 100
    leagues: Optional[List[str]] = None


@app.post("/api/v1/backtest/run")
async def run_backtest(request: BacktestFilterRequest):
    """백테스팅 실행"""
    try:
        backtester = get_backtester()
        result = backtester.run_backtest(
            start_date=request.start_date,
            end_date=request.end_date,
            min_confidence=request.min_confidence,
            max_confidence=request.max_confidence,
            leagues=request.leagues,
        )
        return {"success": True, **backtester.to_dict(result)}
    except Exception as e:
        logger.error(f"백테스팅 실행 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# I-01: 캐시 관리 API
@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """캐시 통계"""
    try:
        cache = get_cache_manager()
        await cache.initialize()
        return {"success": True, **cache.stats()}
    except Exception as e:
        logger.error(f"캐시 통계 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/cache/clear")
async def clear_cache(pattern: str = "sports:*"):
    """캐시 초기화"""
    try:
        cache = get_cache_manager()
        await cache.initialize()
        await cache.clear(pattern)
        return {"success": True, "message": f"Cache cleared for pattern: {pattern}"}
    except Exception as e:
        logger.error(f"캐시 초기화 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# D-04: 선수 부상/출장정지 API
try:
    from src.services.injury_tracker import get_injury_tracker
except ImportError as e:
    logger.warning(f"Injury tracker import failed: {e}")


@app.get("/api/v1/team/{team_id}/injuries")
async def get_team_injuries(team_id: int, team_name: str = ""):
    """팀 부상자 목록 조회"""
    try:
        tracker = get_injury_tracker()
        injuries = await tracker.get_team_injuries(team_id, team_name)
        report = tracker.analyze_team_injuries(injuries, team_name)

        return {
            "success": True,
            "team_id": team_id,
            "team_name": team_name,
            "total_out": report.total_out,
            "total_doubtful": report.total_doubtful,
            "total_suspended": report.total_suspended,
            "impact_score": report.impact_score,
            "key_absences": report.key_absences,
            "position_impact": report.position_impact,
            "injured_players": [
                {
                    "name": p.player_name,
                    "position": p.position.value,
                    "status": p.status.value,
                    "reason": p.reason,
                    "importance": p.importance,
                    "expected_return": p.expected_return,
                }
                for p in injuries
            ],
        }
    except Exception as e:
        logger.error(f"팀 부상자 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/match/{home_team_id}/{away_team_id}/injuries")
async def get_match_injury_analysis(
    home_team_id: int,
    away_team_id: int,
    home_team_name: str = "Home",
    away_team_name: str = "Away",
):
    """경기 부상 영향 분석"""
    try:
        tracker = get_injury_tracker()
        analysis = await tracker.analyze_match_injuries(
            home_team_id, away_team_id, home_team_name, away_team_name
        )
        return {"success": True, **tracker.to_dict(analysis)}
    except Exception as e:
        logger.error(f"경기 부상 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
