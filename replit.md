# Market Inefficiency Agent Platform

## Overview
This platform leverages AI agents to detect market inefficiencies, arbitrage opportunities, and systemic risks across global financial markets (crypto, equities, bonds, commodities, alternative data). It aims to provide a comprehensive monitoring solution with a web-based dashboard, real-time agent scheduling, and multi-channel notifications for various market sectors. The business vision is to offer a cutting-edge tool for financial analysts and traders to gain an edge by identifying actionable insights from vast amounts of market data.

## User Preferences
Preferred communication style: Simple, everyday language.

## Recent Changes
- **2025-11-01**: Added MarketCorrectionAgent - detects early warning signals for 10%+ market corrections using RSI, moving averages, VIX spikes, momentum exhaustion, and yield curve analysis
- **2025-11-01**: Added GeopoliticalRiskAgent - monitors 6 global hotspots (Taiwan, Ukraine, Middle East, China-US, North Korea, South China Sea) using NLP sentiment analysis and risk keywords
- **2025-08-18**: Fixed dashboard "no market data" display issue - resolved API route conflicts and metadata handling
- **2025-08-18**: Market data API now returns authentic findings: SPY (+2.44%), AAPL (+14.12%), TSLA (+8.58%) with 3,000+ total findings
- **2025-08-18**: Added JavaScript cache-busting and debugging to resolve frontend loading issues on live URL
- **2025-08-18**: Fixed production database separation issue - deployed site uses separate database from development
- **2025-08-18**: Added essential API keys (Alpha Vantage, Coinbase, GitHub, News API) for authentic market data collection
- **2025-08-18**: Accelerated agent scheduling from 15-60 minutes to 2-5 minutes for faster data flow
- **2025-08-18**: Verified authentic market data collection working - EquityMomentumAgent generating 36+ findings/hour, AltDataSignalAgent tracking GitHub AI/ML activity, real Coinbase crypto data flowing

## System Architecture

### Core Application Stack
- **Backend Framework**: Flask with SQLAlchemy ORM.
- **Database**: PostgreSQL.
- **Web Interface**: HTML templates, Bootstrap for responsive UI, JavaScript for real-time updates.
- **Task Scheduling**: APScheduler for background agent execution.
- **Health Monitoring**: Multi-endpoint health checks for deployment systems.

### Agent Architecture
- **Base Agent Pattern**: Agents inherit from `BaseAgent` for standardized plan/act/reflect operations.
- **Modular Design**: 11 specialized agents in the `agents/` directory for specific market sectors or data sources.
- **Registry System**: `AgentRegistry` manages agent lifecycle.
- **Scheduling System**: JSON-based configuration (`agent_schedule.json`) defines execution intervals.

### Data Integration Layer
- **Multi-Source Architecture**: Separate client classes for various data providers (e.g., Coinbase, Yahoo Finance, Etherscan, GitHub).
- **API Abstraction**: Standardized interfaces for different data types.
- **Error Handling**: Robust error handling and fallback mechanisms for data source failures.

### Database Schema
- **Findings Table**: Stores detected market inefficiencies with metadata.
- **Agent Status Table**: Tracks agent health, execution, and scheduling.
- **Market Data Table**: Caches market data for analysis.

### Notification System
- **Multi-Channel Support**: Email, Telegram, and SMS.
- **Configurable Alerts**: Severity-based filtering and customizable preferences.
- **Template-Based Messages**: Rich formatting for different channels.

### Web Dashboard
- **Real-Time Updates**: JavaScript-based with automatic data refresh.
- **Agent Management**: Interface for starting, stopping, and configuring agents.
- **Findings Browser**: Searchable and filterable view of findings.
- **Analytics Views**: Charts and visualizations for market trends and agent performance.
- **Health Check Endpoints**: Smart health detection for deployment systems vs. web browsers.

### Configuration Management
- **Environment-Based Config**: API keys and sensitive data via environment variables.
- **YAML Configuration**: Main application settings in `config.yaml`.
- **Agent-Specific Settings**: Individual agent configurations for thresholds and parameters.

## External Dependencies

### Financial Data APIs
- **Coinbase API**: Cryptocurrency prices and data (migrated from Binance).
- **Yahoo Finance**: Stock prices, indices, bonds, and economic indicators via `yfinance` library.
- **Etherscan API**: Ethereum blockchain data.

### Alternative Data Sources
- **GitHub API**: Repository metrics.
- **Patent APIs**: USPTO PatentsView.
- **Satellite Data**: Specialized providers for maritime and logistics.
- **News APIs**: NewsAPI and Google News RSS for geopolitical risk assessment.
- **NLP Processing**: NLTK VADER for sentiment analysis of news articles.

### Infrastructure Services
- **SMTP Servers**: For email notifications.
- **Telegram Bot API**: For real-time messaging.
- **SMS Providers**: For text message notifications.

### Python Libraries
- **Web Framework**: Flask, Flask-SQLAlchemy.
- **Data Processing**: pandas, numpy.
- **Machine Learning**: scikit-learn.
- **Market Data**: ccxt (for crypto exchanges), yfinance.
- **Task Scheduling**: APScheduler.
- **Visualization**: plotly.