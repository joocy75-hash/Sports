import aiohttp
import os
import logging
import json
from typing import Dict

logger = logging.getLogger(__name__)


class GPTAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = "gpt-4o"
        self.url = "https://api.openai.com/v1/chat/completions"

    async def analyze_match(
        self, match_info: str, home_stats: str, away_stats: str
    ) -> Dict:
        """
        Analyze a match using GPT-4o.
        Returns a structured prediction.
        """
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not found. Returning dummy analysis.")
            return {
                "recommendation": {"mark": "분석불가", "type": "none"},
                "reasoning": "OpenAI API 키가 설정되지 않았습니다.",
            }

        system_prompt = """
        You are a world-class sports betting analyst. 
        Your goal is to predict the winner of a match based on provided statistics.
        You must be decisive. Do not hedge.
        
        Output Format (JSON):
        {
            "winner": "Home" | "Draw" | "Away",
            "confidence": 0-100,
            "reasoning": "Short, punchy explanation in Korean (max 2 sentences).",
            "key_factor": "One main reason (e.g. 'Home Strong Attack')"
        }
        """

        user_prompt = f"""
        Analyze this match:
        Match: {match_info}
        
        Home Team Stats:
        {home_stats}
        
        Away Team Stats:
        {away_stats}
        
        Who wins? Give me the answer sheet.
        """

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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.url, headers=headers, json=payload
                ) as response:
                    if response.status != 200:
                        logger.error(f"OpenAI API Error: {await response.text()}")
                        return {
                            "recommendation": {"mark": "오류", "type": "error"},
                            "reasoning": "AI 분석 중 오류 발생",
                        }

                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]
                    result = json.loads(content)

                    # Map to our internal format
                    mark_map = {"Home": "승", "Draw": "무", "Away": "패"}

                    return {
                        "recommendation": {
                            "mark": mark_map.get(result.get("winner"), "무"),
                            "type": "1x2",
                        },
                        "confidence": result.get("confidence", 50),
                        "reasoning": result.get("reasoning", ""),
                        "key_factor": result.get("key_factor", ""),
                    }
        except Exception as e:
            logger.error(f"GPT Analysis Exception: {e}")
            return {
                "recommendation": {"mark": "오류", "type": "error"},
                "reasoning": str(e),
            }
