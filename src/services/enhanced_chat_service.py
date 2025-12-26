"""
Enhanced Chat Service - OpenAI Function Calling 통합
GPT-4가 DB 쿼리 함수를 자동으로 호출하여 데이터 기반 응답을 생성합니다.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.services.conversation_manager import get_conversation_manager
from src.services.query_functions import FUNCTION_SCHEMAS, FUNCTION_MAP
from src.models.chat_models import ChatResponse

logger = logging.getLogger(__name__)


class EnhancedChatService:
    """
    Function Calling 기능을 갖춘 고급 Chat Service

    Features:
    - OpenAI GPT-4o Function Calling
    - DB 쿼리 자동 실행
    - 대화 히스토리 유지
    - 구조화된 응답
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self.conversation_manager = get_conversation_manager()

        if self.settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        else:
            logger.warning("⚠️ OpenAI API Key not found. Function Calling unavailable.")

    async def chat(
        self,
        query: str,
        session_id: str,
        db_session: AsyncSession,
        context: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """
        사용자 질문에 대해 AI 응답 생성

        Args:
            query: 사용자 질문
            session_id: 세션 ID
            db_session: DB 세션 (함수 호출용)
            context: 추가 컨텍스트

        Returns:
            ChatResponse: AI 응답
        """
        # 사용자 메시지 저장
        self.conversation_manager.add_message(session_id, "user", query)

        if not self.client:
            response_text = self._fallback_response(query)
            self.conversation_manager.add_message(session_id, "assistant", response_text)
            return ChatResponse(
                response=response_text,
                session_id=session_id
            )

        try:
            # 대화 히스토리 가져오기
            history = self.conversation_manager.get_messages_for_openai(session_id)

            # System prompt
            system_message = self._build_system_prompt(context or {})
            messages = [{"role": "system", "content": system_message}] + history

            # OpenAI API 호출 (Function Calling 활성화)
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                functions=FUNCTION_SCHEMAS,
                function_call="auto",  # AI가 필요시 자동으로 함수 호출
                temperature=0.7,
                max_tokens=800
            )

            message = response.choices[0].message
            function_used = None
            function_result = None
            tokens_used = response.usage.total_tokens if response.usage else None

            # Function Call 처리
            if message.function_call:
                function_name = message.function_call.name
                function_args = json.loads(message.function_call.arguments)

                logger.info(f"🔧 Function Called: {function_name} with args: {function_args}")

                # 함수 실행
                function_result = await self._execute_function(
                    function_name,
                    function_args,
                    db_session
                )

                # Function Call 정보 저장 (session 제외)
                serializable_function_args = {k: v for k, v in function_args.items() if k != "session"}
                self.conversation_manager.add_message(
                    session_id,
                    "assistant",
                    message.content or "",
                    function_call={
                        "name": function_name,
                        "arguments": serializable_function_args
                    }
                )

                # Function 결과로 다시 AI 호출 (최종 응답 생성)
                # Note: session을 제외한 인자만 직렬화 (session은 직렬화할 수 없음)
                serializable_args = {k: v for k, v in function_args.items() if k != "session"}
                messages.append({
                    "role": "assistant",
                    "content": message.content,
                    "function_call": {
                        "name": function_name,
                        "arguments": json.dumps(serializable_args, ensure_ascii=False)
                    }
                })
                messages.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(function_result, ensure_ascii=False)
                })

                # 최종 응답 생성
                final_response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=800
                )

                response_text = final_response.choices[0].message.content
                function_used = function_name

                if final_response.usage:
                    tokens_used = (tokens_used or 0) + final_response.usage.total_tokens

            else:
                # 일반 응답 (Function Call 없음)
                response_text = message.content

            # Assistant 응답 저장
            self.conversation_manager.add_message(
                session_id,
                "assistant",
                response_text,
                function_response={"name": function_used, "result": function_result} if function_used else None
            )

            return ChatResponse(
                response=response_text,
                session_id=session_id,
                function_used=function_used,
                function_result=function_result,
                tokens_used=tokens_used
            )

        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            error_message = f"죄송합니다. 오류가 발생했습니다: {str(e)}"
            self.conversation_manager.add_message(session_id, "assistant", error_message)
            return ChatResponse(
                response=error_message,
                session_id=session_id
            )

    async def _execute_function(
        self,
        function_name: str,
        arguments: Dict[str, Any],
        db_session: AsyncSession
    ) -> Any:
        """
        함수 실행

        Args:
            function_name: 함수 이름
            arguments: 함수 인자
            db_session: DB 세션

        Returns:
            Any: 함수 실행 결과
        """
        if function_name not in FUNCTION_MAP:
            logger.error(f"Unknown function: {function_name}")
            return {"error": f"Unknown function: {function_name}"}

        try:
            function = FUNCTION_MAP[function_name]

            # arguments 복사본 생성 (원본 보존)
            exec_args = arguments.copy()

            # DB 세션이 필요한 함수인지 확인
            if "session" in function.__code__.co_varnames:
                exec_args["session"] = db_session

            result = await function(**exec_args)
            logger.info(f"✅ Function {function_name} executed successfully")
            return result

        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}", exc_info=True)
            return {"error": str(e)}

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """
        System Prompt 생성

        Args:
            context: 추가 컨텍스트

        Returns:
            str: System prompt
        """
        return """당신은 전문 스포츠 베팅 분석 AI 에이전트입니다.

**역할:**
- 사용자에게 경기 일정, 예측, 통계 등을 제공합니다.
- 제공된 함수를 사용하여 실시간 데이터를 조회하고 정확한 정보를 전달합니다.
- 간결하고 전문적이며 친절하게 답변합니다.

**지침:**
1. 사용자 질문에 답하기 위해 필요한 데이터가 있으면 적절한 함수를 호출하세요.
2. 함수 결과를 바탕으로 명확하고 유용한 답변을 생성하세요.
3. 데이터가 없거나 확실하지 않으면 솔직하게 말하세요.
4. 항상 한국어로 답변하세요.
5. 베팅 조언 시에는 책임감 있게 Edge와 확률을 함께 알려주세요.

**예시:**
- "오늘 맨시티 경기 언제야?" → get_match_by_teams 함수 사용
- "추천 픽 알려줘" → get_predictions 또는 get_value_bets 함수 사용
- "토트넘 최근 폼 어때?" → get_team_stats 함수 사용
"""

    def _fallback_response(self, query: str) -> str:
        """
        OpenAI API가 없을 때 fallback 응답

        Args:
            query: 사용자 질문

        Returns:
            str: Fallback 응답
        """
        query = query.lower()

        if "경기" in query or "match" in query:
            return "OpenAI API 키가 설정되지 않아 AI 기능을 사용할 수 없습니다. 대시보드에서 경기 일정을 확인해주세요."
        if "예측" in query or "픽" in query or "prediction" in query:
            return "OpenAI API 키가 설정되지 않아 AI 예측 기능을 사용할 수 없습니다. Predictions 페이지를 확인해주세요."

        return "OpenAI API 키가 설정되지 않아 AI 채팅 기능을 사용할 수 없습니다. .env 파일에 OPENAI_API_KEY를 추가해주세요."

    def get_session_history(self, session_id: str) -> List[Dict]:
        """
        세션의 대화 히스토리 조회

        Args:
            session_id: 세션 ID

        Returns:
            List[Dict]: 메시지 목록
        """
        return self.conversation_manager.get_history(session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        세션 삭제

        Args:
            session_id: 세션 ID

        Returns:
            bool: 삭제 성공 여부
        """
        return self.conversation_manager.delete_session(session_id)

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        세션 정보 조회

        Args:
            session_id: 세션 ID

        Returns:
            Dict: 세션 정보
        """
        return self.conversation_manager.get_session_info(session_id)
