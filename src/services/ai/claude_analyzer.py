"""
Claude Analyzer - Anthropic Claude 모델 기반 경기 분석

Claude AI 분석 서비스
- 모델: claude-opus-4-5-20251101 (Opus 4.5 - 2025년 말 최신)
- 역할: 논리적 추론 및 구조화된 분석
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


class ClaudeAnalyzer(BaseAIAnalyzer):
    """
    Anthropic Claude 기반 경기 분석기

    특징:
    - 뛰어난 논리적 추론 능력
    - 정확한 JSON 구조화 출력
    - 한국어 분석 품질 우수
    """

    provider_name = "claude"
    default_weight = 0.6  # Claude는 높은 가중치

    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.api_key = settings.claude_api_key
        self.model = "claude-opus-4-5-20251101"  # Opus 4.5 (2025년 말 최신)
        self.url = "https://api.anthropic.com/v1/messages"

    def is_available(self) -> bool:
        """API 키 존재 여부 확인"""
        return bool(self.api_key)

    async def analyze_match(self, context: MatchContext) -> AIOpinion:
        """
        단일 경기 분석

        Args:
            context: 경기 컨텍스트 정보

        Returns:
            AIOpinion: Claude의 분석 의견
        """
        if not self.is_available():
            logger.warning("[Claude] API 키가 설정되지 않음")
            return self._create_unavailable_opinion(context, "Claude API 키가 설정되지 않았습니다.")

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
            logger.error(f"[Claude] 분석 오류: {e}", exc_info=True)
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
        """Anthropic API 호출"""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Claude] API 오류 ({response.status}): {error_text}")
                    raise Exception(f"Claude API 오류: {response.status}")

                data = await response.json()
                content = data["content"][0]["text"]

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
                    logger.warning(f"[Claude] JSON 파싱 실패, 텍스트 응답 처리: {content[:100]}...")
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
