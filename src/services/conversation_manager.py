"""
대화 히스토리 관리 - 메모리 기반
세션별로 최근 10개 메시지를 저장하고 관리합니다.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    메모리 기반 대화 히스토리 관리자

    Features:
    - 세션별 메시지 저장 (최근 10개)
    - 30분 TTL (자동 만료)
    - Thread-safe 구현
    """

    def __init__(self, max_messages: int = 10, ttl_minutes: int = 30):
        """
        Args:
            max_messages: 세션당 최대 메시지 수
            ttl_minutes: 세션 만료 시간 (분)
        """
        self.max_messages = max_messages
        self.ttl_minutes = ttl_minutes

        # {session_id: [messages]}
        self._sessions: Dict[str, List[Dict]] = defaultdict(list)

        # {session_id: last_activity_time}
        self._last_activity: Dict[str, datetime] = {}

        # Thread lock for concurrent access
        self._lock = threading.Lock()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        function_call: Optional[Dict] = None,
        function_response: Optional[Dict] = None
    ) -> None:
        """
        세션에 메시지 추가

        Args:
            session_id: 세션 ID
            role: "user" | "assistant" | "function"
            content: 메시지 내용
            function_call: Function Calling 정보 (선택)
            function_response: Function 응답 (선택)
        """
        with self._lock:
            message = {
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            }

            if function_call:
                message["function_call"] = function_call

            if function_response:
                message["function_response"] = function_response

            self._sessions[session_id].append(message)

            # 최대 메시지 수 제한
            if len(self._sessions[session_id]) > self.max_messages:
                self._sessions[session_id] = self._sessions[session_id][-self.max_messages:]

            # 활동 시간 갱신
            self._last_activity[session_id] = datetime.now()

            logger.info(f"Added message to session {session_id[:8]}... (total: {len(self._sessions[session_id])})")

    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        세션의 대화 히스토리 조회

        Args:
            session_id: 세션 ID
            limit: 반환할 최대 메시지 수 (None이면 전체)

        Returns:
            List[Dict]: 메시지 목록
        """
        with self._lock:
            # 만료된 세션 체크
            if self._is_expired(session_id):
                self._delete_session(session_id)
                return []

            messages = self._sessions.get(session_id, [])

            if limit:
                messages = messages[-limit:]

            return messages.copy()  # 복사본 반환 (안전성)

    def get_messages_for_openai(self, session_id: str) -> List[Dict]:
        """
        OpenAI API 호출용 메시지 포맷으로 변환

        Args:
            session_id: 세션 ID

        Returns:
            List[Dict]: OpenAI format messages
        """
        history = self.get_history(session_id)

        openai_messages = []
        for msg in history:
            openai_msg = {
                "role": msg["role"],
                "content": msg["content"]
            }

            # Function Call 정보 포함
            if "function_call" in msg:
                openai_msg["function_call"] = msg["function_call"]

            # Function Response 정보 포함
            if "function_response" in msg:
                openai_msg["name"] = msg["function_response"].get("name", "")
                openai_msg["content"] = str(msg["function_response"].get("result", ""))

            openai_messages.append(openai_msg)

        return openai_messages

    def delete_session(self, session_id: str) -> bool:
        """
        세션 삭제

        Args:
            session_id: 세션 ID

        Returns:
            bool: 삭제 성공 여부
        """
        with self._lock:
            return self._delete_session(session_id)

    def _delete_session(self, session_id: str) -> bool:
        """내부 세션 삭제 (lock 없이)"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if session_id in self._last_activity:
                del self._last_activity[session_id]
            logger.info(f"Deleted session {session_id[:8]}...")
            return True
        return False

    def _is_expired(self, session_id: str) -> bool:
        """세션 만료 체크"""
        if session_id not in self._last_activity:
            return True

        last_time = self._last_activity[session_id]
        expiry_time = datetime.now() - timedelta(minutes=self.ttl_minutes)

        return last_time < expiry_time

    def cleanup_expired_sessions(self) -> int:
        """
        만료된 세션 정리

        Returns:
            int: 삭제된 세션 수
        """
        with self._lock:
            expired_sessions = [
                session_id
                for session_id in list(self._sessions.keys())
                if self._is_expired(session_id)
            ]

            for session_id in expired_sessions:
                self._delete_session(session_id)

            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

            return len(expired_sessions)

    def get_session_count(self) -> int:
        """활성 세션 수 반환"""
        with self._lock:
            return len(self._sessions)

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        세션 정보 조회

        Returns:
            Dict: 세션 정보 (메시지 수, 마지막 활동 시간 등)
        """
        with self._lock:
            if session_id not in self._sessions:
                return None

            return {
                "session_id": session_id,
                "message_count": len(self._sessions[session_id]),
                "last_activity": self._last_activity.get(session_id, datetime.now()).isoformat(),
                "is_expired": self._is_expired(session_id)
            }


# 전역 인스턴스 (싱글톤 패턴)
_conversation_manager: Optional[ConversationManager] = None


def get_conversation_manager() -> ConversationManager:
    """
    ConversationManager 싱글톤 인스턴스 반환

    Returns:
        ConversationManager: 대화 관리자 인스턴스
    """
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager(
            max_messages=10,  # 최근 10개 메시지
            ttl_minutes=30    # 30분 TTL
        )
    return _conversation_manager
