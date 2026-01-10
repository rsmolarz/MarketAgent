import os
import logging
from datetime import datetime

from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _apply_finding_council_migration(db):
    """Add LLM council columns to findings table if they don't exist."""
    from sqlalchemy import inspect, text
    
    try:
        inspector = inspect(db.engine)
        existing_columns = {col['name'] for col in inspector.get_columns('findings')}
        
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
                    db.session.execute(text(f"ALTER TABLE findings ADD COLUMN {col_name} {col_type}"))
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
    database_url = os.environ.get(
        "DATABASE_URL",
        "sqlite:///market_inefficiency.db"
    )

    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql://", 1
        )

    app.config.update(
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "pool_pre_ping": True,
            "pool_recycle": 300,
        },
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
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    # ------------------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------------------
    try:
        from scheduler import AgentScheduler
        scheduler = AgentScheduler(app)
        app.extensions["scheduler"] = scheduler
        logger.info("AgentScheduler initialized successfully")
    except Exception as e:
        logger.error(f"Scheduler failed to initialize: {e}")

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
    from replit_auth import make_replit_blueprint, init_auth
    
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
    app.register_blueprint(replit_bp, url_prefix='/auth')
    
    @app.route("/landing")
    def landing():
        return render_template("landing.html")

    @app.route("/status")
    def status():
        return jsonify({
            "service": "Market Inefficiency Detection Platform",
            "status": "running",
            "timestamp": datetime.utcnow().isoformat()
        })

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
