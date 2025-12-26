"""
Gemini Analyzer - Google Gemini 모델 기반 경기 분석

Gemini AI 분석 서비스
- 모델: gemini-2.0-flash (Gemini 3 계열 - 2025년 말 최신)
- 역할: 빠른 분석 및 다각도 검증
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


class GeminiAnalyzer(BaseAIAnalyzer):
    """
    Google Gemini 기반 경기 분석기

    특징:
    - 빠른 응답 속도
    - 멀티모달 지원
    - 최신 정보 반영
    """

    provider_name = "gemini"
    default_weight = 0.5

    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model = "gemini-2.0-flash"  # Gemini 3 계열 (2025년 말 최신)
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def is_available(self) -> bool:
        """API 키 존재 여부 확인"""
        return bool(self.api_key)

    async def analyze_match(self, context: MatchContext) -> AIOpinion:
        """
        단일 경기 분석

        Args:
            context: 경기 컨텍스트 정보

        Returns:
            AIOpinion: Gemini의 분석 의견
        """
        if not self.is_available():
            logger.warning("[Gemini] API 키가 설정되지 않음")
            return self._create_unavailable_opinion(context, "Gemini API 키가 설정되지 않았습니다.")

        start_time = time.time()

        prompt = self._build_prompt(context)

        try:
            result = await self._call_api(prompt)
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
            logger.error(f"[Gemini] 분석 오류: {e}", exc_info=True)
            self._measure_latency(start_time)
            return self._create_error_opinion(context, str(e))

    def _build_prompt(self, context: MatchContext) -> str:
        """프롬프트 생성 (시스템 + 사용자 통합)"""
        system_prompt = self._get_sport_system_prompt(context.sport_type)
        sport_label = "축구 승무패" if context.sport_type == SportType.SOCCER else "농구 승5패"

        return f"""{system_prompt}

[스포츠토토 {sport_label}] 다음 경기를 분석해주세요:

{context.to_prompt_string()}

승자를 예측하고 확률을 제시해주세요."""

    async def _call_api(self, prompt: str) -> Dict:
        """Google Gemini API 호출"""
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 1024,
            }
        }

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Gemini] API 오류 ({response.status}): {error_text}")
                    raise Exception(f"Gemini API 오류: {response.status}")

                data = await response.json()

                # 응답 구조에서 텍스트 추출
                try:
                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError) as e:
                    logger.error(f"[Gemini] 응답 구조 오류: {data}")
                    raise Exception(f"Gemini 응답 파싱 실패: {e}")

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
                    logger.warning(f"[Gemini] JSON 파싱 실패, 텍스트 응답 처리: {content[:100]}...")
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
