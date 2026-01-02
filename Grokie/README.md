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

## Documentation

For more information, see the [LiveKit xAI plugin documentation](https://docs.livekit.io/agents/models/realtime/plugins/xai/).

