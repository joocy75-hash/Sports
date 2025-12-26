"""
DeepSeek Analyzer - DeepSeek 모델 기반 경기 분석

DeepSeek AI 분석 서비스
- 모델: deepseek-chat (DeepSeek V3.2 - 2025년 12월 최신)
- 역할: 심층 분석 및 논리적 추론
"""

import aiohttp
import json
import logging
import time
from typing import Dict

from src.config.settings import get_settings
from .base_analyzer import BaseAIAnalyzer
from .models import AIOpinion, MatchContext, WinnerType, SportType

logger = logging.getLogger(__name__)


class DeepSeekAnalyzer(BaseAIAnalyzer):
    """
    DeepSeek 기반 경기 분석기

    특징:
    - 강력한 추론 능력
    - 비용 효율적
    - 빠른 응답 속도
    """

    provider_name = "deepseek"
    default_weight = 0.5

    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.api_key = settings.deepseek_api_key
        self.model = "deepseek-chat"  # DeepSeek V3.2 (2025년 12월 최신)
        self.url = "https://api.deepseek.com/chat/completions"

    def is_available(self) -> bool:
        """API 키 존재 여부 확인"""
        return bool(self.api_key)

    async def analyze_match(self, context: MatchContext) -> AIOpinion:
        """
        단일 경기 분석

        Args:
            context: 경기 컨텍스트 정보

        Returns:
            AIOpinion: DeepSeek의 분석 의견
        """
        if not self.is_available():
            logger.warning("[DeepSeek] API 키가 설정되지 않음")
            return self._create_unavailable_opinion(context, "DeepSeek API 키가 설정되지 않았습니다.")

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
            logger.error(f"[DeepSeek] 분석 오류: {e}", exc_info=True)
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

승자를 예측하고 확률을 제시해주세요. 반드시 JSON 형식으로만 응답하세요."""

    async def _call_api(self, system_prompt: str, user_prompt: str) -> Dict:
        """DeepSeek API 호출 (OpenAI 호환 형식)"""
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

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[DeepSeek] API 오류 ({response.status}): {error_text}")
                    raise Exception(f"DeepSeek API 오류: {response.status}")

                data = await response.json()
                content = data["choices"][0]["message"]["content"]

                # JSON 파싱 시도 (마크다운 코드 블록 제거)
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(f"[DeepSeek] JSON 파싱 실패, 텍스트 응답 처리: {content[:100]}...")
                    return self._parse_text_response(content)

    def _parse_text_response(self, text: str) -> Dict:
        """텍스트 응답에서 결과 추출 (fallback)"""
        text_lower = text.lower()

        if "홈" in text or "home" in text_lower or "승리" in text:
            winner = "Home"
        elif "원정" in text or "away" in text_lower:
            winner = "Away"
        else:
            winner = "Draw"

        return {
            "winner": winner,
            "confidence": 50,
            "probabilities": {"home": 0.33, "draw": 0.34, "away": 0.33},
            "reasoning": text[:200] if len(text) > 200 else text,
            "key_factor": "텍스트 분석",
        }
