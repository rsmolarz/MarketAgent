
import os
import logging
from datetime import datetime

from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

# Phase 4 Extensions: Initialize system services
# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _seed_whitelist(db):
    """Ensure required admin whitelist entries exist with correct roles on every startup."""
    from models import Whitelist, User

    REQUIRED_ENTRIES = [
        {'email': 'rsmolarz@rsmolarz.com', 'role': 'super_admin'},
        {'email': 'rsmolarz@hotmail.com', 'role': 'super_admin'},
        {'email': 'bfunston@storpartners.com', 'role': 'admin'},
    ]

    try:
        for entry_data in REQUIRED_ENTRIES:
            email = entry_data['email'].lower()
            role = entry_data['role']
            existing = Whitelist.query.filter_by(email=email).first()
            if not existing:
                entry = Whitelist(email=email, role=role, added_by='system')
                entry.added_at = datetime.utcnow()
                db.session.add(entry)
                logger.info(f"Seeded whitelist: {email} as {role}")
            elif existing.role != role:
                existing.role = role
                logger.info(f"Updated whitelist role: {email} to {role}")

            user = User.query.filter_by(email=email).first()
            if user and user.role != role:
                user.role = role
                user.is_admin = role in ('super_admin', 'admin')
                logger.info(f"Synced user role: {email} to {role}")

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Whitelist seeding failed: {e}")


