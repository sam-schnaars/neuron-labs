#!/bin/bash
# Installation script for GROK Voice Agent on Raspberry Pi
# Similar to whisplay-ai-chatbot's install_dependencies.sh

set -e

echo "🎤 GROK Voice Agent - Dependency Installation"
echo "================================================"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-venv \
    portaudio19-dev \
    python3-pyaudio \
    alsa-utils \
    git \
    build-essential

# Check if running on Raspberry Pi (for RPi.GPIO)
if [ -f /proc/device-tree/model ] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "✅ Raspberry Pi detected - RPi.GPIO will be installed"
    IS_RASPBERRY_PI=true
else
    echo "⚠️  Not running on Raspberry Pi - RPi.GPIO will be skipped"
    IS_RASPBERRY_PI=false
fi

# Install Node.js and npm (needed for LiveKit CLI)
# Use NVM approach similar to whisplay project
echo ""
echo "📦 Checking Node.js installation..."

# Source bashrc to load nvm if it exists
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

NVM_VERSION="0.39.3"
NVM_URL="https://cdn.pisugar.com/PiSugar-wificonfig/script/nvm/v$NVM_VERSION.tar.gz"

# Function to install nvm and Node.js
install_node_nvm() {
    echo "Installing Node.js 20 using nvm..."
    
    # Install nvm if it's not already installed
    if [ ! -d "$HOME/.nvm" ]; then
        echo "Installing nvm..."
        TEMP_DIR=$(mktemp -d)
        curl -o $TEMP_DIR/nvm-$NVM_VERSION.tar.gz -L $NVM_URL
        tar -xzf $TEMP_DIR/nvm-$NVM_VERSION.tar.gz -C $TEMP_DIR
        mv $TEMP_DIR/nvm-$NVM_VERSION $HOME/.nvm
        rm -rf $TEMP_DIR

        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

        # check if nvm is in the bash profile
        if ! grep -q "nvm" $HOME/.bashrc; then
            echo "export NVM_DIR=\"$HOME/.nvm\"" >> $HOME/.bashrc
            echo "[ -s \"\$NVM_DIR/nvm.sh\" ] && \. \"\$NVM_DIR/nvm.sh\"" >> $HOME/.bashrc
            echo "[ -s \"\$NVM_DIR/bash_completion\" ] && \. \"\$NVM_DIR/bash_completion\"" >> $HOME/.bashrc
        fi
    else
        echo "✅ nvm is already installed."
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
    fi

    # Install and use Node.js 20
    echo "Installing/using Node.js 20..."
    nvm install 20
    nvm use 20
    nvm alias default 20

    # Verify installation
    if command_exists node && [[ "$(node -v)" =~ ^v20 ]]; then
        echo "✅ Node.js 20 installed successfully: $(node -v)"
    else
        echo "❌ Failed to install Node.js 20."
        exit 1
    fi
}

# Check if Node.js is installed and is version 20
if command_exists node; then
    NODE_VERSION=$(node -v)
    if [[ "$NODE_VERSION" =~ ^v20 ]]; then
        echo "✅ Node.js 20 is already installed: $NODE_VERSION"
    else
        echo "Different version of Node.js detected: $NODE_VERSION"
        install_node_nvm
    fi
else
    echo "Node.js is not installed."
    install_node_nvm
fi

# Verify npm is available
if ! command_exists npm; then
    echo "❌ npm is not available. This should not happen if Node.js is installed via nvm."
    echo "   Try running: source ~/.bashrc"
    exit 1
else
    echo "✅ npm is available: $(npm -v)"
fi

# Install LiveKit CLI globally
echo ""
echo "📦 Installing LiveKit CLI..."
if command_exists livekit-server; then
    echo "✅ LiveKit CLI is already installed"
else
    echo "Installing livekit-cli..."
    # Use npm from nvm (no sudo needed for user installs with nvm)
    npm install -g livekit-cli
    
    if command_exists livekit-server; then
        echo "✅ LiveKit CLI installed successfully"
    else
        echo "⚠️  Warning: LiveKit CLI installation may have failed"
        echo "   The command may not be in PATH. Try:"
        echo "   1. source ~/.bashrc"
        echo "   2. Or run: npm install -g livekit-cli"
        echo "   3. Then check: ~/.nvm/versions/node/v20.*/bin/livekit-server"
    fi
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."

# Check if virtual environment should be used
USE_VENV=false
if [ -d "venv" ]; then
    echo "✅ Virtual environment found, will use it"
    USE_VENV=true
else
    read -p "Create a virtual environment? (recommended) [Y/n]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        USE_VENV=true
    else
        echo "⚠️  Using system Python (may require --break-system-packages flag)"
    fi
fi

# Activate virtual environment if using it
if [ "$USE_VENV" = true ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
    PIP_CMD="pip"
else
    PIP_CMD="pip3 --break-system-packages"
fi

# Upgrade pip
echo "Upgrading pip..."
$PIP_CMD install --upgrade pip

# Install main requirements
echo "Installing main Python requirements..."
if [ "$USE_VENV" = true ]; then
    pip install -r requirements.txt
else
    pip install -r requirements.txt --break-system-packages
fi

# Install Raspberry Pi client requirements
echo "Installing Raspberry Pi client requirements..."
if [ "$USE_VENV" = true ]; then
    pip install -r raspberry-pi-client/requirements.txt
else
    pip install -r raspberry-pi-client/requirements.txt --break-system-packages
fi

# Install RPi.GPIO if on Raspberry Pi
if [ "$IS_RASPBERRY_PI" = true ]; then
    echo "Installing RPi.GPIO..."
    if [ "$USE_VENV" = true ]; then
        pip install RPi.GPIO || echo "⚠️  Warning: Failed to install RPi.GPIO"
    else
        pip install RPi.GPIO --break-system-packages || echo "⚠️  Warning: Failed to install RPi.GPIO"
    fi
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Create a .env file with your configuration:"
echo "   cp .env.example .env  # if .env.example exists"
echo "   nano .env"
echo ""
echo "   Required variables:"
echo "   - XAI_API_KEY=your_key_here"
echo "   - SERVE_GROK_AGENT=true  # optional, to auto-start server"
echo ""
echo "2. Start LiveKit server (in a separate terminal or as a service):"
echo "   livekit-server --dev"
echo ""
echo "3. Run the button toggle script:"
echo "   ./run_grokie.sh"
echo ""
if [ "$USE_VENV" = true ]; then
    echo "Note: Remember to activate the virtual environment:"
    echo "   source venv/bin/activate"
    echo ""
fi

