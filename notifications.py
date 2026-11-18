import httpx
from .config import Settings
from .models import Signal

class TelegramNotifier:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=15.0)

    async def close(self):
        await self.client.aclose()

    async def send_signal(self, signal: Signal):
        if not self.settings.telegram_enabled:
            return {"sent": False, "reason": "Telegram notifications are disabled."}
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return {"sent": False, "reason": "Telegram credentials are not configured."}
        arrow = "🟢" if signal.direction == "BUY" else "🔴"
        text = (
            f"{arrow} CART3R SNIPER PRO — {signal.direction}\\n"
            f"Market: {signal.symbol} ({signal.asset_class})\\n"
            f"Timeframe: {signal.timeframe}\\n"
            f"Entry: {signal.entry}\\nSL: {signal.stop_loss}\\nTP: {signal.take_profit}\\n"
            f"RR: 1:{signal.risk_reward}\\n"
            f"Confirmations: {', '.join(signal.confirmations)}\\n"
            f"Signal ID: {signal.id}\\n"
            "Candidate signal only — verify before trading. No order was placed."
        )
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        response = await self.client.post(url, json={"chat_id": self.settings.telegram_chat_id, "text": text})
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError("Telegram API did not accept the message.")
        return {"sent": True}
