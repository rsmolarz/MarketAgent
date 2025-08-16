#!/bin/bash
# Simple script to run the application standalone using main.py
# This is useful for development and testing when the workflow is already running

echo "🚀 Starting Market Inefficiency Platform (Standalone Mode)"
echo "This will automatically find an available port if 5000 is in use."
echo ""
echo "The main workflow is running on port 5000"
echo "Standalone mode will use the next available port (5001, 5002, etc.)"
echo ""

python main.py