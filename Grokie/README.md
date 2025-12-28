# GROK Voice Agent API Integration

This project demonstrates how to use the GROK voice agent API through LiveKit Agents.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up your API key:**
   - Copy `.env.example` to `.env`
   - Add your xAI API key to the `.env` file:
     ```
     XAI_API_KEY=your_actual_api_key_here
     ```
   - You can get your API key from [x.ai/settings](https://x.ai/settings)

## Usage

### Step 1: Set up LiveKit Server

You need a LiveKit server running. Choose one option:

**Option A: Local Development Server (Easiest)**
```bash
# Install LiveKit CLI
npm install -g livekit-cli

# Start local server
livekit-server --dev
```

This will start a server at `ws://localhost:7880` with default credentials:
- API Key: `devkey`
- API Secret: `secret`

**Option B: LiveKit Cloud**
1. Sign up at [cloud.livekit.io](https://cloud.livekit.io)
2. Get your credentials and add to `.env`:
   ```
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret
   ```

### Step 2: Talk to the Agent

**Easiest Method - Console Mode (Recommended):**

Run the agent in console mode - this gives you a built-in voice interface:
```bash
python grok_voice_agent.py console
```

This will:
- Start the agent server
- Open a voice console where you can speak directly
- The agent will hear you through your microphone and respond through your speakers
- Press `Ctrl+C` to exit

**Alternative: Run as Server + Use Test Client**

If you prefer to run the server separately:

1. In one terminal, start the agent server:
   ```bash
   python grok_voice_agent.py
   ```

2. In another terminal, run the test client:
   ```bash
   python test_client.py
   ```

The client will connect to the same room, and you can start talking to the GROK agent!

**Web Client (Browser-based):**

For a web-based interface, use the included web client:

1. Navigate to the web-client directory:
   ```bash
   cd web-client
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the token server (in one terminal):
   ```bash
   npm run server
   ```

4. Start the web client (in another terminal):
   ```bash
   npm run dev
   ```

5. Open your browser to `http://localhost:3000`
   - Enter a room name (default: `test-room`)
   - Click "Connect to Agent"
   - Allow microphone access
   - Start speaking!

See `web-client/README.md` for more details.

## Features

- Real-time voice interactions using GROK
- Customizable assistant instructions
- Multiple voice options (Ara, Rex, Sal, Eve, Leo)
- Turn detection configuration support

## Configuration

You can customize the voice agent by modifying the `RealtimeModel` initialization in `grok_voice_agent.py`:

- **Voice selection**: Uncomment and set the `voice` parameter
- **Turn detection**: Add `turn_detection` configuration for better conversation flow

## Raspberry Pi Setup (Button Toggle)

For Raspberry Pi with GPIO button control (e.g., Whisplay HAT):

### Installation

1. **Install all dependencies:**
   ```bash
   bash install_dependencies.sh
   ```
   
   This will install:
   - System packages (Python, audio libraries, etc.)
   - Node.js and npm (for LiveKit CLI)
   - LiveKit CLI
   - Python dependencies (with optional virtual environment)
   - RPi.GPIO for button control

   **Or install manually:**
   ```bash
   # Option A: With virtual environment (recommended for isolation)
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -r raspberry-pi-client/requirements.txt
   pip install RPi.GPIO
   
   # Option B: System packages (matches whisplay approach)
   pip install -r requirements.txt --break-system-packages
   pip install -r raspberry-pi-client/requirements.txt --break-system-packages
   pip install RPi.GPIO --break-system-packages
   ```

2. **Set up your `.env` file:**
   ```bash
   # Required
   XAI_API_KEY=your_actual_api_key_here
   
   # Optional - LiveKit server settings (defaults shown)
   LIVEKIT_URL=ws://localhost:7880
   LIVEKIT_API_KEY=devkey
   LIVEKIT_API_SECRET=secret
   
   # Optional - Auto-start GROK agent server (set to 'true' to enable)
   SERVE_GROK_AGENT=false
   ```

3. **Set up LiveKit server:**
   - LiveKit CLI should already be installed by `install_dependencies.sh`
   - Start server: `livekit-server --dev` (in a separate terminal, or set up as a service)
   - Or use LiveKit Cloud and update `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` in `.env`

### Usage

**Run with button toggle:**
```bash
./run_grokie.sh
```

- Press the button once to start GROK connection
- Press again to stop GROK connection
- Press Ctrl+C to exit

**Configuration options:**

- **Auto-start server**: Set `SERVE_GROK_AGENT=true` in `.env` to automatically start the GROK agent server when you run `run_grokie.sh`
- **Manual server**: Leave `SERVE_GROK_AGENT=false` (or omit it) and run `python3 grok_voice_agent.py` separately

**Note:** The script uses GPIO pin 11 (same as whisplay). Make sure only one script uses the GPIO at a time.

## Documentation

For more information, see the [LiveKit xAI plugin documentation](https://docs.livekit.io/agents/models/realtime/plugins/xai/).