def _apply_finding_council_migration(db):
    """Add LLM council columns to findings table if they don't exist."""
    from sqlalchemy import inspect, text

    try:
        inspector = inspect(db.engine)
        existing_columns = {
            col['name']
            for col in inspector.get_columns('findings')
        }

        new_columns = [
            ("consensus_action", "VARCHAR(16)"),
            ("consensus_confidence", "FLOAT"),
            ("llm_votes", "JSON"),
            ("llm_disagreement", "BOOLEAN DEFAULT FALSE"),
            ("auto_analyzed", "BOOLEAN DEFAULT FALSE"),
            ("alerted", "BOOLEAN DEFAULT FALSE"),
            ("ta_regime", "VARCHAR(32)"),
            ("analyzed_at", "TIMESTAMP"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    db.session.execute(
                        text(
                            f"ALTER TABLE findings ADD COLUMN {col_name} {col_type}"
                        ))
                    db.session.commit()
                    logger.info(f"Added column {col_name} to findings table")
                except Exception as e:
                    db.session.rollback()
                    logger.debug(f"Column {col_name} may already exist: {e}")
    except Exception as e:
        logger.debug(f"Migration check skipped: {e}")


# ------------------------------------------------------------------------------
# Flask App Factory
# ------------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret")

    # Required for Replit / proxies
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ------------------------------------------------------------------------------
    # Database config
    # ------------------------------------------------------------------------------
    database_url = os.environ.get("DATABASE_URL",
                                  "sqlite:///market_inefficiency.db")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 300,
        },
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='None',
    )

    # ------------------------------------------------------------------------------
    # Init DB
    # ------------------------------------------------------------------------------
    from models import db
    db.init_app(app)

    with app.app_context():
        try:
            import models
            db.create_all()
            logger.info("Database tables created successfully")

            _apply_finding_council_migration(db)
            _seed_whitelist(db)
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    # ------------------------------------------------------------------------------
    # Scheduler - DEFERRED initialization for fast startup
    # ------------------------------------------------------------------------------
    def init_scheduler_deferred():
        """Initialize scheduler in background after app is ready"""
        import threading
        import time

        def delayed_init():
            time.sleep(15)  # Wait 15 seconds for app to be fully ready and health checks to pass
            try:
                with app.app_context():
                    from scheduler import AgentScheduler
                    scheduler = AgentScheduler(app)
                    app.extensions["scheduler"] = scheduler
                    logger.info(
                        "AgentScheduler initialized successfully (deferred)")
            except Exception as e:
                logger.error(f"Scheduler failed to initialize: {e}")

        thread = threading.Thread(target=delayed_init, daemon=True)
        thread.start()

    if not app.extensions.get("scheduler"):
        init_scheduler_deferred()
        logger.info("Scheduler initialization deferred for fast startup")

    # ------------------------------------------------------------------------------
    # ROUTES - Register Blueprints
    # ------------------------------------------------------------------------------
    from routes.dashboard import dashboard_bp
    from routes.admin import admin_bp
    from routes.api import api_bp
    from routes.admin_proposals import admin_proposals_bp
    from routes.uncertainty import bp as uncertainty_bp
    from routes.ta import ta_bp
    from routes.analyze import bp as analyze_bp
    from routes.ensemble import bp as ensemble_bp
    from routes.governor import bp as governor_bp
    from routes.eval import bp as eval_bp
    from routes.insights import bp as insights_bp
    from routes.deals import deals_bp
    from routes.distressed_platform import distressed_platform_bp
    from routes.monitoring import monitoring_bp
    from replit_auth import make_replit_blueprint, init_auth
    from oauth_logins import oauth_bp

    init_auth(app)
    replit_bp = make_replit_blueprint()

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(admin_proposals_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(uncertainty_bp)
    app.register_blueprint(ta_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(ensemble_bp)
    app.register_blueprint(governor_bp)
    app.register_blueprint(eval_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(deals_bp)
    app.register_blueprint(distressed_platform_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(replit_bp, url_prefix='/auth')
    app.register_blueprint(oauth_bp)

    @app.route("/.well-known/apple-developer-domain-association.txt")
    def apple_domain_verification():
        verification_content = os.getenv('APPLE_DOMAIN_VERIFICATION', '')
        from flask import Response
        return Response(verification_content, mimetype='text/plain')

    @app.route("/landing")
    def landing():
        return render_template("landing.html")

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    @app.route("/status")
    def status():
        return jsonify({
            "service": "Market Inefficiency Detection Platform",
            "status": "running",
            "timestamp": datetime.utcnow().isoformat()
        })

    # FAST health check - responds immediately for deployment systems
    @app.route("/healthz")
    def healthz():
        """Ultra-fast health check for Cloud Run - NO database or external calls"""
        return "OK", 200

    # Additional health check endpoints for compatibility
    @app.route("/health")
    def health():
        """Fast health check endpoint"""
        return "OK", 200

    @app.route("/ready")
    def ready():
        """Readiness probe endpoint"""
        return "OK", 200

    @app.route("/live")
    def live():
        """Liveness probe endpoint"""
        return "OK", 200

    return app


# ------------------------------------------------------------------------------
# App instance
# ------------------------------------------------------------------------------
app = create_app()

# ------------------------------------------------------------------------------
# Local run (Replit / dev)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)



# Create the three new agent files (WeatherImpactAgent, NewsAnalysisAgent, CommodityTrendAgent)
import os
# Define the three agent files with their complete code
agent_files = {
        'agents/weather_impact_agent.py': '''"""
        Weather Impact Agent
        
        Analyzes weather data impacts on commodity and financial markets.
        Detects weather patterns that influence trading prices.
        """
        
        import requests
        from typing import List, Dict, Any
        from base_agent import BaseAgent
        from config import Config
        
        
        class WeatherImpactAgent(BaseAgent):
            """
                Weather Impact Agent
                    
                        Monitors weather events and their market impacts on commodities and financials.
                            """
                            
                                def __init__(self):
                                        super().__init__()
                                                self.api_key = Config.get("weather_api_key", "")
                                                        self.weather_symbols = ["CORN", "SOYBEANS", "CRUDE", "NATGAS"]
                                                                self.min_impact_threshold = Config.get("min_weather_impact", 0.05)
                                                                
                                                                    def analyze(self) -> List[Dict[str, Any]]:
                                                                            """
                                                                                    Analyze weather impacts on commodity prices.
                                                                                            """
                                                                                                    findings = []
                                                                                                            
                                                                                                                    try:
                                                                                                                                # Get weather data
                                                                                                                                            weather_data = self._fetch_weather_data()
                                                                                                                                                        
                                                                                                                                                                    if not weather_data:
                                                                                                                                                                                    return findings
                                                                                                                                                                                                
                                                                                                                                                                                                            # Analyze impact on each commodity
                                                                                                                                                                                                                        for symbol in self.weather_symbols:
                                                                                                                                                                                                                                        impact = self._analyze_symbol_impact(symbol, weather_data)
                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                        if impact and abs(impact['''confidence']) >= self.min_impact_threshold:
                        findings.append({
                                                    'type': 'Weather Impact Signal',
                                                    'symbol': symbol,
                                                    'description': f"Weather pattern detected: {impact['pattern']}",
                                                    'confidence': impact['confidence'],
                                                    'impact': impact['price_impact'],
                                                    'timestamp': impact['timestamp']
                        })
    except Exception as e:
            self.logger.error(f"Error analyzing weather impacts: {e}")

        return findings

    def _fetch_weather_data(self) -> Dict[str, Any]:
                """Fetch current weather data from API"""""
                try:
                                # Placeholder for actual weather API call
                                return {'temperature': 0, 'pressure': 0, 'humidity': 0}
                except Exception as e:
                                self.logger.error(f"Error fetching weather data: {e}")
                                return None

            def _analyze_symbol_impact(self, symbol: str, weather_data: Dict) -> Dict[str, Any]:
                        """Analyze specific symbol impact from weather patterns"""""
                        # Simplified impact calculation
                        confidence = min(0.8, max(-0.8, weather_data.get('temperature', 0) / 100))

                        return {
                                        'symbol': symbol,
                                        'pattern': 'Temperature variation',
                                        'confidence': confidence,
                                        'price_impact': confidence * 2.5,
                                        'timestamp': str(__import__('datetime').datetime.now())
                        }
                ''',
                    
                        '''agents/news_analysis_agent.py': '''"""
                        News Analysis Agent
                        
                        Analyzes financial news sentiment and market impact.
                        Detects trading opportunities from news events.
                        """""

import re
from typing import List, Dict, Any
from base_agent import BaseAgent
from config import Config


class NewsAnalysisAgent(BaseAgent):
        """
            News Analysis Agent
                
                    Processes financial news sources and identifies market-moving events.
                        """""

        def __init__(self):
                    super().__init__()
                    self.news_sources = ["reuters", "bloomberg", "cnbc", "ft"]
                    self.sentiment_threshold = Config.get("news_sentiment_threshold", 0.6)
                    self.tracked_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

                def analyze(self) -> List[Dict[str, Any]]:
                            """
                                    Analyze news sentiment and market impact.
                                            """""
                            findings = []

        try:
                        # Fetch news articles
                        articles = self._fetch_news_articles()

                        if not articles:
                                            return findings

                        # Analyze sentiment for each article
                        for article in articles:
                                            sentiment_score = self._analyze_sentiment(article['text'])

                            if abs(sentiment_score) >= self.sentiment_threshold:
                                                    findings.append({
                                                                                'type': 'News Sentiment Signal',
                                                                                'source': article['source'],
                                                                                'headline': article.get('headline', 'N/A'),
                                                                                'sentiment': 'Positive' if sentiment_score > 0 else 'Negative',
                                                                                'confidence': abs(sentiment_score),
                                                                                'impact_tickers': self._extract_tickers(article['text']),
                                                                                'timestamp': article.get('timestamp', '')
                                                    })
except Exception as e:
            self.logger.error(f"Error analyzing news: {e}")

        return findings

    def _fetch_news_articles(self) -> List[Dict[str, Any]]:
                """Fetch news articles from sources"""""
        # Placeholder for actual news API calls
        return []

    def _analyze_sentiment(self, text: str) -> float:
                """Simple sentiment analysis (placeholder)"""""
        positive_words = ['gain', 'surge', 'rally', 'bull', 'profit', 'growth']
        negative_words = ['loss', 'crash', 'bear', 'decline', 'fall', 'slump']

        score = 0
        for word in positive_words:
                        score += len(re.findall(r'\b' + word + r'\b', text.lower(), re.IGNORECASE))
        for word in negative_words:
                    score -= len(re.findall(r'\b' + word + r'\b', text.lower(), re.IGNORECASE))

        return min(1.0, max(-1.0, score / 10))

    def _extract_tickers(self, text: str) -> List[str]:
                """Extract stock tickers from text"""""
                tickers = []
                for ticker in self.tracked_tickers:
                                if ticker.upper() in text.upper():
                                                    tickers.append(ticker)
                                                            return list(set(tickers))
                                    ''',
                                        
                                            '''agents/commodity_trend_agent.py': '''"""
                                            Commodity Trend Agent
                                            
                                            Analyzes commodity market trends and identifies trading opportunities.
                                            Tracks energy, metals, and agricultural commodity patterns.
                                            """""

from typing import List, Dict, Any
from base_agent import BaseAgent
from config import Config
import statistics


class CommodityTrendAgent(BaseAgent):
        """
            Commodity Trend Agent
                
                    Monitors commodity prices for trend changes and patterns.
                        Identifies momentum shifts in oil, metals, and agricultural markets.
                            """""

    def __init__(self):
                super().__init__()
        self.commodities = {
                        'oil': 'WTI',
                        'gold': 'GC',
                        'copper': 'HG',
                        'natural_gas': 'NG',
                        'corn': 'ZC',
                        'wheat': 'ZW'
                    }
                            self.trend_window = Config.get("trend_analysis_window", 20)
        self.trend_threshold = Config.get("trend_threshold", 0.02)

    def analyze(self) -> List[Dict[str, Any]]:
                """
                        Analyze commodity trends and identify opportunities.
                                """""
        findings = []

        try:
                        for commodity_name, ticker in self.commodities.items():
                                            trend_analysis = self._analyze_trend(commodity_name, ticker)

                if trend_analysis and abs(trend_analysis['trend_strength']) >= self.trend_threshold:
                                        findings.append({
                                                                    'type': 'Commodity Trend Signal',
                                                                    'commodity': commodity_name,
                                                                    'ticker': ticker,
                                                                    'trend': 'Uptrend' if trend_analysis['trend_strength'] > 0 else 'Downtrend',
                                                                    'strength': abs(trend_analysis['trend_strength']),
                                                                    'momentum': trend_analysis['momentum'],
                                                                    'support_level': trend_analysis.get('support', 0),
                                                                    'resistance_level': trend_analysis.get('resistance', 0),
                                                                    'timestamp': trend_analysis['timestamp']
                                        })
except Exception as e:
            self.logger.error(f"Error analyzing commodit")
                                        })
        }
                                                    })
                        }
                        })
}