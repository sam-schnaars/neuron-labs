#!/bin/bash
# Install LiveKit Server binary for Raspberry Pi

set -e

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "🎤 Installing LiveKit Server for Raspberry Pi"
echo "=============================================="
echo ""

# Check if already installed
if command_exists livekit-server; then
    echo "✅ LiveKit Server is already installed: $(livekit-server --version 2>/dev/null || echo 'version unknown')"
    exit 0
fi

# Detect architecture
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

# Map architecture to LiveKit binary name
case "$ARCH" in
    "aarch64"|"arm64")
        BINARY_NAME="livekit-server_linux_arm64"
        echo "✅ Using ARM64 binary"
        ;;
    "armv7l"|"armv6l"|"armhf")
        BINARY_NAME="livekit-server_linux_arm"
        echo "✅ Using ARM binary"
        ;;
    "x86_64")
        BINARY_NAME="livekit-server_linux_amd64"
        echo "✅ Using AMD64 binary"
        ;;
    *)
        echo "❌ Unsupported architecture: $ARCH"
        echo "   Please download manually from: https://github.com/livekit/livekit/releases"
        exit 1
        ;;
esac

# Get latest release URL
echo ""
echo "📦 Downloading LiveKit Server..."
LATEST_RELEASE=$(curl -s https://api.github.com/repos/livekit/livekit/releases/latest | grep "tag_name" | cut -d '"' -f 4)
if [ -z "$LATEST_RELEASE" ]; then
    echo "⚠️  Could not determine latest release, using 'latest' tag"
    DOWNLOAD_URL="https://github.com/livekit/livekit/releases/latest/download/${BINARY_NAME}"
else
    DOWNLOAD_URL="https://github.com/livekit/livekit/releases/download/${LATEST_RELEASE}/${BINARY_NAME}"
fi

echo "Download URL: $DOWNLOAD_URL"

# Download to temp directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

if wget -q "$DOWNLOAD_URL" -O "$BINARY_NAME"; then
    echo "✅ Download successful"
else
    echo "❌ Download failed"
    echo "   Please download manually from: https://github.com/livekit/livekit/releases"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Make executable
chmod +x "$BINARY_NAME"

# Move to /usr/local/bin
echo ""
echo "📦 Installing to /usr/local/bin..."
sudo mv "$BINARY_NAME" /usr/local/bin/livekit-server

# Cleanup
rm -rf "$TEMP_DIR"

# Verify installation
if command_exists livekit-server; then
    echo ""
    echo "✅ LiveKit Server installed successfully!"
    echo ""
    echo "Version: $(livekit-server --version 2>/dev/null || echo 'unknown')"
    echo ""
    echo "To start the server, run:"
    echo "  livekit-server --dev"
    echo ""
else
    echo "⚠️  Installation completed but 'livekit-server' command not found in PATH"
    echo "   Try: source ~/.bashrc or restart your terminal"
fi

