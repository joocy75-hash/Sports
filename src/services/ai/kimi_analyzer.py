"""
Kimi Analyzer - Moonshot 모델 기반 경기 분석

보조 AI 분석 서비스
- 모델: kimi-k2-0711-preview (Kimi K2 - 2025년 말 최신)
- 역할: 다각도 검증 및 컨센서스 형성
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


class KimiAnalyzer(BaseAIAnalyzer):
    """
    Moonshot 기반 경기 분석기

    특징:
    - 빠른 추론 속도
    - 다국어 지원 (한국어 우수)
    - 대용량 컨텍스트 지원
    """

    provider_name = "kimi"
    default_weight = 0.5  # 전체 가중치의 50%

    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.api_key = settings.kimi_api_key
        self.base_url = settings.kimi_api_base_url
        self.model = "kimi-k2-0711-preview"  # Kimi K2 (2025년 말 최신)

    def is_available(self) -> bool:
        """API 키 존재 여부 확인"""
        return bool(self.api_key)

    async def analyze_match(self, context: MatchContext) -> AIOpinion:
        """
        단일 경기 분석

        Args:
            context: 경기 컨텍스트 정보

        Returns:
            AIOpinion: Kimi의 분석 의견
        """
        if not self.is_available():
            logger.warning("[Kimi] API 키가 설정되지 않음")
            return self._create_unavailable_opinion(context, "Kimi API 키가 설정되지 않았습니다.")

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
            logger.error(f"[Kimi] 분석 오류: {e}", exc_info=True)
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
        """Moonshot API 호출"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.5,
        }

        timeout = aiohttp.ClientTimeout(total=120)  # 2분 타임아웃
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[Kimi] API 오류 ({response.status}): {error_text}")
                    raise Exception(f"Kimi API 오류: {response.status}")

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
                    # JSON 파싱 실패 시 텍스트 응답 처리
                    logger.warning(f"[Kimi] JSON 파싱 실패, 텍스트 응답 처리: {content[:100]}...")
                    return self._parse_text_response(content)

    def _parse_text_response(self, text: str) -> Dict:
        """텍스트 응답에서 결과 추출 (fallback)"""
        # 간단한 휴리스틱으로 승자 추출
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
