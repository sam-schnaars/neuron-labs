# GROK Voice Agent Web Client

A simple web-based client to connect and talk to your GROK voice agent.

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure LiveKit (optional):**
   - Copy `.env.example` to `.env`
   - Update the values if you're not using local defaults

## Usage

1. **Start the token server (required):**
   ```bash
   npm run server
   ```
   This runs on `http://localhost:8080` and generates LiveKit access tokens.

2. **Start the web client (in a new terminal):**
   ```bash
   npm run dev
   ```

3. **Open your browser:**
   - The app will automatically open at `http://localhost:3000`
   - Or manually navigate to that URL

4. **Connect to your agent:**
   - Make sure your GROK agent is running (`python grok_voice_agent.py`)
   - Make sure LiveKit server is running (`livekit-server --dev`)
   - Enter a room name (default: `test-room`)
   - Enter your name
   - Click "Connect to Agent"
   - Allow microphone access when prompted
   - Start speaking!

## Features

- ✅ Real-time voice communication
- ✅ Simple, clean UI
- ✅ Connection status indicators
- ✅ Automatic audio playback
- ✅ Microphone input handling

## Production Notes

For production use, you'll need to:
1. Set up a backend endpoint to generate LiveKit access tokens securely
2. Update the `generateToken` function in `src/main.ts` to call your backend
3. Build the app: `npm run build`

## Troubleshooting

- **Can't connect?** Make sure:
  - LiveKit server is running (`livekit-server --dev`)
  - GROK agent is running
  - Room names match between client and agent

- **No audio?** Check:
  - Microphone permissions are granted
  - Browser audio settings
  - Console for error messages

