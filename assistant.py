import httpx
from .config import Settings

class AITradingAssistant:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=45)

    async def close(self):
        await self.client.aclose()

    async def reply(self, question: str, symbol: str, timeframe: str, news: list, signals: list):
        if not self.settings.openai_api_key:
            return {"enabled": False, "reply": "AI chat is not configured yet. Add OPENAI_API_KEY to the backend environment, then restart the service."}
        system = (
          "You are CART3R SNIPER PRO, a cautious educational trading assistant. "
          "Explain Forex, XAUUSD and BTCUSD news alongside ICT concepts such as liquidity sweeps, FVG, order blocks, BOS and CHoCH. "
          "Use only supplied context for claims about current news/signals. If context is missing, say so. "
          "Distinguish reported facts from interpretation; never invent prices, entries, SL, TP, event times or headlines. "
          "Do not guarantee outcomes or tell the user to execute a trade. Mention volatility, spread and event risk when relevant. "
          "No broker execution is available. Keep answers clear and concise."
        )
        payload = {"model": self.settings.openai_model, "messages": [
          {"role": "system", "content": system},
          {"role": "user", "content": f"Market: {symbol}; timeframe: {timeframe}.\nLatest news context: {news[:8]}\nRecent ICT signal candidates: {signals[:8]}\nUser question: {question}"}
        ], "temperature": 0.2}
        response = await self.client.post("https://api.openai.com/v1/chat/completions",
          headers={"Authorization": f"Bearer {self.settings.openai_api_key}", "Content-Type": "application/json"}, json=payload)
        response.raise_for_status()
        data = response.json()
        return {"enabled": True, "reply": data["choices"][0]["message"]["content"], "model": self.settings.openai_model}
