# Market Inefficiency Detection Agents

This document provides a comprehensive overview of all 12 AI agents in the Market Inefficiency Detection Platform.

## Agent Architecture

All agents inherit from `BaseAgent` which provides:
- Standardized `analyze()` method that returns findings
- Automatic error handling via `run()` wrapper
- Configuration loading from `config.yaml`
- Finding creation via `create_finding()` helper
- Logging and error handling

## Agent Summary Table

| Agent | Purpose | Data Sources | Schedule | Key Indicators |
|-------|---------|--------------|----------|----------------|
| HeartbeatAgent | System health | Internal | 1 min | Uptime, connectivity |
| ArbitrageFinderAgent | Cross-exchange price gaps | Coinbase, Kraken | 2 min | BTC, ETH, ADA, SOL spreads |
| EquityMomentumAgent | Stock momentum divergences | Yahoo Finance | 5 min | RSI, MACD, volume |
| CryptoFundingRateAgent | Crypto funding stress | Coinbase | 5 min | Spot-volatility proxy |
| BondStressAgent | Fixed-income stress | Yahoo Finance | 5 min | TLT, ^TNX, yield curve |
| SentimentDivergenceAgent | Price vs sentiment gaps | News API, GitHub | 5 min | Sentiment scores |
| AltDataSignalAgent | Alternative data signals | GitHub API | 5 min | AI/ML repo activity |
| WhaleWalletWatcherAgent | Large crypto wallet flows | Etherscan | 5 min | ETH whale movements |
| MacroWatcherAgent | Macro indicator swings | Yahoo Finance | 5 min | VIX, DXY, commodities |
| MarketCorrectionAgent | Correction early warnings | Yahoo Finance | 5 min | SPY, QQQ, VIX, RSI |
| GeopoliticalRiskAgent | Global hotspot monitoring | News API, RSS | 5 min | 6 hotspot regions |
| GreatestTradeAgent | Systemic risk detection | XLRE, CDS models | 5 min | Bubbles, CDS, tranches |

---

## Detailed Agent Descriptions

### 1. HeartbeatAgent
**File:** `agents/heartbeat_agent.py`  
**Purpose:** Generates periodic heartbeat signals to verify the platform is operational.  
**Data Sources:** Internal system checks  
**Schedule:** Every 1 minute  
**Key Outputs:** System operational status, uptime confirmation  

---

### 2. ArbitrageFinderAgent
**File:** `agents/arbitrage_finder_agent.py`  
**Purpose:** Detects cross-exchange cryptocurrency price discrepancies that could represent arbitrage opportunities.  
**Data Sources:** Coinbase API, Kraken API  
**Schedule:** Every 2 minutes  
**Monitored Assets:** BTC/USD, ETH/USD, ADA/USD, SOL/USD, MATIC/USD  
**Key Thresholds:**
- Price spread > 0.5% = potential arbitrage opportunity
- Calculates buy/sell exchange recommendations

---

### 3. EquityMomentumAgent
**File:** `agents/equity_momentum_agent.py`  
**Purpose:** Identifies momentum divergences and trend changes in major equities.  
**Data Sources:** Yahoo Finance (yfinance)  
**Schedule:** Every 5 minutes  
**Monitored Assets:** SPY, QQQ, AAPL, TSLA, NVDA, MSFT, GOOGL, AMZN  
**Key Indicators:**
- Relative Strength Index (RSI)
- Moving Average Convergence Divergence (MACD)
- Volume anomalies
- Price momentum

---

### 4. CryptoFundingRateAgent
**File:** `agents/crypto_funding_rate_agent.py`  
**Purpose:** Monitors cryptocurrency markets for funding rate stress indicators.  
**Data Sources:** Coinbase API  
**Schedule:** Every 5 minutes  
**Key Indicators:**
- Spot price volatility as funding proxy
- Price movement patterns
- Market stress signals

---

### 5. BondStressAgent
**File:** `agents/bond_stress_agent.py`  
**Purpose:** Tracks fixed-income market stress and yield curve anomalies.  
**Data Sources:** Yahoo Finance  
**Schedule:** Every 5 minutes  
**Monitored Assets:** TLT (20+ Year Treasury ETF), ^TNX (10-Year Treasury Yield)  
**Key Indicators:**
- Yield curve inversions
- Treasury volatility
- Credit spread changes

---

### 6. SentimentDivergenceAgent
**File:** `agents/sentiment_divergence_agent.py`  
**Purpose:** Detects divergences between asset price movements and market sentiment.  
**Data Sources:** News API, GitHub activity  
**Schedule:** Every 5 minutes  
**Key Analysis:**
- News sentiment scoring using NLP
- Price-sentiment correlation gaps
- Social media activity proxies

---

