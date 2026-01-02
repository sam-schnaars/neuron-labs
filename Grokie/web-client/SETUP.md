# Quick Setup Guide

## Required Services (All must be running):

### 1. LiveKit Server
```bash
# Install if needed
npm install -g livekit-cli

# Start server
livekit-server --dev
```
Should show: `LiveKit server listening on port 7880`

### 2. GROK Agent
```bash
# From the main Grokie directory
python grok_voice_agent.py
```
Should show: `Server is ready to accept connections...`

### 3. Token Server
```bash
# From web-client directory
cd web-client
npm run server
```
Should show: `Token server running on http://localhost:8080`

### 4. Web Client
```bash
# From web-client directory (in a new terminal)
npm run dev
```
Should open browser at `http://localhost:3000`

## Troubleshooting

**Error: "Cannot reach token server"**
- Make sure token server is running on port 8080
- Check: `curl http://localhost:8080/api/health`

**Error: "Connection refused" on port 7880**
- Make sure LiveKit server is running
- Check: `curl http://localhost:7880`

**Error: "access_token=[object Object]"**
- This means token generation failed
- Check token server logs
- Make sure token server can reach LiveKit

**Microphone not working**
- Check browser permissions (chrome://settings/content/microphone)
- Make sure you clicked "Allow" when prompted
- Try refreshing the page

