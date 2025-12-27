# GROK Voice Agent - Raspberry Pi Client

A simple client to connect your Raspberry Pi to the GROK voice agent using the Pi's built-in microphone and speakers.

## Hardware Requirements

- Raspberry Pi (any model with audio I/O)
- Microphone (USB or built-in)
- Speakers or headphones connected to the Pi's audio output

## Setup on Raspberry Pi

### 1. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install audio dependencies
sudo apt install -y python3-pip python3-venv portaudio19-dev python3-pyaudio alsa-utils

# Test audio devices
arecord -l  # List recording devices
aplay -l    # List playback devices
```

### 2. Set Up Python Environment

```bash
# Navigate to the raspberry-pi-client directory
cd raspberry-pi-client

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit the .env file with your settings
nano .env
```

Update the `.env` file with:
- `LIVEKIT_URL`: The WebSocket URL of your LiveKit server (e.g., `ws://192.168.1.100:7880` for a server on your network)
- `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`: Your LiveKit credentials
- `LIVEKIT_ROOM`: The room name (must match your agent's room)
- `PARTICIPANT_NAME`: A unique name for this Pi

### 4. Test Audio

```bash
# Test microphone (record 5 seconds)
arecord -d 5 test.wav

# Test playback
aplay test.wav

# If you have issues, check audio devices
cat /proc/asound/cards
```

### 5. Run the Client

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run the client
python grok_pi_client.py
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
Description=GROK Voice Agent Client
After=network.target sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Grokie/raspberry-pi-client
Environment="PATH=/home/pi/Grokie/raspberry-pi-client/venv/bin"
ExecStart=/home/pi/Grokie/raspberry-pi-client/venv/bin/python grok_pi_client.py
Restart=always
RestartSec=10

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

**Microphone not working:**
```bash
# Check if microphone is detected
arecord -l

# Test recording
arecord -d 3 -f cd test.wav
aplay test.wav

# Set default audio device (if needed)
# Edit /etc/asound.conf or ~/.asoundrc
```

**No audio output:**
```bash
# Check audio output devices
aplay -l

# Test audio output
speaker-test -t wav -c 2

# Adjust volume
alsamixer
```

### Connection Issues

**Can't connect to server:**
- Check that the LiveKit server is running
- Verify the `LIVEKIT_URL` in `.env` is correct
- Check network connectivity: `ping your-server-ip`
- Ensure firewall allows WebSocket connections

**Room connection fails:**
- Make sure the GROK agent is running
- Verify room name matches between client and agent
- Check LiveKit server logs

### Python Issues

**Import errors:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

**PortAudio errors:**
```bash
# Reinstall portaudio
sudo apt install --reinstall portaudio19-dev
pip install --force-reinstall pyaudio
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
   ```

## Usage Tips

- **Voice activation**: The microphone is always on when connected
- **Disconnect**: Press `Ctrl+C` to disconnect
- **Check status**: Look for connection messages in the console
- **Multiple Pis**: Each Pi needs a unique `PARTICIPANT_NAME`

## Advanced Configuration

### Using USB Microphone

If you have a USB microphone:

```bash
# List audio devices
arecord -l

# Use specific device (update device number)
# You may need to modify the code to specify the device
```

### Adjusting Audio Quality

Edit `grok_pi_client.py` and modify the audio source settings:

```python
source = rtc.AudioSource(24000, 1)  # 24kHz, mono
# Try: 48000 for higher quality (if supported)
```

## Support

For issues, check:
1. All services are running (LiveKit server, GROK agent)
2. Network connectivity
3. Audio device permissions
4. Python dependencies are installed


