"""
Main application entry point for the Market Inefficiency Detection Platform.
This file is imported by gunicorn to run the Flask application.
"""

import os
import logging
from app import app

# Configure logging for production
if os.environ.get('DEPLOYMENT_ENV') == 'production':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

# Ensure app is available for gunicorn
if not app:
    raise RuntimeError("Failed to create Flask application")

if __name__ == '__main__':
    # Only run this when executed directly (not through gunicorn)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)