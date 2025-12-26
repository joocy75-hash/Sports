from functools import lru_cache
from typing import Optional

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    postgres_dsn: str
    redis_url: str

    provider: str = "api_football"  # or "sportmonks"
    api_football_key: Optional[str] = None
    sportmonks_key: Optional[str] = None
    football_data_token: Optional[str] = None
    the_odds_api_key: Optional[str] = None

    # KSPO API (공공데이터포털 - 두 개의 서로 다른 API)
    kspo_todz_api_key: Optional[str] = None  # 체육진흥투표권 발매대상 경기정보
    kspo_todz_api_base_url: Optional[str] = None
    kspo_sosfo_api_key: Optional[str] = None  # 소셜포커스 경기관리
    kspo_sosfo_api_base_url: Optional[str] = None

    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # API 보안
    api_secret_key_hash: Optional[str] = None

    openai_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None
    kimi_api_key: Optional[str] = None
    kimi_api_base_url: str = "https://api.moonshot.cn/v1"

    # Claude AI (Anthropic)
    claude_api_key: Optional[str] = None

    # Gemini (Google)
    gemini_api_key: Optional[str] = None

    # DeepSeek
    deepseek_api_key: Optional[str] = None

    # Sports Data APIs (Free)
    ball_dont_lie_api_key: Optional[str] = None  # NBA (balldontlie.io)

    api_football_base_url: HttpUrl = "https://api-football-v1.p.rapidapi.com/v3"
    sportmonks_base_url: HttpUrl = "https://api.sportmonks.com/v3/football"

    rate_limit_per_sec: float = 5.0

    @property
    def provider_key(self) -> Optional[str]:
        return (
            self.api_football_key
            if self.provider == "api_football"
            else self.sportmonks_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
