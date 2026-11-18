import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .market_data import MarketDataClient, MarketDataError
from .models import HealthResponse, Signal
from .notifications import TelegramNotifier
from .strategy import detect_signal
from .news import NewsClient
from .assistant import AITradingAssistant
from pydantic import BaseModel, Field

settings = get_settings()
market = MarketDataClient(settings)
telegram = TelegramNotifier(settings)
news_client = NewsClient(settings)
ai_assistant = AITradingAssistant(settings)
signals: list[Signal] = []
last_sent: dict[str, datetime] = {}
SYMBOLS = {
    "EURUSD": "FOREX", "GBPUSD": "FOREX", "USDJPY": "FOREX",
    "AUDUSD": "FOREX", "USDCAD": "FOREX", "XAUUSD": "GOLD", "BTCUSD": "CRYPTO",
}
TIMEFRAMES = ["1m", "5m", "15m"]

def _dedupe_key(signal: Signal) -> str:
    return f"{signal.symbol}:{signal.timeframe}:{signal.direction}:{signal.candle_time.isoformat()}"

async def scan_one(symbol: str, timeframe: str, notify: bool = True):
    candles = await market.candles(symbol, timeframe, settings.candle_limit)
    signal = detect_signal(symbol, SYMBOLS[symbol], timeframe, candles, settings)
    if signal is None:
        return None
    key = _dedupe_key(signal)
    if any(_dedupe_key(existing) == key for existing in signals):
        return None
    signals.insert(0, signal)
    del signals[500:]
    if notify:
        previous = last_sent.get(f"{symbol}:{timeframe}")
        cooldown = timedelta(minutes=settings.signal_cooldown_minutes)
        if previous is None or datetime.now(timezone.utc) - previous >= cooldown:
            try:
                result = await telegram.send_signal(signal)
                if result.get("sent"):
                    last_sent[f"{symbol}:{timeframe}"] = datetime.now(timezone.utc)
            except Exception as exc:
                print(f"Telegram send failed: {exc}")
    return signal

async def scan_loop():
    while True:
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                try:
                    await scan_one(symbol, timeframe, notify=True)
                except Exception as exc:
                    print(f"Scan error {symbol} {timeframe}: {exc}")
                await asyncio.sleep(0.5)
        await asyncio.sleep(max(30, settings.scan_interval_seconds))

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if settings.scan_enabled:
        task = asyncio.create_task(scan_loop())
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await market.close()
    await telegram.close()
    await news_client.close()
    await ai_assistant.close()

app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your deployed frontend domain in production.
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok", app=settings.app_name,
        signal_engine="RUNNING" if settings.scan_enabled else "ON_DEMAND",
    )

@app.get("/api/config")
async def public_config():
    return {
        "symbols": list(SYMBOLS.keys()),
        "timeframes": TIMEFRAMES,
        "default_risk_percent": settings.default_risk_percent,
        "automatic_execution": False,
        "telegram_enabled": settings.telegram_enabled,
        "news_enabled": bool(settings.finnhub_api_key),
        "ai_chat_enabled": bool(settings.openai_api_key),
        "scan_enabled": settings.scan_enabled,
    }

@app.get("/api/candles")
async def get_candles(
    symbol: str = Query("EURUSD"),
    timeframe: str = Query("5m"),
    limit: int = Query(200, ge=50, le=1000),
):
    symbol, timeframe = symbol.upper(), timeframe.lower()
    if symbol not in SYMBOLS or timeframe not in TIMEFRAMES:
        raise HTTPException(400, "Unsupported symbol or timeframe.")
    try:
        data = await market.candles(symbol, timeframe, limit)
        return {"symbol": symbol, "timeframe": timeframe, "candles": [c.model_dump(mode="json") for c in data]}
    except MarketDataError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Market data provider error: {exc}")

@app.post("/api/scan")
async def run_scan(
    symbol: str = Query("EURUSD"),
    timeframe: str = Query("5m"),
):
    symbol, timeframe = symbol.upper(), timeframe.lower()
    if symbol not in SYMBOLS or timeframe not in TIMEFRAMES:
        raise HTTPException(400, "Unsupported symbol or timeframe.")
    try:
        signal = await scan_one(symbol, timeframe, notify=True)
        return {"signal": signal.model_dump(mode="json") if signal else None,
                "message": "Candidate found." if signal else "No qualifying setup on the latest closed candle.",
                "automatic_execution": False}
    except MarketDataError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"Scan failed: {exc}")

@app.get("/api/signals")
async def get_signals(
    symbol: str | None = None,
    timeframe: str | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    result = signals
    if symbol:
        result = [s for s in result if s.symbol == symbol.upper()]
    if timeframe:
        result = [s for s in result if s.timeframe == timeframe.lower()]
    return {"count": len(result[:limit]), "signals": [s.model_dump(mode="json") for s in result[:limit]],
            "automatic_execution": False}


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    symbol: str = "BTCUSD"
    timeframe: str = "5m"

@app.get("/api/news")
async def get_news(category: str = Query("general", pattern="^(general|forex|crypto|merger)$")):
    try:
        return await news_client.latest(category)
    except Exception as exc:
        raise HTTPException(502, f"News provider error: {exc}")

@app.post("/api/assistant/chat")
async def assistant_chat(request: ChatRequest):
    symbol, timeframe = request.symbol.upper(), request.timeframe.lower()
    if symbol not in SYMBOLS or timeframe not in TIMEFRAMES:
        raise HTTPException(400, "Unsupported symbol or timeframe.")
    try:
        news_result = await news_client.latest("general")
        recent_signals = [s.model_dump(mode="json") for s in signals if s.symbol == symbol and s.timeframe == timeframe][:8]
        return await ai_assistant.reply(request.question, symbol, timeframe, news_result.get("items", []), recent_signals)
    except Exception as exc:
        raise HTTPException(502, f"AI assistant error: {exc}")
