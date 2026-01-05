#!/bin/bash
# Recovery script - checks what's installed and installs what's missing

echo "🔍 Checking installed packages..."
echo "=================================="
echo ""

# Set temp directory
export TMPDIR="$HOME/tmp"
mkdir -p "$TMPDIR"

# Check if in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d "venv" ]; then
        echo "📦 Activating virtual environment..."
        source venv/bin/activate
    else
        echo "⚠️  No virtual environment found. Install in current environment?"
        read -p "Continue? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# List of required packages
REQUIRED_PACKAGES=(
    "pyaudio"
    "numpy"
    "torch"
    "torchaudio"
    "silero-vad"
    "pyttsx3"
    "openai-whisper"
    "requests"
    "python-dotenv"
)

# Check WiFi connection
check_wifi() {
    if command -v iwgetid &> /dev/null; then
        if iwgetid -r &> /dev/null; then
            return 0
        fi
    fi
    return 1
}

echo "📡 Checking WiFi connection..."
if ! check_wifi; then
    echo "❌ Not connected to WiFi!"
    echo "   Please connect to WiFi first and run this script again."
    exit 1
fi

SSID=$(iwgetid -r 2>/dev/null || echo "unknown")
echo "✅ Connected to: $SSID"
echo ""

# Check what's installed
echo "📋 Checking installed packages..."
echo ""

MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if pip show "$package" &> /dev/null; then
        VERSION=$(pip show "$package" | grep Version | awk '{print $2}')
        echo "✅ $package ($VERSION)"
    else
        echo "❌ $package - NOT INSTALLED"
        MISSING_PACKAGES+=("$package")
    fi
done

echo ""

if [ ${#MISSING_PACKAGES[@]} -eq 0 ]; then
    echo "✅ All packages are already installed!"
    echo ""
    echo "You can now run: python simple-client.py"
    exit 0
fi

echo "📦 Missing packages: ${MISSING_PACKAGES[*]}"
echo ""
read -p "Install missing packages now? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi

echo ""
echo "📦 Installing missing packages..."
echo ""

# Install packages one at a time
for package in "${MISSING_PACKAGES[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Installing: $package"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Special handling for PyTorch packages
    if [ "$package" == "torch" ] || [ "$package" == "torchaudio" ]; then
        echo "🔥 Large package - this may take 10-20 minutes..."
        echo "   ⚠️  Keep Pi connected to power and WiFi!"
        
        # Try CPU-only version first
        if [ "$package" == "torch" ]; then
            pip install --no-cache-dir --timeout 1800 --retries 5 \
                --index-url https://download.pytorch.org/whl/cpu \
                torch torchaudio || {
                echo "⚠️  CPU-only install failed, trying standard..."
                pip install --no-cache-dir --timeout 1800 --retries 5 torch
                pip install --no-cache-dir --timeout 1800 --retries 5 torchaudio
            }
            # Skip torchaudio since we installed both
            continue
        else
            # torchaudio already installed with torch
            continue
        fi
    fi
    
    # Regular packages
    if pip install --no-cache-dir --timeout 600 --retries 3 "$package"; then
        echo "✅ Successfully installed $package"
    else
        echo "❌ Failed to install $package"
        echo "   You can retry later with: pip install $package"
    fi
    
    echo ""
done

echo ""
echo "✅ Installation recovery complete!"
echo ""
echo "📋 Final status:"
pip list | grep -E "$(IFS='|'; echo "${REQUIRED_PACKAGES[*]}")" || echo "Run 'pip list' to see all packages"



