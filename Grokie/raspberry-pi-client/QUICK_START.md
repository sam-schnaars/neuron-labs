# Quick Start Guide - Raspberry Pi Setup

Follow these steps to get the GROK Voice Agent running on your Raspberry Pi with WM8960 Audio HAT.

## Step 1: Install WM8960 Audio Driver (if not already installed)

```bash
# Clone the driver repository
git clone https://github.com/waveshare/WM8960-Audio-HAT
cd WM8960-Audio-HAT

# Run the installation script
sudo ./install.sh

# Reboot your Raspberry Pi
sudo reboot
```

After rebooting, verify the sound card is detected:
```bash
cat /proc/asound/cards
# You should see "wm8960soundcard" listed
```

## Step 2: Install System Dependencies

```bash
# Update package list
sudo apt update

# Install required packages
sudo apt install -y \
  nodejs npm \
  sox \
  mpg123 \
  alsa-utils \
  build-essential \
  git

# Verify installations
node --version  # Should be v18 or higher
sox --version
mpg123 --version
```

If Node.js version is too old (< 18), upgrade it:
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

## Step 3: Transfer Files to Raspberry Pi

### Option A: Using Git (if you have the repo on GitHub)
```bash
cd ~
git clone <your-repo-url>
cd neuron-labs/Grokie/raspberry-pi-client
```

### Option B: Using SCP (from your development machine)
```bash
# From your Mac/PC, run:
scp -r Grokie/raspberry-pi-client pi@<raspberry-pi-ip>:/home/pi/
```

### Option C: Using USB drive or network share
Copy the `raspberry-pi-client` folder to your Pi's home directory.

## Step 4: Navigate to Project Directory

```bash
cd ~/raspberry-pi-client
# or wherever you placed the files
```

## Step 5: Install Node.js Dependencies

```bash
npm install
```

This will install:
- `livekit-client`
- `dotenv`
- `typescript` and `@types/node`

## Step 6: Create Configuration File

```bash
# Create .env file
nano .env
```

Add the following (update with your actual values):

```env
# LiveKit Server Configuration
# Change to your LiveKit server IP/URL
LIVEKIT_URL=ws://192.168.1.100:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# Room Configuration (must match your GROK agent's room)
LIVEKIT_ROOM=test-room

# Participant name (unique for this Pi)
PARTICIPANT_NAME=raspberry-pi

# Token Server URL (if using separate token server)
TOKEN_SERVER_URL=http://192.168.1.100:8080
```

**Important**: 
- Replace `192.168.1.100` with your actual LiveKit server IP address
- If LiveKit server is on the same Pi, use `ws://localhost:7880`
- Make sure `LIVEKIT_ROOM` matches the room name used by your GROK agent

Save and exit: `Ctrl+X`, then `Y`, then `Enter`

## Step 7: Test Audio Hardware

Before running the client, verify WM8960 is working:

```bash
# Find your sound card index
cat /proc/asound/cards
# Note the number next to "wm8960soundcard" (usually 1)

# Test microphone (replace 1 with your card index if different)
arecord -D hw:1,0 -f S16_LE -r 24000 -c 1 -d 5 test.wav

# Test speaker
aplay -D hw:1,0 test.wav

# Adjust volume if needed
amixer -c 1 set Speaker 114
```

## Step 8: Build TypeScript

```bash
npm run build
```

This compiles the TypeScript code to JavaScript in the `dist/` directory.

## Step 9: Make Startup Script Executable

```bash
chmod +x run-pi-client.sh
```

## Step 10: Run the Client

### Option A: Using the startup script (recommended)
```bash
./run-pi-client.sh
```

The script will:
- Auto-detect WM8960 sound card
- Set volume
- Load environment variables
- Build if needed
- Start the client

### Option B: Manual start
```bash
# Set sound card index
export SOUND_CARD_INDEX=$(awk '/wm8960soundcard/ {print $1}' /proc/asound/cards | head -n1)

# Set volume
amixer -c $SOUND_CARD_INDEX set Speaker 114

# Start
npm start
```

## Step 11: Verify Connection

You should see output like:
```
🎤 GROK Voice Agent - Raspberry Pi Client
==================================================
Using sound card index: 1
LiveKit URL: ws://192.168.1.100:7880
Room: test-room
==================================================

Generating access token...
Token received successfully
Creating room instance...
Connecting to LiveKit server...
✅ Connected to room: test-room

✅ Connected! Microphone is active - start speaking!
Press Ctrl+C to disconnect
```

## Troubleshooting

### "WM8960 sound card not found"
- Make sure WM8960 driver is installed (Step 1)
- Check: `cat /proc/asound/cards`
- Reboot if needed: `sudo reboot`

### "Cannot reach token server"
- Verify token server is running
- Check `TOKEN_SERVER_URL` in `.env`
- Test: `curl http://localhost:8080/api/health`

### "Connection failed"
- Verify LiveKit server is running
- Check `LIVEKIT_URL` in `.env` is correct
- Test network: `ping <server-ip>`
- Ensure GROK agent is running

### "Audio input error" or "Audio output error"
- Verify sox and mpg123 are installed
- Test audio hardware (Step 7)
- Check sound card index: `cat /proc/asound/cards`
- Adjust volume: `alsamixer -c 1`

### "Module not found" or build errors
```bash
# Clean and reinstall
rm -rf node_modules dist
npm install
npm run build
```

## Running in Background (Optional)

To keep the client running after you disconnect from SSH:

### Using screen:
```bash
# Install screen
sudo apt install screen

# Start a screen session
screen -S grok

# Run the client
./run-pi-client.sh

# Detach: Press Ctrl+A, then D
# Reattach: screen -r grok
```

### Using systemd service:
See the main README.md for systemd service setup instructions.

## Stopping the Client

Press `Ctrl+C` to gracefully disconnect and stop the client.

## Next Steps

- Set up as a systemd service to run on boot (see README.md)
- Adjust audio levels with `alsamixer -c 1`
- Monitor logs for debugging
- Configure multiple Pis with different `PARTICIPANT_NAME` values

