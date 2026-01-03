# Simple Grok Voice Agent

A simple command-line voice agent that uses:
- **Whisper** for speech-to-text
- **Grok API** for AI responses
- **pyttsx3** for text-to-speech
- **Silero VAD** for voice activity detection

## Setup

### On macOS/Linux

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Note: On macOS, you may need to install PortAudio for pyaudio:
   ```bash
   brew install portaudio
   ```

### On Raspberry Pi

1. **Install system dependencies:**
   ```bash
   sudo apt update
   sudo apt install -y \
     portaudio19-dev \
     python3-pyaudio \
     python3-pip \
     python3-venv \
     alsa-utils
   ```

2. **Create virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   **Note**: PyTorch installation on Pi can take 10-20 minutes. The script automatically uses the "tiny" Whisper model on Pi for better performance.

4. **Configure audio device (if using WM8960 or other HAT):**
   
   First, find your audio device index:
   ```bash
   arecord -l  # List recording devices
   ```
   
   Then set it in your `.env` file:
   ```
   INPUT_DEVICE_INDEX=1  # Replace with your device index
   ```

5. **Performance tips for Pi:**
   - Use a Pi 4 (2GB+) for best results
   - Close other applications to free up RAM
   - The script automatically uses "tiny" Whisper model on Pi
   - You can override with `WHISPER_MODEL=small` in `.env` if you have a Pi 4 with 4GB+

2. **Set up your API key:**
   
   Create a `.env` file in this directory or set the environment variable:
   ```bash
   export XAI_API_KEY=your_api_key_here
   ```
   
   Or create a `.env` file:
   ```
   XAI_API_KEY=your_api_key_here
   ```
   
   You can get your API key from [x.ai/settings](https://x.ai/settings)

## Usage

Run the voice agent:
```bash
python simple-client.py
```

The agent will:
1. Listen for your voice input (detects when you start and stop speaking)
2. Transcribe your speech using Whisper
3. Send the transcript to Grok API for a response
4. Speak the response back to you

Press `Ctrl+C` to exit.

## How it works

- The agent continuously records audio from your microphone
- Uses Silero VAD to detect when you're speaking vs. silent
- When silence is detected after speech, it transcribes the audio
- Sends the transcript to Grok and speaks the response

## Troubleshooting

### General Issues

- **No audio input**: Make sure your microphone permissions are enabled
- **API errors**: Check that your `XAI_API_KEY` is set correctly
- **TTS not working**: On macOS, you may need to allow Terminal/system access to speech features

### Raspberry Pi Specific

- **PyAudio errors**: Make sure `portaudio19-dev` is installed:
  ```bash
  sudo apt install portaudio19-dev
  ```

- **Audio device not found**: 
  - List devices: `arecord -l`
  - Set `INPUT_DEVICE_INDEX` in `.env` file
  - For WM8960 HAT, typically index is `1`

- **Slow transcription**: 
  - The script uses "tiny" model by default on Pi
  - If still slow, try closing other apps
  - Consider using a Pi 4 with 4GB+ RAM

- **Out of memory**: 
  - Use "tiny" Whisper model (default on Pi)
  - Close other applications
  - Consider adding swap space: `sudo dphys-swapfile swapoff && sudo dphys-swapfile swapon`

- **PyTorch installation fails**: 
  - Install from pip (CPU-only version is fine)
  - May take 10-20 minutes on Pi
  - Ensure you have enough disk space (2GB+ free)

## Performance Notes

- **Whisper models** (smaller = faster, less accurate):
  - `tiny`: Fastest, good for Pi (default on Pi)
  - `base`: Balanced (default on desktop)
  - `small`: Better accuracy, slower
  - `medium`/`large`: Best accuracy, very slow on Pi

- **Expected performance on Pi 4 (4GB)**:
  - Transcription: 2-5 seconds for 5-10 second audio
  - Total response time: 5-10 seconds (including API call)

