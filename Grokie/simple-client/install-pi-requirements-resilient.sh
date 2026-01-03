#!/bin/bash
# Resilient installation script for Raspberry Pi that handles network issues

set -e

echo "🐍 Resilient Python Requirements Installation for Raspberry Pi"
echo "=============================================================="
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

# Set temp directory to avoid /tmp space issues
export TMPDIR="$HOME/tmp"
mkdir -p "$TMPDIR"
echo "📁 Using temp directory: $TMPDIR"
echo ""

# Function to check WiFi connection
check_wifi() {
    if command -v iwgetid &> /dev/null; then
        if iwgetid -r &> /dev/null; then
            return 0
        fi
    fi
    return 1
}

# Function to install package with retries
install_with_retries() {
    local package=$1
    local max_retries=3
    local retry=0
    
    while [ $retry -lt $max_retries ]; do
        echo "📦 Installing $package (attempt $((retry + 1))/$max_retries)..."
        
        if pip install --no-cache-dir --timeout 600 --retries 3 "$package"; then
            echo "✅ Successfully installed $package"
            return 0
        else
            retry=$((retry + 1))
            if [ $retry -lt $max_retries ]; then
                echo "⚠️  Installation failed. Checking WiFi connection..."
                if ! check_wifi; then
                    echo "❌ WiFi disconnected! Please reconnect and run this script again."
                    echo "   The script will resume from where it left off."
                    exit 1
                fi
                echo "🔄 Retrying in 5 seconds..."
                sleep 5
            fi
        fi
    done
    
    echo "❌ Failed to install $package after $max_retries attempts"
    return 1
}

# Check WiFi connection before starting
echo "📡 Checking WiFi connection..."
if ! check_wifi; then
    echo "❌ Not connected to WiFi!"
    echo ""
    echo "Please connect to WiFi first:"
    echo "   sudo raspi-config  # Network Options > Wi-fi"
    echo "   or"
    echo "   sudo nmtui"
    echo ""
    exit 1
fi

SSID=$(iwgetid -r 2>/dev/null || echo "unknown")
echo "✅ Connected to: $SSID"
echo ""

# Install packages one at a time to avoid overwhelming the connection
echo "📦 Installing packages one at a time (more stable)..."
echo ""

# Install small packages first
echo "🔹 Installing small packages..."
for package in python-dotenv requests numpy; do
    install_with_retries "$package"
done

# Install pyaudio (medium size)
echo ""
echo "🔹 Installing pyaudio..."
install_with_retries "pyaudio"

# Install silero-vad and pyttsx3
echo ""
echo "🔹 Installing silero-vad..."
install_with_retries "silero-vad"

echo ""
echo "🔹 Installing pyttsx3..."
install_with_retries "pyttsx3"

# Install PyTorch (large, do this last and separately)
echo ""
echo "🔥 Installing PyTorch (this is the big one - may take 15-20 minutes)..."
echo "   ⚠️  Keep your Pi connected to power and WiFi!"
echo "   ⚠️  Don't disconnect during this step!"
echo ""

# Try CPU-only version from PyTorch's official index first (smaller)
echo "   Trying CPU-only version from PyTorch official index..."
if pip install --no-cache-dir --timeout 600 --retries 3 \
    --index-url https://download.pytorch.org/whl/cpu \
    torch torchaudio; then
    echo "✅ PyTorch installed successfully!"
else
    echo "⚠️  CPU-only install failed, trying standard PyPI..."
    install_with_retries "torch"
    install_with_retries "torchaudio"
fi

# Install openai-whisper last (depends on torch)
echo ""
echo "🔹 Installing openai-whisper (depends on PyTorch)..."
install_with_retries "openai-whisper"

echo ""
echo "✅ All requirements installed successfully!"
echo ""
echo "💡 Tips to prevent WiFi disconnections:"
echo "   1. Use ethernet cable if possible (more stable)"
echo "   2. Keep Pi close to WiFi router"
echo "   3. Ensure Pi has adequate power supply (2.5A+ recommended)"
echo "   4. Close other network-intensive applications"
echo ""

