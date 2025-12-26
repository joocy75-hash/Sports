"""
Chat API용 Pydantic 모델들
타입 안전성과 자동 검증을 제공합니다.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ChatMessage(BaseModel):
    """
    대화 메시지 모델
    """
    role: str = Field(..., description="메시지 역할 (user | assistant | function)")
    content: str = Field(..., description="메시지 내용")
    timestamp: Optional[str] = Field(None, description="타임스탬프 (ISO format)")
    function_call: Optional[Dict[str, Any]] = Field(None, description="Function Call 정보")
    function_response: Optional[Dict[str, Any]] = Field(None, description="Function 응답")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "오늘 맨시티 경기 언제야?",
                "timestamp": "2025-12-17T15:30:00"
            }
        }


class ChatRequest(BaseModel):
    """
    채팅 요청 모델
    """
    query: str = Field(..., min_length=1, max_length=1000, description="사용자 질문")
    session_id: Optional[str] = Field(None, description="세션 ID (대화 컨텍스트 유지용)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="추가 컨텍스트")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "오늘 경기 일정 알려줘",
                "session_id": "user_12345_20251217",
                "context": {}
            }
        }


class FunctionCallInfo(BaseModel):
    """
    Function Call 정보
    """
    name: str = Field(..., description="호출된 함수 이름")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="함수 인자")
    result: Optional[Any] = Field(None, description="함수 실행 결과")


class ChatResponse(BaseModel):
    """
    채팅 응답 모델
    """
    response: str = Field(..., description="AI 응답 텍스트")
    session_id: str = Field(..., description="세션 ID")
    function_used: Optional[str] = Field(None, description="사용된 함수 이름 (있는 경우)")
    function_result: Optional[Any] = Field(None, description="함수 실행 결과 (있는 경우)")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="응답 생성 시간")
    tokens_used: Optional[int] = Field(None, description="사용된 토큰 수")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "오늘 맨시티 경기는 오후 3시에 있습니다.",
                "session_id": "user_12345_20251217",
                "function_used": "get_match_by_teams",
                "function_result": {
                    "home_team": "Manchester City",
                    "away_team": "Arsenal",
                    "start_time": "2025-12-17T15:00:00"
                },
                "timestamp": "2025-12-17T14:30:00",
                "tokens_used": 450
            }
        }


class ChatHistoryResponse(BaseModel):
    """
    대화 히스토리 응답 모델
    """
    session_id: str = Field(..., description="세션 ID")
    messages: List[ChatMessage] = Field(default_factory=list, description="메시지 목록")
    message_count: int = Field(..., description="총 메시지 수")
    last_activity: Optional[str] = Field(None, description="마지막 활동 시간")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "user_12345_20251217",
                "messages": [
                    {
                        "role": "user",
                        "content": "오늘 경기 알려줘",
                        "timestamp": "2025-12-17T14:30:00"
                    },
                    {
                        "role": "assistant",
                        "content": "오늘은 맨시티 vs 아스날 경기가 있습니다.",
                        "timestamp": "2025-12-17T14:30:05"
                    }
                ],
                "message_count": 2,
                "last_activity": "2025-12-17T14:30:05"
            }
        }


class SessionInfo(BaseModel):
    """
    세션 정보 모델
    """
    session_id: str
    message_count: int
    last_activity: str
    is_expired: bool


class ErrorResponse(BaseModel):
    """
    에러 응답 모델
    """
    error: str = Field(..., description="에러 메시지")
    detail: Optional[str] = Field(None, description="상세 정보")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        json_schema_extra = {
            "example": {
                "error": "OpenAI API Error",
                "detail": "Rate limit exceeded",
                "timestamp": "2025-12-17T14:30:00"
            }
        }
