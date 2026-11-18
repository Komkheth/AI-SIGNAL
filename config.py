from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CART3R SNIPER PRO API"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    # Twelve Data provides Forex and precious-metals OHLC data.
    twelve_data_api_key: str = ""
    twelve_data_base_url: str = "https://api.twelvedata.com"

    # Binance public market-data endpoint is used for BTCUSDT candles.
    binance_base_url: str = "https://api.binance.com"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False

    # Optional news and AI services; secrets remain server-side.
    finnhub_api_key: str = ""
    finnhub_base_url: str = "https://finnhub.io/api/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    scan_enabled: bool = False
    scan_interval_seconds: int = 300
    candle_limit: int = 250
    signal_cooldown_minutes: int = 30
    minimum_rr: float = 2.0
    fvg_max_age: int = 8
    sweep_lookback: int = 20
    swing_lookback: int = 5
    atr_period: int = 14
    displacement_atr_multiple: float = 1.0

    # Risk is informational only; the service never places orders.
    default_risk_percent: float = 1.0

@lru_cache
def get_settings() -> Settings:
    return Settings()
