# Running Web Client in Headless Browser on Raspberry Pi

This approach runs your existing web-client in a headless Chromium browser instead of rewriting it in Python.

## Difficulty Assessment: **Medium** (3-4 hours setup)

### Pros ✅
- **Single codebase** - No need to maintain Python client
- **Browser APIs** - Well-tested audio handling
- **Easier updates** - Just update web-client code
- **Full feature parity** - All web-client features work

### Cons ⚠️
- **Resource overhead** - ~100-200MB RAM for Chromium
- **Audio setup** - Needs proper flags for headless audio
- **Initial complexity** - More moving parts (browser + automation)

## Setup Instructions

### 1. Install Dependencies

```bash
# On Raspberry Pi
sudo apt update
sudo apt install -y chromium-browser nodejs npm

# Install Node.js dependencies
cd /path/to/Grokie/web-client
npm install

# Install Puppeteer (for browser automation)
cd ../raspberry-pi-client
npm install puppeteer-core
```

### 2. Configure Audio Devices

The headless browser needs access to your Pi's microphone and speakers:

```bash
# Test audio devices
arecord -l  # List microphones
aplay -l    # List speakers

# Set default audio device (if needed)
# Edit ~/.asoundrc or /etc/asound.conf
```

### 3. Set Environment Variables

Create a `.env` file in `raspberry-pi-client/`:

```bash
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_ROOM=test-room
PARTICIPANT_NAME=raspberry-pi
CHROMIUM_PATH=/usr/bin/chromium-browser  # Optional, auto-detected
DEV_MODE=true  # Set to false to use built files
```

### 4. Run the Headless Client

**Option A: Development Mode (with Vite dev server)**

```bash
# Terminal 1: Start Vite dev server
cd web-client
npm run dev

# Terminal 2: Start token server
cd web-client
npm run server

# Terminal 3: Run headless browser
cd raspberry-pi-client
node run_web_client_headless.js
```

**Option B: Production Mode (built files)**

```bash
# Build the web client first
cd web-client
npm run build

# Start token server
npm run server

# Run headless browser (DEV_MODE=false)
cd ../raspberry-pi-client
DEV_MODE=false node run_web_client_headless.js
```

## Audio Configuration

### Real Audio Devices (Recommended)

For real microphone/speaker access, you may need to:

1. **Use PulseAudio** (if available):
```bash
sudo apt install pulseaudio
pulseaudio --start
```

2. **Modify browser args** in `run_web_client_headless.js`:
```javascript
args: [
  '--no-sandbox',
  '--use-fake-ui-for-media-stream', // Auto-allow mic
  // Remove '--use-fake-device-for-media-stream' to use real devices
],
```

3. **Set ALSA defaults**:
```bash
# Find your audio card
cat /proc/asound/cards

# Set as default in ~/.asoundrc
pcm.!default {
  type hw
  card 1  # Your card number
}
ctl.!default {
  type hw
  card 1
}
```

### Testing Audio

```bash
# Test microphone
arecord -d 5 test.wav
aplay test.wav

# Test in browser (temporarily set headless: false)
# Then check browser console for audio errors
```

## Running as a Service

Create a systemd service:

```bash
sudo nano /etc/systemd/system/grok-headless.service
```

```ini
[Unit]
Description=GROK Voice Agent (Headless Browser)
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Grokie/raspberry-pi-client
Environment="PATH=/usr/bin:/usr/local/bin"
EnvironmentFile=/home/pi/Grokie/raspberry-pi-client/.env
ExecStart=/usr/bin/node run_web_client_headless.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable grok-headless.service
sudo systemctl start grok-headless.service
sudo systemctl status grok-headless.service
```

## Troubleshooting

### Browser Won't Launch
```bash
# Check Chromium path
which chromium-browser

# Try with explicit path
CHROMIUM_PATH=/usr/bin/chromium-browser node run_web_client_headless.js
```

### No Audio Input/Output
- Check browser console logs (they're printed to terminal)
- Verify audio devices: `arecord -l` and `aplay -l`
- Try running with `headless: false` to see what's happening
- Check PulseAudio: `pulseaudio --check -v`

### Connection Issues
- Make sure token server is running on port 8080
- Check LiveKit server is accessible
- Verify environment variables are set correctly

### Memory Issues
- Raspberry Pi 4 (4GB+) recommended
- Close other applications
- Consider using lighter browser flags

## Comparison: Headless Browser vs Python Client

| Aspect | Headless Browser | Python Client |
|--------|-----------------|---------------|
| **Setup Time** | 3-4 hours | 2-3 hours |
| **Memory Usage** | ~150MB | ~50MB |
| **Code Maintenance** | Single codebase | Two codebases |
| **Audio Handling** | Browser APIs (robust) | Direct ALSA (more control) |
| **Updates** | Update web-client only | Update both |
| **Debugging** | Browser DevTools (if not headless) | Python debugger |
| **Performance** | Slightly slower | Faster |

## Recommendation

**Use headless browser if:**
- You want to maintain a single codebase
- You have a Pi 4 with 4GB+ RAM
- You prioritize easy updates over raw performance

**Use Python client if:**
- You need lower memory footprint
- You want direct audio device control
- You prefer native performance

## Next Steps

1. Try the headless browser approach
2. If audio doesn't work, debug with `headless: false`
3. If it works but is too slow/heavy, stick with Python client
4. Consider hybrid: use headless for development, Python for production




