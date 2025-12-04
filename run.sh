#!/bin/bash

# DramaFlow Backend Startup Script

echo "=========================================="
echo "  DramaFlow Backend Server"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from template..."
    if [ -f "env.template" ]; then
        cp env.template .env
        echo "✅ Created .env file. Please edit it and add your API keys."
        echo ""
        echo "Required API keys:"
        echo "  - OPENROUTER_API_KEY"
        echo "  - ELEVENLABS_API_KEY"
        echo ""
        exit 1
    else
        echo "❌ env.template not found!"
        exit 1
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "❌ Dependencies not installed!"
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the server
echo ""
echo "Starting DramaFlow server..."
echo "API will be available at: http://localhost:8000"
echo "API docs available at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

# Use uvicorn (the correct way for FastAPI)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

