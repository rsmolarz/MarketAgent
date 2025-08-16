"""
Main application entry point for the Market Inefficiency Detection Platform.
This file is imported by gunicorn to run the Flask application.
"""

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)