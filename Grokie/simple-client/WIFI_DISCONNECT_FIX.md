# Fix WiFi Disconnection During Installation

## What Happened

Your Pi disconnected from WiFi during the large PyTorch download. This is a common issue caused by:

1. **Network overload** - Large downloads can overwhelm the WiFi connection
2. **Power issues** - Insufficient power can cause WiFi instability
3. **WiFi driver issues** - Some Pi models have WiFi stability problems
4. **Router issues** - Router may drop connection during long transfers

## Immediate Steps

### 1. Reconnect to WiFi

If you have physical access to the Pi:
```bash
# Check WiFi status
iwconfig

# Reconnect using raspi-config
sudo raspi-config
# Navigate to: Network Options > Wi-fi
# Enter your SSID and password

# Or use nmtui (text-based network manager)
sudo nmtui
```

If you're SSH'd in and lost connection:
- You'll need physical access or use a monitor/keyboard
- Or wait for it to auto-reconnect (if configured)

### 2. Check Connection

Once reconnected:
```bash
# Verify WiFi connection
iwgetid -r

# Test internet
ping -c 4 8.8.8.8
```

## Solutions to Prevent Future Disconnections

### Option 1: Use Ethernet (Most Reliable)

**Best solution** - Use an ethernet cable instead of WiFi:
- More stable for large downloads
- Faster speeds
- No disconnection issues

```bash
# Just plug in ethernet cable - it should auto-connect
# Check connection:
ip addr show eth0
```

### Option 2: Install Packages One at a Time

Use the resilient installation script that installs packages individually:

```bash
chmod +x install-pi-requirements-resilient.sh
./install-pi-requirements-resilient.sh
```

This script:
- Installs packages one at a time
- Checks WiFi connection between installs
- Can resume if interrupted
- Uses longer timeouts

### Option 3: Improve WiFi Stability

**Increase WiFi power management:**
```bash
# Edit WiFi config
sudo nano /etc/network/interfaces

# Or create/modify wpa_supplicant config
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf

# Add these settings:
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="YOUR_SSID"
    psk="YOUR_PASSWORD"
    # Add these for stability:
    scan_ssid=1
    ap_scan=1
}
```

**Disable WiFi power saving:**
```bash
# Create a config file to disable power saving
sudo nano /etc/modprobe.d/8192cu.conf

# Add this line:
options 8192cu rtw_power_mgnt=0 rtw_enusbss=0

# Reboot
sudo reboot
```

### Option 4: Use Better Power Supply

WiFi disconnections can be caused by insufficient power:
- Use official Raspberry Pi power supply (2.5A+)
- Avoid USB power from computers
- Use a quality USB-C power adapter (for Pi 4/5)

### Option 5: Install PyTorch Separately with Resume

Install PyTorch in a way that can resume if interrupted:

```bash
# Set temp directory
export TMPDIR=/home/pi/tmp
mkdir -p /home/pi/tmp

# Install PyTorch with very long timeout
pip install --no-cache-dir \
    --timeout 1800 \
    --retries 10 \
    --index-url https://download.pytorch.org/whl/cpu \
    torch torchaudio
```

### Option 6: Download on Another Machine and Transfer

If WiFi keeps disconnecting:

1. **Download on your Mac/PC:**
   ```bash
   # On your Mac/PC, create a virtual environment
   python3 -m venv pi-packages
   source pi-packages/bin/activate
   
   # Download packages (but don't install)
   pip download --platform linux_aarch64 \
       --only-binary :all: \
       -r requirements.txt \
       -d pi-packages-downloads
   ```

2. **Transfer to Pi:**
   ```bash
   # From Mac/PC
   scp -r pi-packages-downloads pi@<pi-ip>:/home/pi/
   ```

3. **Install from local files on Pi:**
   ```bash
   # On Pi
   pip install --no-index --find-links pi-packages-downloads -r requirements.txt
   ```

## Recommended Approach

**Best solution for stability:**

1. **Use ethernet cable** (if possible)
2. **Use the resilient installation script:**
   ```bash
   ./install-pi-requirements-resilient.sh
   ```
3. **Install during off-peak hours** (less network congestion)
4. **Ensure adequate power supply**

## If Installation Was Interrupted

The resilient script can resume, but if you need to manually resume:

```bash
# Check what's already installed
pip list | grep -E "torch|whisper|pyaudio"

# Install missing packages
pip install --no-cache-dir --timeout 600 <missing-package>
```

## Check What's Already Installed

After reconnecting, check what installed successfully:

```bash
source venv/bin/activate  # if using venv
pip list
```

Then install only what's missing from `requirements.txt`.

## Quick Recovery Command

If you just need to finish the installation:

```bash
# Make sure you're in the right directory and venv
cd /path/to/simple-client
source venv/bin/activate  # if using venv

# Set temp directory
export TMPDIR=/home/pi/tmp
mkdir -p /home/pi/tmp

# Install remaining packages one at a time
pip install --no-cache-dir --timeout 600 torch
pip install --no-cache-dir --timeout 600 torchaudio
pip install --no-cache-dir --timeout 600 openai-whisper
```

