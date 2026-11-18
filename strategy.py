from datetime import datetime, timezone
from uuid import uuid4
from .config import Settings
from .models import Candle, Signal

def _atr(candles: list[Candle], period: int) -> float:
    subset = candles[-(period + 1):]
    trs = []
    for i in range(1, len(subset)):
        c, p = subset[i], subset[i - 1]
        trs.append(max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)))
    return sum(trs) / len(trs) if trs else 0.0

def detect_signal(symbol: str, asset_class: str, timeframe: str,
                  candles: list[Candle], settings: Settings) -> Signal | None:
    # Last candle is ignored because it may still be forming.
    if len(candles) < max(settings.sweep_lookback + 5, settings.atr_period + 5):
        return None
    closed = candles[:-1]
    current = closed[-1]
    prior = closed[-(settings.sweep_lookback + 1):-1]
    if len(prior) < settings.sweep_lookback:
        return None

    prior_high = max(c.high for c in prior)
    prior_low = min(c.low for c in prior)
    atr = _atr(closed, settings.atr_period)
    if atr <= 0:
        return None

    body = abs(current.close - current.open)
    bullish = current.close > current.open
    bearish = current.close < current.open
    displacement = body >= atr * settings.displacement_atr_multiple

    # Sweep: wick trades through a prior range extreme, then candle closes back inside.
    buy_sweep = current.low < prior_low and current.close > prior_low
    sell_sweep = current.high > prior_high and current.close < prior_high

    # Structure break uses the preceding local swing range, excluding the current candle.
    swing = closed[-(settings.swing_lookback + 1):-1]
    swing_high = max(c.high for c in swing)
    swing_low = min(c.low for c in swing)
    bullish_bos = current.close > swing_high
    bearish_bos = current.close < swing_low

    # Three-candle fair value gap, measured on the latest closed candle.
    a, b, c = closed[-3], closed[-2], closed[-1]
    bull_fvg = a.high < c.low
    bear_fvg = a.low > c.high

    direction = None
    liquidity_level = 0.0
    fvg_low = fvg_high = 0.0
    confirmations = []

    if buy_sweep and bullish and displacement and bullish_bos and bull_fvg:
        direction = "BUY"
        liquidity_level = prior_low
        fvg_low, fvg_high = a.high, c.low
        confirmations = ["Sell-side liquidity sweep", "Bullish displacement", "Bullish BOS", "Bullish FVG"]
    elif sell_sweep and bearish and displacement and bearish_bos and bear_fvg:
        direction = "SELL"
        liquidity_level = prior_high
        fvg_low, fvg_high = c.high, a.low
        confirmations = ["Buy-side liquidity sweep", "Bearish displacement", "Bearish BOS", "Bearish FVG"]
    else:
        return None

    # Basic OB approximation: last opposing candle in a short lookback before displacement.
    ob = None
    search = closed[-6:-1]
    for candle in reversed(search):
        opposing = (direction == "BUY" and candle.close < candle.open) or (direction == "SELL" and candle.close > candle.open)
        if opposing:
            ob = (candle.low, candle.high)
            break
    if ob:
        confirmations.append("Opposing-candle order block found")

    entry = (fvg_low + fvg_high) / 2
    if direction == "BUY":
        stop = min(liquidity_level, ob[0] if ob else liquidity_level) - atr * 0.10
        risk = entry - stop
        if risk <= 0:
            return None
        target = entry + risk * settings.minimum_rr
    else:
        stop = max(liquidity_level, ob[1] if ob else liquidity_level) + atr * 0.10
        risk = stop - entry
        if risk <= 0:
            return None
        target = entry - risk * settings.minimum_rr

    # Reject zones too far from the latest close; avoids stale/overextended entries.
    if abs(current.close - entry) > atr * 2.5:
        return None

    rr = abs(target - entry) / abs(entry - stop)
    score = min(95, 55 + 8 * (len(confirmations) - 4))
    return Signal(
        id=str(uuid4()),
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        direction=direction,
        entry=round(entry, 8),
        stop_loss=round(stop, 8),
        take_profit=round(target, 8),
        risk_reward=round(rr, 2),
        confidence_score=score,
        confirmations=confirmations,
        liquidity_level=round(liquidity_level, 8),
        fvg_low=round(fvg_low, 8),
        fvg_high=round(fvg_high, 8),
        order_block_low=round(ob[0], 8) if ob else None,
        order_block_high=round(ob[1], 8) if ob else None,
        generated_at=datetime.now(timezone.utc),
        candle_time=current.time,
        note="Rule-based ICT-inspired candidate. Confirm spread, session, higher timeframe bias and retest manually.",
    )
