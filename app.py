
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