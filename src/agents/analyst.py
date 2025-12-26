import logging
from typing import Optional, Dict
from openai import AsyncOpenAI
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class AnalystAgent:
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        if self.settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        else:
            logger.warning("OPENAI_API_KEY not set. AnalystAgent will not function.")

    async def analyze_match(self, match_info: Dict) -> str:
        """
        Generates a betting analysis report for a given match.
        match_info should contain: home, away, league, odds, prediction, etc.
        """
        if not self.client:
            return "⚠️ AI Analysis unavailable (Missing API Key)."

        prompt = self._build_prompt(match_info)

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o",  # or gpt-3.5-turbo
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 전문 스포츠 베팅 분석가입니다. 데이터에 기반한 분석을 제공하세요. 반드시 한국어로 답변해야 합니다.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return "⚠️ Analysis failed due to an error."

    def _build_prompt(self, info: Dict) -> str:
        return f"""
        Analyze this football match for betting value:
        
        Match: {info.get("home")} vs {info.get("away")}
        League: {info.get("league")}
        Start Time: {info.get("start")}
        
        Current Odds:
        - Home: {info.get("odds", {}).get("home")}
        - Draw: {info.get("odds", {}).get("draw")}
        - Away: {info.get("odds", {}).get("away")}
        
        Our Model Prediction:
        - Probabilities: Home {info.get("prob", {}).get("home")}, Draw {info.get("prob", {}).get("draw")}, Away {info.get("prob", {}).get("away")}
        - Recommendation: {info.get("recommendation")}
        
        Key Factors:
        - Sharp Money Detected: {info.get("sharp", {}).get("flag")} ({info.get("sharp", {}).get("direction")})
        
        Task:
        1. Compare the odds with our model's probability.
        2. Identify if there is value.
        3. Consider the sharp money movement if any.
        4. Provide a final verdict and a confidence level (1-10).
        5. Keep it under 200 words.
        """
