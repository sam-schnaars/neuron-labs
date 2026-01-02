# GROK Voice Agent - Raspberry Pi Client (WM8960)

A Node.js/TypeScript client to connect your Raspberry Pi to the GROK voice agent using WM8960 Audio HAT for microphone input and speaker output.

## Hardware Requirements

- Raspberry Pi (any model)
- **WM8960 Audio HAT** (Waveshare or compatible)
- WM8960 driver installed and configured

## Prerequisites

### 1. Install WM8960 Audio Driver

If you haven't already installed the WM8960 driver:

```bash
# Clone the driver repository
git clone https://github.com/waveshare/WM8960-Audio-HAT
cd WM8960-Audio-HAT

# Run the installation script
sudo ./install.sh

# Reboot your Raspberry Pi
sudo reboot
```

### 2. Verify WM8960 Installation

After rebooting, verify the sound card is recognized:

```bash
# List all sound cards
aplay -l
arecord -l

# You should see an entry for "wm8960soundcard" or similar
cat /proc/asound/cards
```

### 3. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install audio and build dependencies
sudo apt install -y \
  nodejs npm \
  sox \
  mpg123 \
  alsa-utils \
  build-essential \
  git

# Verify installations
sox --version
mpg123 --version
node --version  # Should be v18 or higher
```

## Setup on Raspberry Pi

### 1. Navigate to Project Directory

```bash
cd /path/to/Grokie/raspberry-pi-client
```

### 2. Install Node.js Dependencies

```bash
npm install
```

### 3. Configure Environment

Create a `.env` file in the `raspberry-pi-client` directory:

```bash
# Copy from example if available, or create new
nano .env
```

Add the following configuration:

```env
# LiveKit Server Configuration
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

# Room Configuration
LIVEKIT_ROOM=test-room
PARTICIPANT_NAME=raspberry-pi

# Token Server (if using separate token server)
TOKEN_SERVER_URL=http://localhost:8080

# Sound Card Index (auto-detected by script, but can override)
# SOUND_CARD_INDEX=1
```

**Important**: Update `LIVEKIT_URL` to point to your LiveKit server. If running on a different machine, use the IP address:
```
LIVEKIT_URL=ws://192.168.1.100:7880
```

### 4. Test Audio Hardware

Before running the client, test that WM8960 is working:

```bash
# Test microphone recording (5 seconds)
arecord -D hw:1,0 -f S16_LE -r 24000 -c 1 -d 5 test.wav

# Test speaker playback
aplay -D hw:1,0 test.wav

# Adjust volume if needed
amixer -c 1 set Speaker 114
alsamixer -c 1  # Interactive volume control
```

**Note**: Replace `hw:1,0` with your actual sound card index if different. The startup script will auto-detect this.

### 5. Build TypeScript

```bash
npm run build
```

This compiles TypeScript to JavaScript in the `dist/` directory.

## Running the Client

### Quick Start

Use the provided bash script (recommended):

```bash
./run-pi-client.sh
```

The script will:
- Auto-detect WM8960 sound card index
- Set volume levels
- Load environment variables
- Build TypeScript if needed
- Start the client

### Manual Start

If you prefer to run manually:

```bash
# Set sound card index (find it first)
export SOUND_CARD_INDEX=$(awk '/wm8960soundcard/ {print $1}' /proc/asound/cards | head -n1)

# Set volume
amixer -c $SOUND_CARD_INDEX set Speaker 114

# Build if needed
npm run build

# Start
npm start
```

## Running as a Service (Optional)

To run automatically on boot:

### 1. Create Systemd Service

```bash
sudo nano /etc/systemd/system/grok-voice.service
```

Add this content (update paths as needed):

```ini
[Unit]
Description=GROK Voice Agent Client (WM8960)
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Grokie/raspberry-pi-client
Environment="NODE_ENV=production"
EnvironmentFile=/home/pi/Grokie/raspberry-pi-client/.env
ExecStart=/usr/bin/node /home/pi/Grokie/raspberry-pi-client/dist/index.js
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable grok-voice.service

# Start service now
sudo systemctl start grok-voice.service

# Check status
sudo systemctl status grok-voice.service

# View logs
sudo journalctl -u grok-voice.service -f
```

## Troubleshooting

### Audio Issues

**WM8960 not detected:**
```bash
# Check if driver is loaded
lsmod | grep snd_soc_wm8960

# Check sound cards
cat /proc/asound/cards

# If not found, reinstall driver
cd WM8960-Audio-HAT
sudo ./install.sh
sudo reboot
```

**Microphone not working:**
```bash
# Check if microphone is detected
arecord -l

# Test recording with WM8960
arecord -D hw:1,0 -f S16_LE -r 24000 -c 1 -d 3 test.wav

