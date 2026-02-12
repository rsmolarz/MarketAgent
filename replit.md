# Market Inefficiency Agent Platform

## Overview
This platform uses AI agents to identify market inefficiencies, arbitrage opportunities, and systemic risks across global financial markets (crypto, equities, bonds, commodities, alternative data). It provides a web-based dashboard, real-time agent scheduling, and multi-channel notifications. The goal is to equip financial analysts and traders with actionable insights from vast market data.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Core Application Stack
- **Backend Framework**: Flask with SQLAlchemy ORM.
- **Database**: PostgreSQL.
- **Web Interface**: HTML templates, Bootstrap for responsive UI, JavaScript for real-time updates.
- **Task Scheduling**: APScheduler for background agent execution.
- **Health Monitoring**: Multi-endpoint health checks.

### Agent Architecture
- **Base Agent Pattern**: Agents inherit from `BaseAgent` for standardized operations.
- **Modular Design**: Specialized agents and reusable analysis components (`agents/analyzers/`).
- **Registry System**: `AgentRegistry` manages agent lifecycle.
- **Scheduling System**: JSON-based configuration (`agent_schedule.json`) for execution intervals.
- **Meta-Agent**: Automates agent ranking, weighting, and auto-disabling based on forward-return labeling and performance metrics.
- **LLM Regime Council**: Multi-model LLM ensemble (GPT, Claude, Gemini) for confidence-weighted regime assessment, disagreement detection, and uncertainty management, including decay curves and early warning systems.
- **Meta-Supervisor**: Governance layer for agent monitoring, telemetry, safety (kill-switches), and promotion policies.
- **Builder Agent**: Outputs complete file contents, incorporates safety workflow with risk scoring, admin review UI, sandboxed execution, and memory for learning from rejected proposals.

### Data Integration Layer
- **Multi-Source Architecture**: Separate client classes for various data providers.
- **API Abstraction**: Standardized interfaces for different data types.
- **Error Handling**: Robust error handling and fallback mechanisms.

### Database Schema
- **Tables**: Users, OAuth, Whitelist, Findings, Agent Status, Market Data, AgentMemory, ApprovalEvent, UncertaintyEvent, DistressedDeal.

### Distressed Property Deal Pipeline
- **DistressedDeal Model**: Tracks distressed properties through acquisition lifecycle with stage progression (screened → underwritten → LOI → closed, plus "dead" escape).
- **DealValuation Model**: Pricing bands with Zestimate, distressed_price (55-75% of Zestimate), recovery_value, and recovery_multiple calculation.
- **ICVote Model**: Human vs AI vote tracking (ACT/WATCH/PASS) with automatic override detection when humans override AI recommendations.
- **IC Memo Service**: LLM-powered Investment Committee memo generation for institutional-grade distressed asset analysis (`services/distressed_ic_memo.py`).
- **CRM Handoff**: Webhook-based integration with external CRMs and deal rooms (`services/crm_handoff.py`). Supports multiple CRM configs via env vars (CRM_WEBHOOK_URL, CRM_1_WEBHOOK_URL, etc.).
- **Deal Kill Rules Engine**: Automated deal killing based on stage timeout (14/30/21 days), IC inactivity, missing docs, and regime normalization (`services/deal_kill_rules.py`).
- **Portfolio Exposure**: Weighted capital exposure by stage (screened: 0%, underwritten: 30%, LOI: 60%, closed: 100%).
- **Deal Routes**: Full CRUD operations, stage progression, memo generation, IC voting, valuation, exposure API, and CRM sync (`routes/deals.py`).
- **Kanban UI**: Pipeline visualization at `/deals/` with stage cards, IC voting, pricing bands, memo buttons, and CRM sync actions.
- **ZillowDistressAgent**: Metro-level distress analysis using Zillow Research datasets, identifies liquidity freeze, affordability shock, oversupply, and rent compression regimes (`agents/zillow_distress_agent.py`).
- **DistressedDealEvaluatorAgent**: Institutional-grade distressed debt/equity evaluation using Moyer's "Distressed Debt Analysis" frameworks. Features Altman Z-Score, EBITDA normalization (EBITDAR), multiple derivation from DCF theory, capital structure analysis, fulcrum security identification, recovery waterfall modeling with plan vs true value scenarios, and capital structure arbitrage detection (`agents/distressed_deal_evaluator_agent.py`).

### Authentication System
- **Replit Auth**: OAuth-based authentication using Replit.
- **Whitelist Control**: Only whitelisted emails can access the platform, managed via an `/admin` panel.
- **ADMIN_EMAILS**: Environment variable for initial admin seeding.

### Notification System
- **Multi-Channel Support**: Email, Telegram, and SMS.
- **Configurable Alerts**: Severity-based filtering.

### Web Dashboard
- **Real-Time Updates**: JavaScript-based with automatic data refresh.
- **Agent Management**: Interface for starting, stopping, and configuring agents.
- **Findings Browser**: Searchable and filterable view of findings.
- **Analytics Views**: Charts and visualizations for market trends, agent performance (e.g., SPY price with agent signals, decay curve visualizations, agent failure heatmap).

### Configuration Management
- **Environment-Based Config**: API keys and sensitive data.
- **YAML Configuration**: Main application settings in `config.yaml`.
- **Agent-Specific Settings**: Individual agent configurations.

## External Dependencies

### Financial Data APIs
- **Coinbase API**: Cryptocurrency prices and data.
- **Yahoo Finance**: Stock prices, indices, bonds, and economic indicators via `yfinance` library.
- **Schwab/Thinkorswim API**: Real-time quotes, price history, options chains, movers, market hours via OAuth 2.0 (`data_sources/schwab_client.py`). 30-min access token auto-refresh, 7-day refresh token requires re-auth. OAuth routes at `/oauth/schwab/authorize` and `/oauth/callback/schwab`. Falls back as secondary data source in `price_loader.py` when Yahoo Finance fails. Status endpoint at `/api/schwab_status`.
- **Etherscan API**: Ethereum blockchain data.

### Alternative Data Sources
- **GitHub API**: Repository metrics.
- **Patent APIs**: USPTO PatentsView.
- **Satellite Data**: Specialized providers for maritime and logistics.
- **News APIs**: NewsAPI and Google News RSS.
- **NLP Processing**: NLTK VADER for sentiment analysis.

### Infrastructure Services
- **SMTP Servers**: For email notifications.
- **Telegram Bot API**: For real-time messaging.
- **SMS Providers**: For text message notifications.

### Python Libraries
- **Web Framework**: Flask, Flask-SQLAlchemy.
- **Data Processing**: pandas, numpy.
- **Machine Learning**: scikit-learn.
- **Market Data**: ccxt, yfinance.
- **Task Scheduling**: APScheduler.
- **Visualization**: plotly, matplotlib.
- **LLMs**: anthropic, google-generativeai.