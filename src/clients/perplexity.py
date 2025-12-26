"""Perplexity AI Client for real-time sports information retrieval."""

from typing import Optional, List, Dict, Any
import httpx
from dataclasses import dataclass


@dataclass
class PerplexityResponse:
    """Perplexity AI response structure."""
    content: str
    model: str
    citations: List[str]
    usage: Dict[str, int]


class PerplexityClient:
    """
    Perplexity AI client for sports information retrieval.

    Uses OpenAI-compatible API format with Perplexity's sonar models
    for real-time web search + AI analysis.

    Features:
    - Real-time sports news and injury updates
    - Team form analysis
    - Player statistics and recent performance
    - Head-to-head historical data
    """

    BASE_URL = "https://api.perplexity.ai"

    def __init__(self, api_key: str, model: str = "sonar"):
        """
        Initialize Perplexity client.

        Args:
            api_key: Perplexity API key
            model: Model to use (sonar, sonar-pro, sonar-reasoning)
        """
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> PerplexityResponse:
        """
        Send chat completion request to Perplexity AI.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response

        Returns:
            PerplexityResponse with content and citations
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()

            return PerplexityResponse(
                content=data["choices"][0]["message"]["content"],
                model=data.get("model", self.model),
                citations=data.get("citations", []),
                usage=data.get("usage", {}),
            )

    async def ask(self, question: str, system_prompt: Optional[str] = None) -> PerplexityResponse:
        """
        Simple question-answer interface.

        Args:
            question: Question to ask
            system_prompt: Optional system prompt

        Returns:
            PerplexityResponse with answer
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": question})

        return await self.chat(messages)

    # ========== Sports-specific methods ==========

    async def get_team_news(self, team_name: str, sport: str = "soccer") -> PerplexityResponse:
        """
        Get latest news and updates for a team.

        Args:
            team_name: Team name (e.g., "Manchester United", "LA Lakers")
            sport: Sport type (soccer, basketball, baseball)

        Returns:
            Latest team news, injuries, transfers
        """
        sport_kr = {"soccer": "축구", "basketball": "농구", "baseball": "야구"}.get(sport, sport)

        system_prompt = f"""당신은 {sport_kr} 전문 스포츠 분석가입니다.
최신 정보를 바탕으로 팀 상황을 분석해주세요.
반드시 한국어로 답변하고, 출처가 있다면 명시해주세요."""

        question = f"""{team_name} 팀의 최신 소식을 알려주세요:
1. 최근 경기 결과 및 폼
2. 부상자/결장자 명단
3. 주요 뉴스 (이적, 감독 교체 등)
4. 다음 경기 전망"""

        return await self.ask(question, system_prompt)

    async def get_match_preview(
        self,
        home_team: str,
        away_team: str,
        sport: str = "soccer",
        league: Optional[str] = None,
    ) -> PerplexityResponse:
        """
        Get match preview with analysis.

        Args:
            home_team: Home team name
            away_team: Away team name
            sport: Sport type
            league: Optional league name

        Returns:
            Match preview with statistics and prediction factors
        """
        sport_kr = {"soccer": "축구", "basketball": "농구", "baseball": "야구"}.get(sport, sport)
        league_info = f" ({league})" if league else ""

        system_prompt = f"""당신은 {sport_kr} 베팅 분석 전문가입니다.
객관적인 데이터와 최신 정보를 바탕으로 경기를 분석해주세요.
확률과 통계를 중심으로 분석하되, 주관적 예측은 최소화하세요."""

        question = f"""{home_team} vs {away_team}{league_info} 경기 분석:

1. 양팀 최근 5경기 성적
2. 상대 전적 (최근 5경기)
3. 홈/원정 기록
4. 주요 결장자 및 부상자
5. 경기에 영향을 미칠 수 있는 요소들
6. 객관적 분석 요약"""

        return await self.ask(question, system_prompt)

    async def get_player_form(
        self,
        player_name: str,
        sport: str = "soccer",
    ) -> PerplexityResponse:
        """
        Get player's recent form and statistics.

        Args:
            player_name: Player name
            sport: Sport type

        Returns:
            Player form analysis
        """
        sport_kr = {"soccer": "축구", "basketball": "농구", "baseball": "야구"}.get(sport, sport)

        system_prompt = f"당신은 {sport_kr} 선수 분석 전문가입니다. 최신 통계와 폼을 분석해주세요."

        question = f"""{player_name} 선수의 최근 폼을 분석해주세요:
1. 최근 5경기 주요 기록
2. 시즌 전체 통계
3. 컨디션/부상 이력
4. 팀 내 역할 및 중요도"""

        return await self.ask(question, system_prompt)

    async def get_league_standings(
        self,
        league: str,
        sport: str = "soccer",
    ) -> PerplexityResponse:
        """
        Get current league standings and analysis.

        Args:
            league: League name (e.g., "프리미어리그", "NBA", "KBO")
            sport: Sport type

        Returns:
            League standings and form analysis
        """
        question = f"""{league} 현재 순위와 상황을 알려주세요:
1. 현재 순위표 (상위 10팀)
2. 최근 폼이 좋은 팀
3. 폼이 나쁜 팀
4. 주목할 만한 경기 일정"""

        return await self.ask(question)

    async def analyze_odds_value(
        self,
        home_team: str,
        away_team: str,
        odds: Dict[str, float],
        sport: str = "soccer",
    ) -> PerplexityResponse:
        """
        Analyze if odds provide value based on current information.

        Args:
            home_team: Home team name
            away_team: Away team name
            odds: Dict with 'home', 'draw' (optional), 'away' odds
            sport: Sport type

        Returns:
            Value analysis for the odds
        """
        sport_kr = {"soccer": "축구", "basketball": "농구", "baseball": "야구"}.get(sport, sport)

        odds_str = ", ".join([f"{k}: {v}" for k, v in odds.items()])

        system_prompt = f"""당신은 {sport_kr} 배당 분석 전문가입니다.
배당률과 실제 확률을 비교하여 가치 베팅 기회를 찾아주세요.
배당률에서 역산한 내재확률과 실제 예상 확률을 비교 분석해주세요."""

        question = f"""{home_team} vs {away_team}
현재 배당률: {odds_str}

1. 배당률에서 역산한 내재확률
2. 최신 정보를 반영한 실제 예상 확률
3. 가치(Value)가 있는 선택지
4. 주의해야 할 요소"""

        return await self.ask(question, system_prompt)


# Factory function
def create_perplexity_client(api_key: Optional[str] = None) -> PerplexityClient:
    """
    Create Perplexity client with API key from environment or parameter.

    Args:
        api_key: Optional API key (falls back to PERPLEXITY_API_KEY env var)

    Returns:
        PerplexityClient instance
    """
    import os

    key = api_key or os.getenv("PERPLEXITY_API_KEY")
    if not key:
        raise ValueError("PERPLEXITY_API_KEY not found in environment or parameter")

    return PerplexityClient(api_key=key)