# Check ALSA configuration
alsamixer -c 1
# Press F4 to see capture controls, adjust microphone levels
```

**No audio output:**
```bash
# Check audio output devices
aplay -l

# Test audio output
speaker-test -D hw:1,0 -t wav -c 2

# Adjust volume
amixer -c 1 set Speaker 114
alsamixer -c 1  # Press F3 for playback controls
```

**Audio format issues:**
- Ensure sox is installed: `sudo apt install sox`
- Ensure mpg123 is installed: `sudo apt install mpg123`
- Check sample rate matches (24kHz for LiveKit)

### Connection Issues

**Can't connect to LiveKit server:**
- Check that the LiveKit server is running
- Verify the `LIVEKIT_URL` in `.env` is correct
- Check network connectivity: `ping your-server-ip`
- Ensure firewall allows WebSocket connections on port 7880
- If using remote server, ensure it's accessible from your network

**Token server errors:**
- Ensure token server is running (if using separate server)
- Check `TOKEN_SERVER_URL` in `.env`
- Verify token server is accessible: `curl http://localhost:8080/api/health`

**Room connection fails:**
- Make sure the GROK agent is running
- Verify room name matches between client and agent
- Check LiveKit server logs
- Verify API keys and secrets are correct

### Node.js/TypeScript Issues

**Build errors:**
```bash
# Clean and rebuild
rm -rf dist node_modules
npm install
npm run build
```

**Runtime errors:**
```bash
# Check Node.js version (needs v18+)
node --version

# Update Node.js if needed
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

**Module not found errors:**
```bash
# Reinstall dependencies
npm install

# Check if dist/ directory exists
ls -la dist/
```

### Sound Card Index Issues

If the script can't find WM8960:

```bash
# Manually find the card index
cat /proc/asound/cards

# Set it manually in .env
echo "SOUND_CARD_INDEX=1" >> .env

# Or export before running
export SOUND_CARD_INDEX=1
npm start
```

## Network Setup

If your LiveKit server is on a different machine:

1. **Find your server's IP address:**
   ```bash
   # On the server machine
   hostname -I
   ```

2. **Update LIVEKIT_URL in .env:**
   ```
   LIVEKIT_URL=ws://192.168.1.100:7880
   ```

3. **Test connectivity:**
   ```bash
   # From the Pi
   ping 192.168.1.100
   curl http://192.168.1.100:8080/api/health  # If using token server
   ```

## Usage Tips

- **Voice activation**: The microphone is always on when connected
- **Disconnect**: Press `Ctrl+C` to disconnect gracefully
- **Check status**: Look for connection messages in the console
- **Multiple Pis**: Each Pi needs a unique `PARTICIPANT_NAME`
- **Volume control**: Use `alsamixer -c 1` to adjust microphone and speaker levels

## Architecture Notes

This client uses:
- **sox** for microphone input (streaming raw PCM via ALSA)
- **mpg123** or **aplay** for speaker output (playing audio from LiveKit)
- **livekit-client** for WebSocket connection to LiveKit server
- **WM8960 Audio HAT** for hardware audio I/O

**Note**: The `livekit-client` package is primarily designed for browsers. For full Node.js audio support with custom sources, consider using `@livekit/agents` SDK which has better Node.js audio handling capabilities.

## Advanced Configuration

### Adjusting Audio Quality

Edit `src/audio-input.ts` to change sample rate:

```typescript
this.audioInput = new AudioInputStream({
  sampleRate: 24000,  // 24kHz (LiveKit standard)
  channels: 1,         // Mono
  format: 'raw',
});
```

### Using Different Audio Formats

Edit `src/audio-output.ts` to switch between mpg123 (MP3) and aplay (PCM):

```typescript
this.audioOutput = new AudioOutputStream({
  useMpg123: true,  // Use mpg123 for MP3, false for aplay (PCM)
});
```

### Custom Sound Card Selection

Override auto-detection in `.env`:

```env
SOUND_CARD_INDEX=1
```

## Support

For issues, check:
1. All services are running (LiveKit server, GROK agent, token server if used)
2. Network connectivity between Pi and server
3. WM8960 driver is installed and sound card is detected
4. Audio permissions and ALSA configuration
5. Node.js dependencies are installed and up to date
6. TypeScript is compiled (`dist/` directory exists)

## Related Files

- `src/index.ts` - Main entry point
- `src/grok-client.ts` - LiveKit client implementation
- `src/audio-input.ts` - Microphone input via sox/ALSA
- `src/audio-output.ts` - Speaker output via mpg123/aplay
- `run-pi-client.sh` - Startup script with auto-detection
- `package.json` - Node.js dependencies
- `.env` - Configuration file (create this)
