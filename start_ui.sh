#!/bin/bash
# Start the Table OCR Streamlit UI

# Change to the directory containing this script
cd "$(dirname "$0")"

# Check if virtual environment exists and activate it if not already active
if [ -d ".venv" ]; then
    if [ -z "$VIRTUAL_ENV" ]; then
        echo "Activating virtual environment..."
        source .venv/bin/activate
    else
        echo "Virtual environment already active"
    fi
else
    echo "Warning: .venv directory not found. Please create a virtual environment first."
    echo "Run: uv venv && source .venv/bin/activate && uv pip install -r requirements.txt"
    exit 1
fi

# Check if GEMINI_API_KEY is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Warning: GEMINI_API_KEY environment variable is not set"
    echo "Please set it with: export GEMINI_API_KEY='your-api-key'"
    exit 1
fi

# Run Streamlit from ui directory so pages/ paths work correctly
cd ui
streamlit run app.py
