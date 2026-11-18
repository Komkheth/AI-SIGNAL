# CART3R Sniper PRO — Multi-asset starter

Includes a responsive dashboard for Forex, XAUUSD (Gold), and BTCUSD; TradingView embedded charts; M1/M5/M15 selector; ICT-style checklist for liquidity sweep, FVG, Order Block, and BOS/CHoCH; demo signal preview; risk calculator; and Telegram integration placeholder.

## Run
Open `index.html` in a modern browser with internet access.

## Publish with GitHub Pages
1. Upload `index.html` to the root of a GitHub repository.
2. Open Settings → Pages.
3. Select Deploy from a branch, choose `main` and `/ (root)`, then Save.

## Live signals and Telegram
This is a front-end starter. The demo signal button shows fictional sample values and does not analyze live candles. A real signal engine requires:
- A reliable market-data API for Forex, Gold and BTCUSD OHLC candles.
- Backend strategy logic for liquidity sweeps, displacement/BOS/CHoCH, FVG and Order Block retests.
- Multi-timeframe confirmation, spread/session filters, invalidation, and risk controls.
- A secure backend API for the website to read signals.
- A Telegram bot integrated server-side. Do not expose bot tokens or broker/exchange credentials in `index.html`.

Backtest and paper-trade thoroughly. This site does not execute trades or provide guaranteed signals.
