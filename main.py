"""
Main application entry point for the Market Inefficiency Detection Platform.
This file is imported by gunicorn to run the Flask application.
"""

import os
import logging
from app import create_app

# Create Flask application instance
app = create_app()

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
    import socket
    
    def find_free_port(start_port=5000):
        """Find a free port starting from start_port"""
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        raise RuntimeError("No free ports available")
    
    # Try to use the specified port, fallback to free port if occupied
    desired_port = int(os.environ.get('PORT', 5000))
    try:
        # Test if the desired port is available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', desired_port))
        port = desired_port
    except OSError:
        # Port is occupied, find a free one
        port = find_free_port(desired_port + 1)
        print(f"Port {desired_port} is in use. Using port {port} instead.")
    
    # Disable debug mode for production deployments
    debug_mode = os.environ.get('DEPLOYMENT_ENV') != 'production'
    print(f"Starting Market Inefficiency Detection Platform on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)