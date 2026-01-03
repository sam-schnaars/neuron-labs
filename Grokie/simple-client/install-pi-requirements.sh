#!/bin/bash
# Install requirements for Raspberry Pi with proper PyTorch installation

set -e

echo "🐍 Installing Python requirements for Raspberry Pi"
echo "=================================================="
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

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "🐍 Python version: $PYTHON_VERSION"
echo ""

# Install PyTorch first (CPU-only version for Pi, from official index)
echo "🔥 Installing PyTorch (this may take 10-20 minutes on Pi)..."
echo "   Using CPU-only version optimized for Raspberry Pi"
echo ""

# Install PyTorch from official index with increased timeout
pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    --timeout 300 \
    --retries 5 \
    torch torchaudio || {
    echo ""
    echo "⚠️  PyTorch installation failed. Trying alternative method..."
    echo "   Installing from PyPI with CPU-only..."
    pip install --no-cache-dir --timeout 300 --retries 5 torch torchaudio --index-url https://download.pytorch.org/whl/cpu
}

echo ""
echo "✅ PyTorch installed successfully!"
echo ""

# Install other requirements (excluding torch and torchaudio which we already installed)
echo "📦 Installing other requirements..."
pip install --no-cache-dir --timeout 300 --retries 5 \
    pyaudio \
    numpy \
    silero-vad \
    pyttsx3 \
    openai-whisper \
    requests \
    python-dotenv

echo ""
echo "✅ All requirements installed successfully!"
echo ""
echo "💡 Note: If downloads are slow, you can:"
echo "   1. Wait patiently (Pi downloads are often slow)"
echo "   2. Use a faster internet connection"
echo "   3. Install packages one at a time to see progress"
echo ""

