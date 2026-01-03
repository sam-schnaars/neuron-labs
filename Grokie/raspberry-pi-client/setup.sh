#!/bin/bash
# Setup script for Raspberry Pi GROK Voice Client

set -e

echo "🎤 GROK Voice Agent - Raspberry Pi Setup"
echo "========================================"
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt install -y \
    python3-pip \
    python3-venv \
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils \
    git

# Check and fix /tmp space issue (common on Raspberry Pi)
echo "🔍 Checking /tmp space..."
TMP_SPACE=$(df /tmp 2>/dev/null | tail -1 | awk '{print $4}' || echo "0")
TMP_SPACE_MB=$((TMP_SPACE / 1024))

if [ $TMP_SPACE_MB -lt 100 ]; then
    echo "⚠️  /tmp is low on space (${TMP_SPACE_MB} MB available)"
    echo "🧹 Cleaning old files from /tmp..."
    sudo find /tmp -type f -atime +7 -delete 2>/dev/null || true
    
    # Use home directory for temp files during pip install
    echo "📁 Using home directory for temporary files..."
    export TMPDIR="$HOME/tmp"
    mkdir -p "$TMPDIR"
else
    echo "✅ /tmp has sufficient space (${TMP_SPACE_MB} MB available)"
fi

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv

# Activate and install Python packages
echo "📦 Installing Python packages..."
source venv/bin/activate

# Clear pip cache if it's large
if [ -d ~/.cache/pip ]; then
    CACHE_SIZE=$(du -sm ~/.cache/pip 2>/dev/null | cut -f1 || echo "0")
    if [ $CACHE_SIZE -gt 500 ]; then
        echo "🧹 Clearing large pip cache (${CACHE_SIZE} MB)..."
        pip cache purge || true
    fi
fi

pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo ""
    echo "⚠️  Please edit .env file with your LiveKit server settings:"
    echo "   nano .env"
    echo ""
fi

# Test audio
echo ""
echo "🔊 Testing audio devices..."
echo "Recording devices:"
arecord -l 2>/dev/null || echo "   No recording devices found"
echo ""
echo "Playback devices:"
aplay -l 2>/dev/null || echo "   No playback devices found"
echo ""

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your LiveKit server settings"
echo "2. Run: source venv/bin/activate && python grok_pi_client.py"
echo ""


