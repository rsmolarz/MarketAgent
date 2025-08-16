# Market Inefficiency Agent Platform

## Overview

This is a comprehensive market inefficiency detection platform that uses AI agents to monitor global financial markets for anomalies, arbitrage opportunities, and systemic risks. The platform consists of multiple specialized agents that analyze different market sectors including crypto, equities, bonds, commodities, and alternative data sources. It features a web-based dashboard built with Flask, real-time agent scheduling, and multi-channel notification systems.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Application Stack
- **Backend Framework**: Flask with SQLAlchemy ORM for database operations
- **Database**: PostgreSQL for both development and production environments
- **Web Interface**: HTML templates with Bootstrap for responsive UI and JavaScript for real-time updates
- **Task Scheduling**: APScheduler for background agent execution with configurable intervals
- **Health Monitoring**: Multi-endpoint health checks for deployment systems and monitoring

### Agent Architecture
- **Base Agent Pattern**: All agents inherit from `BaseAgent` class providing standardized interface for plan/act/reflect operations
- **Modular Design**: 24+ specialized agents in the `agents/` directory, each focusing on specific market sectors or data sources
- **Registry System**: `AgentRegistry` manages agent lifecycle, loading, and execution
- **Scheduling System**: JSON-based configuration (`agent_schedule.json`) defines execution intervals for each agent

### Data Integration Layer
- **Multi-Source Architecture**: Separate client classes for different data providers (Binance, Etherscan, Yahoo Finance, GitHub)
- **API Abstraction**: Standardized interfaces for cryptocurrency exchanges, blockchain data, financial markets, and alternative data
- **Error Handling**: Robust error handling and fallback mechanisms for data source failures

### Database Schema
- **Findings Table**: Stores detected market inefficiencies with metadata including severity, confidence, and agent source
- **Agent Status Table**: Tracks agent health, execution counts, error rates, and scheduling information
- **Market Data Table**: Caches market data for analysis and historical tracking

### Notification System
- **Multi-Channel Support**: Email, Telegram, and SMS notification capabilities
- **Configurable Alerts**: Severity-based filtering and customizable notification preferences
- **Template-Based Messages**: Rich formatting for different notification channels

### Web Dashboard
- **Real-Time Updates**: JavaScript-based dashboard with automatic data refresh
- **Agent Management**: Interface for starting, stopping, and configuring agents
- **Findings Browser**: Searchable and filterable view of detected market inefficiencies
- **Analytics Views**: Charts and visualizations for market trends and agent performance
- **Health Check Endpoints**: Smart health detection for deployment systems vs. web browsers

### Configuration Management
- **Environment-Based Config**: API keys and sensitive data managed through environment variables
- **YAML Configuration**: Main application settings in `config.yaml` with defaults
- **Agent-Specific Settings**: Individual agent configurations for thresholds and parameters

## External Dependencies

### Financial Data APIs
- **Binance API**: Cryptocurrency prices, funding rates, and perpetual swap data
- **Yahoo Finance**: Stock prices, indices, bonds, and economic indicators via yfinance library
- **Etherscan API**: Ethereum blockchain data and wallet transaction monitoring

### Alternative Data Sources
- **GitHub API**: Repository metrics for technology trend analysis
- **Patent APIs**: USPTO PatentsView for innovation tracking
- **Satellite Data**: Maritime and logistics monitoring through specialized providers
- **News APIs**: Regulatory and geopolitical risk assessment

### Infrastructure Services
- **SMTP Servers**: Email notifications through configurable SMTP providers
- **Telegram Bot API**: Real-time messaging for critical alerts
- **SMS Providers**: Text message notifications for high-priority findings

### Python Libraries
- **Web Framework**: Flask, Flask-SQLAlchemy for web application and database ORM
- **Data Processing**: pandas, numpy for numerical analysis and data manipulation
- **Machine Learning**: scikit-learn for anomaly detection and pattern recognition
- **Market Data**: ccxt for cryptocurrency exchange integration, yfinance for traditional markets
- **Task Scheduling**: APScheduler for background job management
- **Visualization**: plotly for interactive charts and dashboards

### Development Tools
- **Package Management**: pip with requirements.txt for dependency management
- **Code Organization**: setuptools for package distribution and entry points
- **Testing Framework**: Built-in Python unittest for agent validation

## Recent Changes

### Deployment & Coinbase Integration (Aug 16, 2025)
- ✅ Successfully migrated from Binance to Coinbase API for global accessibility
- ✅ Fixed all agent import dependencies and removed binance_client references
- ✅ Implemented CoinbaseClient with proper ccxt.coinbase integration
- ✅ All 8 agents now operational with real-time market data collection
- ✅ Platform successfully detecting market inefficiencies (AAPL volume divergence found)
- ✅ Manual agent execution endpoints working perfectly (/api/agents/{name}/run)
- ✅ Fixed duplicate health check endpoint conflicts causing startup failures
- ✅ Implemented smart health check detection on root path (/) for deployment systems
- ✅ Added dedicated health check endpoints: `/health`, `/healthz` (fallback), `/api/health` (JSON)
- ✅ Enhanced health check detection for Google Cloud Run, AWS ALB, and Kubernetes probes
- ✅ Resolved scheduler initialization issues with improved error handling
- ✅ Added production-ready logging configuration in main.py
- ✅ Implemented graceful degradation - app starts even if components fail
- ✅ All health endpoints return 200 status codes as required by deployment systems
- ✅ Maintained full web dashboard functionality for normal browser requests
- ✅ Coinbase API credentials properly configured in Replit Secrets

### Production Deployment Fixes (Aug 16, 2025)
- ✅ Fixed LSP type errors in CoinbaseClient return types
- ✅ Enhanced root route (/) health check detection for all major deployment platforms
- ✅ Added comprehensive health check endpoints: `/healthz`, `/health`, `/ping`, `/ready`, `/live`
- ✅ Implemented lightweight API health endpoints: `/api/health`, `/api/healthz`
- ✅ Optimized health checks to return immediate 200 OK without database operations
- ✅ Verified all health endpoints respond correctly with curl testing
- ✅ Enhanced user agent detection for deployment systems (Render, Heroku, Netlify, etc.)
- ✅ Application fully ready for production deployment on any platform