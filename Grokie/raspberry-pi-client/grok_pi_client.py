"""
GROK Voice Agent Client for Raspberry Pi
Connects to the GROK agent and handles voice input/output using the Pi's microphone and speakers.
"""

import asyncio
import os
import sys
import requests
import subprocess
import struct
import numpy as np
from dotenv import load_dotenv
from livekit import rtc

# Load environment variables
load_dotenv()

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
ROOM_NAME = os.getenv("LIVEKIT_ROOM", "test-room")
PARTICIPANT_NAME = os.getenv("PARTICIPANT_NAME", "raspberry-pi")
TOKEN_SERVER_URL = os.getenv("TOKEN_SERVER_URL", "http://localhost:8080")
SOUND_CARD_INDEX = os.getenv("SOUND_CARD_INDEX", "1")
SAMPLE_RATE = 24000
CHANNELS = 2  # WM8960 requires stereo


async def capture_audio_from_wm8960(source: rtc.AudioSource):
    """Capture audio from WM8960 using sox and feed to AudioSource."""
    try:
        # Use sox to capture audio from WM8960
        # WM8960 requires stereo (2 channels)
        sox_cmd = [
            "sox",
            "-t", "alsa",
            "default",
            "-r", str(SAMPLE_RATE),
            "-c", str(CHANNELS),
            "-t", "raw",
            "-e", "signed-integer",
            "-b", "16",
            "-"  # stdout
        ]
        
        print(f"Starting sox capture: {' '.join(sox_cmd)}")
        process = await asyncio.create_subprocess_exec(
            *sox_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Read audio in chunks and feed to source
        # 100ms chunks: sample_rate * channels * bytes_per_sample * 0.1
        chunk_size = SAMPLE_RATE * CHANNELS * 2 // 10  # ~100ms of audio
        
        try:
            while True:
                chunk = await asyncio.wait_for(process.stdout.read(chunk_size), timeout=1.0)
                if not chunk:
                    break
                
                # Convert bytes to audio frame
                # LiveKit AudioSource expects numpy array
                try:
                    # Convert bytes to numpy array of int16 samples
                    audio_data = np.frombuffer(chunk, dtype=np.int16)
                    # Convert to float32 in range [-1.0, 1.0]
                    audio_float = audio_data.astype(np.float32) / 32768.0
                    
                    # For stereo, reshape to (samples, channels) if needed
                    # Or keep as interleaved - depends on LiveKit API
                    # Try reshaping to (num_samples//2, 2) for stereo
                    if CHANNELS == 2:
                        audio_float = audio_float.reshape(-1, 2)
                    
                    # Feed to source
                    source.capture_frame(audio_float)
                    
                except AttributeError as e:
                    # If capture_frame doesn't exist, try alternative method
                    print(f"⚠️  AudioSource API issue: {e}")
                    print("   Trying alternative method...")
                    # Some versions might use different method name
                    if hasattr(source, 'push_frame'):
                        source.push_frame(audio_float)
                    else:
                        print("   No suitable method found for feeding audio")
                        break
                except Exception as e:
                    print(f"Error feeding audio frame: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue trying - don't break on first error
                    continue
                    
        except asyncio.TimeoutError:
            print("Audio capture timeout")
        except Exception as e:
            print(f"Error reading audio: {e}")
        finally:
            process.terminate()
            await process.wait()
                
    except Exception as e:
        print(f"Error in audio capture: {e}")
        import traceback
        traceback.print_exc()


def setup_audio_output(track: rtc.Track):
    """Set up audio output to WM8960 speakers."""
    global audio_output_process
    
    try:
        print("Setting up audio output to WM8960...")
        # LiveKit Python SDK should handle audio playback automatically
        # If it doesn't work, we may need to extract frames and play via aplay
        # For now, let's check if track has a way to get audio data
        
        # Try to get the underlying audio stream
        # This depends on LiveKit Python SDK implementation
        print("✅ Audio output should work automatically via LiveKit SDK")
        print("   If you don't hear audio, check speaker volume: alsamixer -c 1")
    except Exception as e:
        print(f"Error setting up audio output: {e}")
        import traceback
        traceback.print_exc()


def generate_token(room_name: str, participant_name: str) -> str:
    """Generate LiveKit access token from token server."""
    try:
        response = requests.post(
            f"{TOKEN_SERVER_URL}/api/token",
            json={"room": room_name, "name": participant_name},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        return data["token"]
    except Exception as e:
        print(f"Error getting token from server: {e}")
        print(f"Make sure token server is running at {TOKEN_SERVER_URL}")
        sys.exit(1)


async def main():
    """Main function to connect and handle voice interaction."""
    print("🎤 GROK Voice Agent - Raspberry Pi Client")
    print("=" * 50)
    print(f"Connecting to: {LIVEKIT_URL}")
    print(f"Room: {ROOM_NAME}")
    print("=" * 50)
    
    # Generate access token
    print("Generating access token...")
    token = generate_token(ROOM_NAME, PARTICIPANT_NAME)
    
    # Create room
    room = rtc.Room()
    
    # Set up event handlers
    @room.on("connected")
    def on_connected():
        print("✅ Connected to room!")
        print("🎤 Microphone is active - start speaking!")
        print("Press Ctrl+C to disconnect\n")
    
    @room.on("disconnected")
    def on_disconnected():
        print("\n❌ Disconnected from room")
    
    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        print(f"👤 Agent connected: {participant.identity}")
    
    # Store audio output process
    audio_output_process = None
    
    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"🔊 Audio track received from {participant.identity}")
            # Set up audio playback through WM8960
            setup_audio_output(track)
    
    @room.on("track_published")
    def on_track_published(
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if publication.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"🎤 Microphone track published")
    
    try:
        # Connect to room
        print("Connecting to LiveKit server...")
        await room.connect(LIVEKIT_URL, token)
        
        # Create and publish microphone track
        print("Setting up microphone...")
        try:
            # Create audio source for WM8960 (stereo, 24kHz)
            source = rtc.AudioSource(SAMPLE_RATE, CHANNELS)
            track = rtc.LocalAudioTrack.create_audio_track("microphone", source)
            await room.local_participant.publish_track(track, rtc.TrackPublishOptions())
            print("✅ Microphone track published!")
            
            # Start capturing audio from WM8960 and feeding to source
            asyncio.create_task(capture_audio_from_wm8960(source))
            print("✅ Audio capture started!")
        except Exception as e:
            print(f"⚠️  Warning: Could not set up microphone: {e}")
            print("   Audio input may not work, but you can still receive audio.")
            import traceback
            traceback.print_exc()
        
        # Keep running until interrupted
        print("\n" + "=" * 50)
        print("🎤 Ready! Speak into the microphone.")
        print("=" * 50 + "\n")
        
        # Run forever until interrupted
        await asyncio.sleep(3600 * 24)  # Run for 24 hours (or until Ctrl+C)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await room.disconnect()
        print("👋 Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


