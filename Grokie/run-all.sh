#!/bin/bash

# Grokie Web Client - Complete Startup Script
# This script starts all required services:
# 1. LiveKit server
# 2. Python GROK agent
# 3. Node.js token server
# 4. Frontend dev server

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"

# PID files for cleanup
LIVEKIT_PID_FILE="$LOGS_DIR/livekit.pid"
AGENT_PID_FILE="$LOGS_DIR/agent.pid"
TOKEN_SERVER_PID_FILE="$LOGS_DIR/token-server.pid"
FRONTEND_PID_FILE="$LOGS_DIR/frontend.pid"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    if [ -f "$LIVEKIT_PID_FILE" ]; then
        kill $(cat "$LIVEKIT_PID_FILE") 2>/dev/null || true
        rm "$LIVEKIT_PID_FILE"
        echo -e "${GREEN}✓ LiveKit server stopped${NC}"
    fi
    
    if [ -f "$AGENT_PID_FILE" ]; then
        kill $(cat "$AGENT_PID_FILE") 2>/dev/null || true
        rm "$AGENT_PID_FILE"
        echo -e "${GREEN}✓ Python agent stopped${NC}"
    fi
    
    if [ -f "$TOKEN_SERVER_PID_FILE" ]; then
        kill $(cat "$TOKEN_SERVER_PID_FILE") 2>/dev/null || true
        rm "$TOKEN_SERVER_PID_FILE"
        echo -e "${GREEN}✓ Token server stopped${NC}"
    fi
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        kill $(cat "$FRONTEND_PID_FILE") 2>/dev/null || true
        rm "$FRONTEND_PID_FILE"
        echo -e "${GREEN}✓ Frontend server stopped${NC}"
    fi
    
    # Kill any remaining processes
    pkill -f "livekit-server" 2>/dev/null || true
    pkill -f "grok_voice_agent.py" 2>/dev/null || true
    pkill -f "node.*server.js" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

# Set up trap to call cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Grokie Web Client Startup Script${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check for required commands
echo -e "${YELLOW}Checking dependencies...${NC}"

command -v livekit-server >/dev/null 2>&1 || {
    echo -e "${RED}✗ livekit-server not found. Please install it first.${NC}"
    echo -e "${YELLOW}  Install: https://docs.livekit.io/home/self-hosting/deployment/${NC}"
    exit 1
}

command -v python3 >/dev/null 2>&1 || {
    echo -e "${RED}✗ python3 not found${NC}"
    exit 1
}

command -v node >/dev/null 2>&1 || {
    echo -e "${RED}✗ node not found. Please install Node.js.${NC}"
    exit 1
}

command -v npm >/dev/null 2>&1 || {
    echo -e "${RED}✗ npm not found${NC}"
    exit 1
}

echo -e "${GREEN}✓ All dependencies found${NC}\n"

# Check for .env file
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠ Warning: .env file not found${NC}"
    echo -e "${YELLOW}  Using default LiveKit credentials (devkey/secret)${NC}\n"
fi

# Check if Python virtual environment exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    echo -e "${GREEN}✓ Using virtual environment${NC}"
else
    PYTHON_CMD="python3"
    echo -e "${YELLOW}⚠ No virtual environment found, using system Python${NC}"
fi

# Check if web-client dependencies are installed
if [ ! -d "$SCRIPT_DIR/web-client/node_modules" ]; then
    echo -e "${YELLOW}Installing web-client dependencies...${NC}"
    cd "$SCRIPT_DIR/web-client"
    npm install
    cd "$SCRIPT_DIR"
fi

echo ""

# 1. Start LiveKit Server
echo -e "${BLUE}[1/4] Starting LiveKit server...${NC}"
livekit-server --dev > "$LOGS_DIR/livekit.log" 2>&1 &
LIVEKIT_PID=$!
echo $LIVEKIT_PID > "$LIVEKIT_PID_FILE"
sleep 2

if ps -p $LIVEKIT_PID > /dev/null; then
    echo -e "${GREEN}✓ LiveKit server started (PID: $LIVEKIT_PID)${NC}"
    echo -e "  Logs: $LOGS_DIR/livekit.log"
else
    echo -e "${RED}✗ Failed to start LiveKit server${NC}"
    cat "$LOGS_DIR/livekit.log"
    exit 1
fi

# 2. Start Python Agent
echo -e "\n${BLUE}[2/4] Starting Python GROK agent...${NC}"
cd "$SCRIPT_DIR"
$PYTHON_CMD grok_voice_agent.py > "$LOGS_DIR/agent.log" 2>&1 &
AGENT_PID=$!
echo $AGENT_PID > "$AGENT_PID_FILE"
sleep 3

if ps -p $AGENT_PID > /dev/null; then
    echo -e "${GREEN}✓ Python agent started (PID: $AGENT_PID)${NC}"
    echo -e "  Logs: $LOGS_DIR/agent.log"
else
    echo -e "${RED}✗ Failed to start Python agent${NC}"
    cat "$LOGS_DIR/agent.log"
    exit 1
fi

# 3. Start Token Server
echo -e "\n${BLUE}[3/4] Starting token server...${NC}"
cd "$SCRIPT_DIR/web-client"
npm run server > "$LOGS_DIR/token-server.log" 2>&1 &
TOKEN_SERVER_PID=$!
echo $TOKEN_SERVER_PID > "$TOKEN_SERVER_PID_FILE"
sleep 2

if ps -p $TOKEN_SERVER_PID > /dev/null; then
    echo -e "${GREEN}✓ Token server started (PID: $TOKEN_SERVER_PID)${NC}"
    echo -e "  Logs: $LOGS_DIR/token-server.log"
    echo -e "  URL: http://localhost:8080"
else
    echo -e "${RED}✗ Failed to start token server${NC}"
    cat "$LOGS_DIR/token-server.log"
    exit 1
fi

# 4. Start Frontend Dev Server
echo -e "\n${BLUE}[4/4] Starting frontend dev server...${NC}"
cd "$SCRIPT_DIR/web-client"
npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$FRONTEND_PID_FILE"
sleep 3

if ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${GREEN}✓ Frontend server started (PID: $FRONTEND_PID)${NC}"
    echo -e "  Logs: $LOGS_DIR/frontend.log"
else
    echo -e "${RED}✗ Failed to start frontend server${NC}"
    cat "$LOGS_DIR/frontend.log"
    exit 1
fi

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  All services started successfully!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo -e "${BLUE}Services:${NC}"
echo -e "  • LiveKit Server:    ws://localhost:7880"
echo -e "  • Token Server:      http://localhost:8080"
echo -e "  • Frontend:          http://localhost:3000"
echo -e "  • Python Agent:      Running and ready\n"

echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Open http://localhost:3000 in your browser"
echo -e "  2. Enter a room name (default: test-room)"
echo -e "  3. Enter your name"
echo -e "  4. Click 'Connect to Agent'"
echo -e "  5. Allow microphone access"
echo -e "  6. Start speaking!\n"

echo -e "${YELLOW}Logs are available in: $LOGS_DIR${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}\n"

# Wait for all background processes
wait
