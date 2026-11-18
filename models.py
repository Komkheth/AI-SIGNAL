from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Timeframe = Literal["1m", "5m", "15m"]
Direction = Literal["BUY", "SELL"]

class Candle(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

class Signal(BaseModel):
    id: str
    symbol: str
    asset_class: str
    timeframe: Timeframe
    direction: Direction
    status: Literal["ACTIVE", "INVALIDATED", "EXPIRED"] = "ACTIVE"
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    confidence_score: int = Field(ge=0, le=100)
    confirmations: list[str]
    liquidity_level: float
    fvg_low: float
    fvg_high: float
    order_block_low: float | None = None
    order_block_high: float | None = None
    generated_at: datetime
    candle_time: datetime
    note: str

class HealthResponse(BaseModel):
    status: str
    app: str
    execution: str = "DISABLED"
    signal_engine: str
