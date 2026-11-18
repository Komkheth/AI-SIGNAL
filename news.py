from datetime import datetime, timedelta, timezone
import httpx
from .config import Settings

class NewsClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=15)

    async def close(self):
        await self.client.aclose()

    async def latest(self, category: str = "general"):
        if not self.settings.finnhub_api_key:
            return {"enabled": False, "message": "Configure FINNHUB_API_KEY on the server to enable live news.", "items": []}
        now = datetime.now(timezone.utc)
        params = {"category": category, "token": self.settings.finnhub_api_key,
                  "from": (now - timedelta(hours=36)).strftime("%Y-%m-%d"),
                  "to": now.strftime("%Y-%m-%d")}
        response = await self.client.get(f"{self.settings.finnhub_base_url}/news", params=params)
        response.raise_for_status()
        raw = response.json()
        items = []
        for item in raw[:40] if isinstance(raw, list) else []:
            headline = str(item.get("headline", ""))
            summary = str(item.get("summary", ""))
            text = (headline + " " + summary).lower()
            positive = ["beats expectations", "rises", "surge", "higher", "bullish", "inflows", "cuts rates"]
            negative = ["misses expectations", "falls", "drop", "lower", "bearish", "outflows", "hike rates"]
            pos = sum(word in text for word in positive)
            neg = sum(word in text for word in negative)
            bias = "BULLISH" if pos > neg else "BEARISH" if neg > pos else "MIXED / UNCLEAR"
            items.append({"headline": headline, "summary": summary[:700],
                "source": item.get("source", "Unknown"), "url": item.get("url", ""),
                "published_at": item.get("datetime"), "category": item.get("category", category),
                "bias": bias, "related": item.get("related", ""),
                "warning": "Headline keyword bias is a rough filter, not verified market impact."})
        return {"enabled": True, "items": items}
