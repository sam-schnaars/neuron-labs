#!/bin/bash
# Raspberry Pi Client Startup Script for GROK Voice Agent
# Detects WM8960 sound card and starts the Node.js client

set -e

echo "🎤 GROK Voice Agent - Raspberry Pi Client Startup"
echo "=================================================="
echo ""

# Find the sound card index for wm8960soundcard
card_index=$(awk '/wm8960soundcard/ {print $1}' /proc/asound/cards | head -n1)

# Default to 1 if not found
if [ -z "$card_index" ]; then
  echo "⚠️  Warning: WM8960 sound card not found in /proc/asound/cards"
  echo "   Using default sound card index: 1"
  card_index=1
else
  echo "✅ Found WM8960 sound card at index: $card_index"
fi

# Set sound card index environment variable
export SOUND_CARD_INDEX=$card_index
echo "   Using SOUND_CARD_INDEX=$card_index"
echo ""

# Adjust volume (optional - adjust the value as needed)
echo "🔊 Setting speaker volume..."
amixer -c $card_index set Speaker 114 > /dev/null 2>&1 || echo "   (Volume adjustment skipped - may need manual setup)"
echo ""

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
  echo "📝 Loading environment variables from .env..."
  # Export variables from .env (simple parsing, handles basic KEY=VALUE format)
  set -a
  source .env
  set +a
  echo "   Environment variables loaded"
  echo ""
else
  echo "⚠️  Warning: .env file not found"
  echo "   Using default environment variables"
  echo ""
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
  echo "📦 Installing dependencies..."
  npm install
  echo ""
fi

# Build TypeScript if dist doesn't exist or src is newer
if [ ! -d "dist" ] || [ "src" -nt "dist" ]; then
  echo "🔨 Building TypeScript..."
  npm run build
  echo ""
fi

# Start the client
echo "🚀 Starting GROK Voice Agent client..."
echo ""
npm start

