import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def create_app():
    # Create the app
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Configure the database
    database_url = os.environ.get("DATABASE_URL", "sqlite:///market_inefficiency.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize the app with the extension
    db.init_app(app)
    
    with app.app_context():
        try:
            # Import models to ensure tables are created
            import models
            db.create_all()
            app.logger.info("Database tables created successfully")
        except Exception as e:
            app.logger.error(f"Database initialization failed: {e}")
            # Continue without database for basic health checks
        
        # Register blueprints
        try:
            from routes.dashboard import dashboard_bp
            from routes.api import api_bp
            
            app.register_blueprint(dashboard_bp)
            app.register_blueprint(api_bp, url_prefix='/api')
            app.logger.info("Blueprints registered successfully")
        except Exception as e:
            app.logger.error(f"Blueprint registration failed: {e}")
        
        # Initialize scheduler
        try:
            from scheduler import AgentScheduler
            scheduler = AgentScheduler(app)
            # Store scheduler as an application extension instead of direct attribute
            app.extensions['scheduler'] = scheduler
            app.logger.info("Scheduler initialized successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize scheduler: {e}")
            # Continue without scheduler for basic health checks
    
    # Add fallback health check route directly to app (in case blueprint fails)
    @app.route('/healthz')
    def fallback_health():
        """Fallback health check endpoint"""
        return 'OK', 200
    
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
