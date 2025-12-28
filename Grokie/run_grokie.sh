#!/bin/bash
# Set working directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Output current environment information (for debugging)
echo "===== Start time: $(date) =====" 
echo "Current user: $(whoami)" 
echo "Working directory: $(pwd)" 
echo "PATH: $PATH" 
echo "Python version: $(python3 --version)"

# Check if virtual environment exists and activate it
use_venv=false
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
    use_venv=true
    echo "Virtual environment activated."
else
    echo "No virtual environment found, using system Python."
    echo "Note: If you encounter package conflicts, consider creating a venv:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo "  pip install -r raspberry-pi-client/requirements.txt"
    echo "  pip install RPi.GPIO"
fi

# Check if .env file exists
serve_grok_agent=false
if [ -f ".env" ]; then
    echo ".env file found."
    # Load SERVE_GROK_AGENT from .env if it exists (similar to SERVE_OLLAMA in run_chatbot.sh)
    if grep -Eq '^[[:space:]]*SERVE_GROK_AGENT[[:space:]]*=' .env; then
        val=$(grep -E '^[[:space:]]*SERVE_GROK_AGENT[[:space:]]*=' .env | tail -n1 | cut -d'=' -f2-)
        # trim whitespace and surrounding quotes
        SERVE_GROK_AGENT=$(echo "$val" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        export SERVE_GROK_AGENT
        # check if SERVE_GROK_AGENT is set to true
        if [ "$SERVE_GROK_AGENT" = "true" ]; then
            serve_grok_agent=true
        fi
    fi
    echo ".env variables loaded."
else
    echo "⚠️  Warning: .env file not found."
    echo "   Please create a .env file with your configuration."
    echo "   Required variables:"
    echo "   - XAI_API_KEY"
    echo "   - LIVEKIT_URL (optional, defaults to ws://localhost:7880)"
    echo "   - LIVEKIT_API_KEY (optional, defaults to devkey)"
    echo "   - LIVEKIT_API_SECRET (optional, defaults to secret)"
    echo "   - SERVE_GROK_AGENT (optional, set to 'true' to auto-start server)"
    echo ""
    echo "   Continuing anyway..."
fi

# Check if RPi.GPIO is available (for Raspberry Pi)
if ! python3 -c "import RPi.GPIO" 2>/dev/null; then
    echo "❌ Error: RPi.GPIO is not installed."
    echo "   This script requires RPi.GPIO to monitor button presses."
    if [ "$use_venv" = true ]; then
        echo "   Install it with: pip install RPi.GPIO"
    else
        echo "   Install it with: pip install RPi.GPIO --break-system-packages"
    fi
    exit 1
fi

# Check if the client script exists
if [ ! -f "raspberry-pi-client/grok_pi_client.py" ]; then
    echo "❌ Error: grok_pi_client.py not found at raspberry-pi-client/grok_pi_client.py"
    exit 1
fi

# Check if required Python packages are installed
echo "Checking Python dependencies..."
missing_packages=()
if ! python3 -c "import livekit" 2>/dev/null; then
    missing_packages+=("livekit")
fi
if ! python3 -c "import dotenv" 2>/dev/null; then
    missing_packages+=("python-dotenv")
fi

if [ ${#missing_packages[@]} -gt 0 ]; then
    echo "⚠️  Warning: Some required packages are missing: ${missing_packages[*]}"
    if [ "$use_venv" = true ]; then
        echo "   Install with: pip install -r raspberry-pi-client/requirements.txt"
    else
        echo "   Install with: pip install -r raspberry-pi-client/requirements.txt --break-system-packages"
    fi
    echo "   Continuing anyway..."
fi

# Start GROK agent server if configured
if [ "$serve_grok_agent" = true ]; then
    echo "Starting GROK agent server..."
    if [ "$use_venv" = true ]; then
        python3 grok_voice_agent.py &
    else
        python3 grok_voice_agent.py &
    fi
    GROK_AGENT_PID=$!
    echo "GROK agent server started (PID: $GROK_AGENT_PID)"
    sleep 3  # Give server time to start
else
    echo ""
    echo "⚠️  Note: SERVE_GROK_AGENT is not set to 'true' in .env"
    echo "   Make sure the GROK voice agent server is running separately!"
    echo "   Start it in another terminal with:"
    echo "     python3 grok_voice_agent.py"
    echo ""
fi

echo ""
echo "=========================================="
echo "Starting GROK Button Toggle Monitor"
echo "=========================================="
echo ""
echo "Press the button to toggle GROK connection on/off"
echo "Press Ctrl+C to exit"
echo ""
sleep 2

# Start the button toggle script
python3 grokie_button_toggle.py

# After the service ends, perform cleanup
echo ""
echo "Cleaning up after service..."

if [ "$serve_grok_agent" = true ] && [ -n "$GROK_AGENT_PID" ]; then
    echo "Stopping GROK agent server (PID: $GROK_AGENT_PID)..."
    kill $GROK_AGENT_PID 2>/dev/null || true
    wait $GROK_AGENT_PID 2>/dev/null || true
fi

echo "===== Service ended: $(date) ====="

# Deactivate virtual environment if it was activated
if [ "$use_venv" = true ]; then
    deactivate
fi

