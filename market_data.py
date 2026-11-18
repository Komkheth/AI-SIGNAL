from datetime import datetime, timezone
import httpx
from .config import Settings
from .models import Candle

FOREX_SYMBOLS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
}
GOLD_SYMBOLS = {"XAUUSD": "XAU/USD"}
CRYPTO_SYMBOLS = {"BTCUSD": "BTCUSDT"}

class MarketDataError(Exception):
    pass

class MarketDataClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=20.0)

    async def close(self):
        await self.client.aclose()

    async def candles(self, symbol: str, timeframe: str, limit: int = 250) -> list[Candle]:
        symbol = symbol.upper()
        if symbol in CRYPTO_SYMBOLS:
            return await self._binance(symbol, timeframe, limit)
        if symbol in FOREX_SYMBOLS or symbol in GOLD_SYMBOLS:
            return await self._twelve_data(symbol, timeframe, limit)
        raise MarketDataError(f"Unsupported symbol: {symbol}")

    async def _twelve_data(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        if not self.settings.twelve_data_api_key:
            raise MarketDataError("TWELVE_DATA_API_KEY is not configured.")
        provider_symbol = {**FOREX_SYMBOLS, **GOLD_SYMBOLS}[symbol]
        interval = {"1m": "1min", "5m": "5min", "15m": "15min"}[timeframe]
        response = await self.client.get(
            f"{self.settings.twelve_data_base_url}/time_series",
            params={
                "symbol": provider_symbol,
                "interval": interval,
                "outputsize": min(max(limit, 50), 5000),
                "apikey": self.settings.twelve_data_api_key,
                "format": "JSON",
                "timezone": "UTC",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "error" or "values" not in payload:
            raise MarketDataError(payload.get("message", "Twelve Data returned no candle values."))
        rows = reversed(payload["values"])  # provider returns newest first
        candles = []
        for row in rows:
            candles.append(Candle(
                time=datetime.fromisoformat(row["datetime"].replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
                    if "T" in row["datetime"] else datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
                open=float(row["open"]), high=float(row["high"]), low=float(row["low"]),
                close=float(row["close"]), volume=float(row.get("volume") or 0),
            ))
        return candles

    async def _binance(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        interval = {"1m": "1m", "5m": "5m", "15m": "15m"}[timeframe]
        response = await self.client.get(
            f"{self.settings.binance_base_url}/api/v3/klines",
            params={"symbol": CRYPTO_SYMBOLS[symbol], "interval": interval, "limit": min(max(limit, 50), 1000)},
        )
        response.raise_for_status()
        rows = response.json()
        return [Candle(
            time=datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
            open=float(row[1]), high=float(row[2]), low=float(row[3]),
            close=float(row[4]), volume=float(row[5]),
        ) for row in rows]
