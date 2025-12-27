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

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv

# Activate and install Python packages
echo "📦 Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

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


