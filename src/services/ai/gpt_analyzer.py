"""
GPT Analyzer - OpenAI GPT 모델 기반 경기 분석

주력 AI 분석 서비스
- 모델: chatgpt-4o-latest (GPT-5.2 계열 - 2025년 말 최신)
- 역할: 승부 예측 및 확률 계산의 핵심 엔진
"""

import aiohttp
import json
import logging
import time
from typing import Dict, Optional

from src.config.settings import get_settings
from .base_analyzer import BaseAIAnalyzer
from .models import AIOpinion, MatchContext, WinnerType, SportType

logger = logging.getLogger(__name__)


class GPTAnalyzer(BaseAIAnalyzer):
    """
    OpenAI GPT-4o 기반 경기 분석기

    특징:
    - 강력한 추론 능력
    - JSON 구조화 출력 지원
    - 높은 정확도의 승부 예측
    """

    provider_name = "gpt"
    default_weight = 0.5  # 전체 가중치의 50%

    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model = "chatgpt-4o-latest"  # GPT-5.2 계열 (2025년 말 최신)
        self.url = "https://api.openai.com/v1/chat/completions"

    def is_available(self) -> bool:
        """API 키 존재 여부 확인"""
        return bool(self.api_key)

    async def analyze_match(self, context: MatchContext) -> AIOpinion:
        """
        단일 경기 분석

        Args:
            context: 경기 컨텍스트 정보

        Returns:
            AIOpinion: GPT의 분석 의견
        """
        if not self.is_available():
            logger.warning("[GPT] API 키가 설정되지 않음")
            return self._create_unavailable_opinion(context, "OpenAI API 키가 설정되지 않았습니다.")

        start_time = time.time()

        system_prompt = self._build_system_prompt(context)
        user_prompt = self._build_user_prompt(context)

        try:
            result = await self._call_api(system_prompt, user_prompt)
            latency = self._measure_latency(start_time)

            return AIOpinion(
                provider=self.provider_name,
                winner=self._parse_winner(result.get("winner", "Draw")),
                confidence=result.get("confidence", 50),
                reasoning=result.get("reasoning", ""),
                key_factor=result.get("key_factor", ""),
                probabilities=result.get("probabilities", {
                    "home": 0.33,
                    "draw": 0.34,
                    "away": 0.33
                }),
                raw_response=result,
                latency_ms=latency,
            )

        except Exception as e:
            logger.error(f"[GPT] 분석 오류: {e}", exc_info=True)
            self._measure_latency(start_time)
            return self._create_error_opinion(context, str(e))

    def _build_system_prompt(self, context: MatchContext) -> str:
        """스포츠 타입별 시스템 프롬프트 생성"""
        return self._get_sport_system_prompt(context.sport_type)

    def _build_user_prompt(self, context: MatchContext) -> str:
        """사용자 프롬프트 생성"""
        sport_label = "축구 승무패" if context.sport_type == SportType.SOCCER else "농구 승5패"
        return f"""[스포츠토토 {sport_label}] 다음 경기를 분석해주세요:

{context.to_prompt_string()}

승자를 예측하고 확률을 제시해주세요."""

    async def _call_api(self, system_prompt: str, user_prompt: str) -> Dict:
        """OpenAI API 호출"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.5,
            "response_format": {"type": "json_object"},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, headers=headers, json=payload, timeout=30) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[GPT] API 오류 ({response.status}): {error_text}")
                    raise Exception(f"OpenAI API 오류: {response.status}")

                data = await response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
