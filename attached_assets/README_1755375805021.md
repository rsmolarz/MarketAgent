
# 📊 Market Inefficiency Agent Platform

A modular, intelligent anomaly detection system that monitors global markets for inefficiencies, events, and signals — across macroeconomics, equities, crypto, commodities, and alternative data.

---

## 🚀 Features

- ✅ 24+ Modular AI Agents (Crypto, Equities, Macro, Options, Patents, Whale Wallets, etc.)
- 🔌 Real API integrations (Binance, GitHub, Etherscan, etc.)
- 📊 Plotly Dashboard UI + FastAPI Backend
- 🧠 Scheduling system for continuous monitoring
- 📩 Notification system (Email, SMS, Telegram)
- 🧪 Unit tests for every agent
- 💾 Local findings storage with SQLite
- 🧱 Easily extensible for custom agents
- 🟦 Replit-ready + Docker + pip installable

---

## 🧠 Example Agents

| Name                       | Description                               |
|----------------------------|-------------------------------------------|
| `MacroWatcherAgent`        | Detects macroeconomic anomalies (2008-type) |
| `ArbitrageFinderAgent`     | Finds crypto arbitrage opportunities       |
| `WhaleWalletWatcherAgent`  | Detects large ETH wallet movements         |
| `OptionsSkewAgent`         | Flags high put-call skew                   |
| `PatentSurgeAgent`         | AI/Crypto patent filings surge             |
| `SentimentDivergenceAgent` | Mismatch between price & social sentiment  |
| `SatelliteDataAgent`       | Tracks oil tankers via satellite data      |

---

## 🖥 Replit Instructions

1. Upload all project files to your Replit workspace
2. Set the entrypoint to:
   ```bash
   uvicorn ui.server:app --host 0.0.0.0 --port 10000
   ```
3. Create `.env` (optional) for secrets like:
   ```env
   GITHUB_TOKEN=
   ETHERSCAN_API_KEY=
   TELEGRAM_TOKEN=
   ```
4. Replit will expose the dashboard at your public URL

---

## 🧪 Running Tests

```bash
python3 -m unittest discover tests
```

---

## 🔧 Run Specific Agents

```bash
python main.py --agents MacroWatcherAgent AltDataSignalAgent
```

Or control via UI toggles in the dashboard.

---

## 📦 Deploy as Python Package

Install locally:

```bash
pip install .
market-agent
```

---

## 🐳 Run via Docker

```bash
docker build -t market-agent .
docker run -p 10000:10000 market-agent
```

---

## 🔗 API Endpoints

| Route            | Description                  |
|------------------|------------------------------|
| `/findings`      | Get or post agent findings   |
| `/schedule`      | Add/remove agent schedules   |
| `/ohlcv`         | (Future) Price candle API    |

---

## 📂 Project Structure

```
├── agents/           # All agents (each file = 1 agent)
├── data_sources/     # API logic
├── notifiers/        # Email/SMS/Telegram alerts
├── ui/               # FastAPI server + dashboard
├── scheduler.py      # APScheduler logic
├── main.py           # CLI entrypoint
├── tests/            # Unit tests
```

---

Built with ❤️ by [YourName]
