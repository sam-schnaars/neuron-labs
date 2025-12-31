#!/usr/bin/env python3
"""
Simple Deepgram TTS test script
Says "I like poop" using Deepgram's text-to-speech API
"""

import os
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ Error: requests library not installed")
    print("   Install with: pip install requests")
    sys.exit(1)

# Deepgram API configuration
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
if not DEEPGRAM_API_KEY:
    print("❌ Error: DEEPGRAM_API_KEY environment variable not set")
    print("   Set it with: export DEEPGRAM_API_KEY='your_api_key_here'")
    print("   Or add it to your .env file")
    sys.exit(1)

# Text to speak
TEXT = "I like poop"

# Deepgram TTS endpoint - model can be in URL or as query param
DEEPGRAM_TTS_BASE = "https://api.deepgram.com/v1/speak"

def say_text(text: str):
    """Use Deepgram TTS to convert text to speech and play it."""
    print(f"🎤 Saying: '{text}'")
    
    # Prepare request
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Deepgram TTS request payload - only text in body (as per API requirement)
    payload = {
        "text": text
    }
    
    # Model selection
    model = "aura-asteria-en"  # You can change this to other voices like "aura-luna-en", "aura-stella-en"
    
    # Query parameters for audio settings (model might need to be in URL)
    params = {
        "encoding": "linear16",
        "container": "wav",
        "sample_rate": 24000
    }
    
    # Try with model in URL path first
    url = f"{DEEPGRAM_TTS_BASE}/{model}"
    
    print("📡 Sending request to Deepgram...")
    print(f"   URL: {url}")
    print(f"   Params: {params}")
    print(f"   Body: {payload}")
    try:
        # Make API request - text in JSON body, model in URL, settings as query params
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            params=params,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Error: Deepgram API returned status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        # Save audio to temporary file
        audio_file = "/tmp/deepgram_tts.wav"
        with open(audio_file, "wb") as f:
            f.write(response.content)
        
        print(f"✅ Audio received, saved to {audio_file}")
        print("🔊 Playing audio...")
        
        # Play audio using aplay (Raspberry Pi default)
        # Try to find the correct sound card
        try:
            # Check for wm8960soundcard (common on Pi HATs)
            result = subprocess.run(
                ["awk", "/wm8960soundcard/ {print $1}", "/proc/asound/cards"],
                capture_output=True,
                text=True
            )
            card_index = result.stdout.strip().split('\n')[0] if result.stdout.strip() else None
            
            if card_index and card_index.isdigit():
                print(f"   Using sound card: {card_index}")
                subprocess.run(
                    ["aplay", "-D", f"hw:{card_index},0", audio_file],
                    check=True
                )
            else:
                # Use default audio device
                print("   Using default audio device")
                subprocess.run(["aplay", audio_file], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Error playing audio: {e}")
            print("   Audio file saved at:", audio_file)
            print("   You can play it manually with: aplay", audio_file)
            return False
        
        print("✅ Done!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error making request to Deepgram: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Deepgram TTS Test")
    print("=" * 50)
    print()
    
    success = say_text(TEXT)
    
    if success:
        print("\n✅ Successfully said:", TEXT)
    else:
        print("\n❌ Failed to say text")
        sys.exit(1)