### 7. AltDataSignalAgent
**File:** `agents/alt_data_signal_agent.py`  
**Purpose:** Uses alternative data (tech repository activity) as market signals.  
**Data Sources:** GitHub API  
**Schedule:** Every 5 minutes  
**Key Metrics:**
- AI/ML repository star counts
- Commit activity in trending repos
- Developer activity patterns

---

### 8. WhaleWalletWatcherAgent
**File:** `agents/whale_wallet_watcher_agent.py`  
**Purpose:** Monitors large Ethereum wallet transactions that may signal market moves.  
**Data Sources:** Etherscan API  
**Schedule:** Every 5 minutes  
**Key Thresholds:**
- Transactions > 1000 ETH
- Exchange inflow/outflow patterns
- Whale accumulation signals

---

### 9. MacroWatcherAgent
**File:** `agents/macro_watcher_agent.py`  
**Purpose:** Tracks macroeconomic indicator swings and their market implications.  
**Data Sources:** Yahoo Finance  
**Schedule:** Every 5 minutes  
**Monitored Indicators:**
- VIX (Volatility Index)
- DXY (US Dollar Index)
- Gold (GC=F)
- Oil (CL=F)

---

### 10. MarketCorrectionAgent
**File:** `agents/market_correction_agent.py`  
**Purpose:** Detects early warning signals for potential 10%+ market corrections.  
**Data Sources:** Yahoo Finance  
**Schedule:** Every 5 minutes  
**Monitored Assets:** SPY, QQQ, DIA, IWM (indices), VIX, TLT, ^TNX  
**Warning Signals:**
- RSI overbought/oversold conditions
- 50/200-day moving average crossovers
- VIX spike detection (>25)
- Momentum exhaustion patterns
- Yield curve stress indicators

---

### 11. GeopoliticalRiskAgent
**File:** `agents/geopolitical_risk_agent.py`  
**Purpose:** Monitors global geopolitical hotspots using NLP sentiment analysis.  
**Data Sources:** News API, Google News RSS  
**Schedule:** Every 5 minutes  
**Monitored Regions:**
1. Taiwan Strait
2. Ukraine-Russia
3. Middle East (Israel-Iran)
4. US-China relations
5. North Korea
6. South China Sea

**Analysis Methods:**
- NLTK VADER sentiment analysis
- Risk keyword detection
- News volume tracking

---

### 12. GreatestTradeAgent
**File:** `agents/greatest_trade_agent.py`  
**Purpose:** Detects systemic market inefficiencies inspired by "The Greatest Trade Ever" - combining macro bubble detection, CDS pricing analysis, and structured product risk assessment.  
**Data Sources:** Yahoo Finance (XLRE), Internal CDS models, Structured product models  
**Schedule:** Every 5 minutes  

**Modular Components:**
- `agents/analyzers/macro_bubble_detector.py` - Housing/credit bubble detection
- `agents/analyzers/cds_analyzer.py` - CDS pricing inefficiency analysis
- `agents/analyzers/structured_product_analyzer.py` - Tranche risk assessment

**Key Analysis:**
- **Macro Bubbles:** Price-to-income ratios, credit growth thresholds
- **CDS Pricing:** Compares spreads vs expected loss for AAA through BB ratings
- **Structured Products:** Analyzes tranche risk under correlated vs independent defaults
- **Combined Signal:** Triggers "Greatest Trade" alert when multiple systemic conditions align

**Monitored Ratings:** AAA, AA, A, BBB, BB  
**Key Thresholds:**
- Price-to-income > 1.25x historical average = bubble warning
- CDS mispricing > 1% = trading opportunity
- Tranche risk multiplier > 3x = hidden systemic risk

---

## Environment Variables Required

| Variable | Used By | Purpose |
|----------|---------|---------|
| `COINBASE_API_KEY` | ArbitrageFinderAgent, CryptoFundingRateAgent | Coinbase API access |
| `COINBASE_SECRET` | ArbitrageFinderAgent, CryptoFundingRateAgent | Coinbase API authentication |
| `NEWS_API_KEY` | SentimentDivergenceAgent, GeopoliticalRiskAgent | NewsAPI access |
| `GITHUB_TOKEN` | AltDataSignalAgent | GitHub API access |
| `ALPHA_VANTAGE_API_KEY` | Various agents | Alternative market data |

---

## Adding a New Agent

1. Create a new file in `agents/` inheriting from `BaseAgent`
2. Implement the `analyze()` method that returns a list of findings
3. Use `create_finding()` helper to generate standardized findings
4. Add configuration to `agent_schedule.json` with execution interval
5. Register in `agents/__init__.py` AVAILABLE_AGENTS list

## Testing

Run agent tests with:
```bash
python -m pytest tests/ -v
```
