import pyaudio
import numpy as np
import threading
import queue
from silero_vad import load_silero_vad
from pyttsx3 import init as init_tts
import torch
import os
import whisper
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Detect if running on Raspberry Pi
def is_raspberry_pi():
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except:
        return False

# Choose Whisper model based on device
# On Pi, use smaller model for better performance
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny" if is_raspberry_pi() else "base")

# Setup
import time

print("Loading models...")
print(f"Using Whisper model: {WHISPER_MODEL}")
print("⚠️  NOTE: Model loading is CPU/RAM intensive. Ensure adequate power supply!")
print("")

# Load models gradually to reduce power spikes
print("⏳ Loading Silero VAD model...")
vad_model = load_silero_vad()
print("✅ VAD model loaded")
time.sleep(1)  # Brief pause to let system stabilize

print("⏳ Loading Whisper model into memory...")
print("   This may take 30-60 seconds on Pi and uses significant power.")
print("   If Pi shuts down, check power supply and cooling!")
whisper_model = whisper.load_model(WHISPER_MODEL)
print("✅ Whisper model loaded")
time.sleep(1)  # Brief pause

print("⏳ Initializing TTS engine...")
tts_engine = init_tts()
tts_engine.setProperty('rate', 150)
tts_engine.setProperty('volume', 0.8)
print("✅ TTS engine ready")
print("✅ All models loaded! Starting voice agent...\n")

audio_queue = queue.Queue()

def record_audio():
    """Record audio from microphone and add to queue"""
    p = pyaudio.PyAudio()
    try:
        # On Pi, you might need to specify device index
        # Set INPUT_DEVICE_INDEX in .env if needed (e.g., for WM8960 HAT)
        input_device_index = None
        device_index_str = os.getenv("INPUT_DEVICE_INDEX")
        if device_index_str:
            try:
                input_device_index = int(device_index_str)
                print(f"Using audio input device index: {input_device_index}")
            except ValueError:
                pass
        
        stream = p.open(
            format=pyaudio.paInt16,  # Use Int16 instead of Float32
            channels=1,
            rate=16000,
            input=True,
            input_device_index=input_device_index,
            frames_per_buffer=512
        )
        
        while True:
            chunk = stream.read(512, exception_on_overflow=False)
            # Convert bytes to numpy array
            audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
            audio_queue.put(audio_data)
    except Exception as e:
        print(f"Error in audio recording: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

def speak(text):
    """Speak text using TTS"""
    try:
        # Clean up text and split into sentences
        text = text.strip()
        if not text:
            return
        
        # Split by sentence endings but keep them
        sentences = []
        current = ""
        for char in text:
            current += char
            if char in '.!?':
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())
        
        for sentence in sentences:
            if sentence.strip():
                tts_engine.say(sentence)
        tts_engine.runAndWait()
    except Exception as e:
        print(f"Error in TTS: {e}")

def get_grok_response(transcript, api_key):
    """Get response from Grok API"""
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "grok-3",
        "messages": [
            {
                "role": "system",
                "content": "You are Grokie a handheld pocket tutor. Respond in two sentences or less unless explicitly asked to expand on a topic."
            },
            {
                "role": "user",
                "content": transcript
            }
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"Error calling Grok API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None

def main():
    # Get API key from environment
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        print("Error: XAI_API_KEY environment variable is not set.")
        print("Please set it in your .env file or environment:")
        print("  export XAI_API_KEY=your_api_key_here")
        return
    
    print("Starting voice agent...")
    print("Press Ctrl+C to exit\n")
    
    # Start audio recording thread
    audio_thread = threading.Thread(target=record_audio, daemon=True)
    audio_thread.start()
    
    # Give audio system a moment to initialize
    import time
    time.sleep(0.5)
    
    try:
        while True:
            print("🎤 Listening... (speak now)")
            recorded_chunks = []
            silence_count = 0
            max_silence = 15  # Increased for better detection
            
            while silence_count < max_silence:
                try:
                    chunk = audio_queue.get(timeout=0.5)
                    recorded_chunks.append(chunk)
                    
                    # Check for voice activity
                    chunk_tensor = torch.from_numpy(chunk).unsqueeze(0)
                    confidence = vad_model(chunk_tensor, 16000).item()
                    
                    if confidence > 0.5:
                        silence_count = 0
                    else:
                        silence_count += 1
                except queue.Empty:
                    silence_count += 1
            
            if len(recorded_chunks) < 10:  # Too short, probably noise
                print("⚠️  Audio too short, ignoring...\n")
                continue
            
            print("📝 Transcribing...")
            audio_data = np.concatenate(recorded_chunks)
            
            # Ensure audio is in the right format for whisper
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Normalize if needed
            if np.abs(audio_data).max() > 1.0:
                audio_data = audio_data / np.abs(audio_data).max()
            
            try:
                # On Pi, use faster inference settings
                transcribe_options = {
                    "language": "en",
                    "fp16": False,  # Disable FP16 on Pi (may not be supported)
                    "verbose": False
                }
                if is_raspberry_pi():
                    # Use CPU-optimized settings for Pi
                    transcribe_options["fp16"] = False
                
                result = whisper_model.transcribe(audio_data, **transcribe_options)
                transcript = result['text'].strip()
                
                if not transcript or len(transcript) < 2:
                    print("⚠️  No speech detected, try again...\n")
                    continue
                
                print(f"👤 You: {transcript}\n")
                
                print("🤔 Getting response from Grok...")
                reply = get_grok_response(transcript, api_key)
                
                if reply:
                    print(f"🤖 Grok: {reply}\n")
                    speak(reply)
                else:
                    print("❌ Failed to get response from Grok\n")
                
                print("-" * 50 + "\n")
                
            except Exception as e:
                print(f"❌ Error during transcription: {e}\n")
                continue
                
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()