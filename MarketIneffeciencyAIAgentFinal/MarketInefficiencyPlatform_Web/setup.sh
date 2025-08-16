#!/usr/bin/env bash
set -e
pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
fi
echo "Setup complete. Edit .env with your API keys."
