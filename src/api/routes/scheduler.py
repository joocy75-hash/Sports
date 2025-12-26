"""
자동 분석 스케줄러 API Router

스케줄러 관리 엔드포인트
- 스케줄 조회/변경
- 수동 분석 실행
- 텔레그램 테스트
"""

import logging
from typing import Optional
from datetime import time

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.services.auto_scheduler import AutoScheduler
from src.services.telegram_bot import TelegramNotifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["Auto Scheduler"])

# 전역 스케줄러 인스턴스
scheduler: Optional[AutoScheduler] = None


# ============================================================================
# Request/Response Models
# ============================================================================

class ScheduleUpdateRequest(BaseModel):
    """스케줄 변경 요청"""
    game_type: str = Field(..., description="승5패 or 승무패")
    hour: int = Field(..., ge=0, le=23, description="시 (0-23)")
    minute: int = Field(..., ge=0, le=59, description="분 (0-59)")


class ManualAnalysisRequest(BaseModel):
    """수동 분석 요청"""
    game_type: str = Field(..., description="승5패 or 승무패")


class SchedulerStatusResponse(BaseModel):
    """스케줄러 상태 응답"""
    running: bool
    schedules: dict
    api_base_url: str


class SchedulerActionResponse(BaseModel):
    """스케줄러 액션 응답"""
    success: bool
    message: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/start", response_model=SchedulerActionResponse)
async def start_scheduler(background_tasks: BackgroundTasks):
    """
    자동 분석 스케줄러 시작

    백그라운드에서 실행되며, 설정된 시간에 자동으로 분석 수행
    """
    global scheduler

    if scheduler and scheduler.running:
        return SchedulerActionResponse(
            success=False,
            message="스케줄러가 이미 실행 중입니다"
        )

    try:
        if scheduler is None:
            scheduler = AutoScheduler()

        # 백그라운드에서 실행
        background_tasks.add_task(scheduler.start)

        return SchedulerActionResponse(
            success=True,
            message="자동 분석 스케줄러가 시작되었습니다"
        )

    except Exception as e:
        logger.error(f"스케줄러 시작 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop", response_model=SchedulerActionResponse)
async def stop_scheduler():
    """
    자동 분석 스케줄러 중지
    """
    global scheduler

    if scheduler is None or not scheduler.running:
        return SchedulerActionResponse(
            success=False,
            message="실행 중인 스케줄러가 없습니다"
        )

    try:
        scheduler.stop()

        return SchedulerActionResponse(
            success=True,
            message="자동 분석 스케줄러가 중지되었습니다"
        )

    except Exception as e:
        logger.error(f"스케줄러 중지 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """
    스케줄러 상태 조회
    """
    global scheduler

    if scheduler is None:
        scheduler = AutoScheduler()

    return SchedulerStatusResponse(
        running=scheduler.running,
        schedules=scheduler.get_schedules(),
        api_base_url=scheduler.api_base_url
    )


@router.put("/schedule", response_model=SchedulerActionResponse)
async def update_schedule(request: ScheduleUpdateRequest):
    """
    스케줄 시간 변경

    예: {"game_type": "승5패", "hour": 9, "minute": 30}
    """
    global scheduler

    if scheduler is None:
        scheduler = AutoScheduler()

    try:
        scheduler.set_schedule(
            game_type=request.game_type,
            hour=request.hour,
            minute=request.minute
        )

        return SchedulerActionResponse(
            success=True,
            message=f"{request.game_type} 스케줄이 {request.hour:02d}:{request.minute:02d}로 변경되었습니다"
        )

    except Exception as e:
        logger.error(f"스케줄 변경 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-run", response_model=SchedulerActionResponse)
async def run_manual_analysis(request: ManualAnalysisRequest, background_tasks: BackgroundTasks):
    """
    수동으로 특정 게임 타입 분석 실행

    스케줄과 무관하게 즉시 분석을 시작합니다
    """
    global scheduler

    if scheduler is None:
        scheduler = AutoScheduler()

    try:
        # 백그라운드에서 실행
        background_tasks.add_task(scheduler.run_manual_analysis, request.game_type)

        return SchedulerActionResponse(
            success=True,
            message=f"{request.game_type} 수동 분석이 시작되었습니다 (백그라운드 실행)"
        )

    except Exception as e:
        logger.error(f"수동 분석 실행 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test-telegram", response_model=SchedulerActionResponse)
async def test_telegram():
    """
    텔레그램 봇 연결 테스트

    설정된 TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID로 테스트 메시지 전송
    """
    global scheduler

    if scheduler is None:
        scheduler = AutoScheduler()

    try:
        success = await scheduler.run_test()

        if success:
            return SchedulerActionResponse(
                success=True,
                message="텔레그램 연결 성공! 메시지를 확인하세요"
            )
        else:
            return SchedulerActionResponse(
                success=False,
                message="텔레그램 연결 실패. 환경변수 TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 확인하세요"
            )

    except Exception as e:
        logger.error(f"텔레그램 테스트 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules")
async def get_schedules():
    """
    현재 설정된 스케줄 조회

    Returns:
        {'승5패': '09:00', '승무패': '10:00'}
    """
    global scheduler

    if scheduler is None:
        scheduler = AutoScheduler()

    return scheduler.get_schedules()
