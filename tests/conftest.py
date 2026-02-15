"""
Shared test configuration and fixtures.

Sets environment variables needed for test imports before any app code loads.
"""

import os

# Set required environment variables for testing
os.environ.setdefault("REPL_ID", "test-repl-id")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
