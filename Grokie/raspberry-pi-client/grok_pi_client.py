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
    process = None
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
        
        # Read stderr in background to catch errors
        async def read_stderr():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_str = line.decode().strip()
                if line_str and ('error' in line_str.lower() or 'Error' in line_str):
                    print(f"sox stderr: {line_str}")
        
        stderr_task = asyncio.create_task(read_stderr())
        
        # Read audio in chunks and feed to source
        # 100ms chunks: sample_rate * channels * bytes_per_sample * 0.1
        chunk_size = SAMPLE_RATE * CHANNELS * 2 // 10  # ~100ms of audio
        
        frame_count = 0
        while True:
            try:
                # Read with shorter timeout to avoid blocking
                chunk = await asyncio.wait_for(process.stdout.read(chunk_size), timeout=0.5)
                if not chunk:
                    print("sox process ended (no more data)")
                    break
                
                # Convert bytes to audio frame
                try:
                    # Convert bytes to numpy array of int16 samples
                    audio_data = np.frombuffer(chunk, dtype=np.int16)
                    # Convert to float32 in range [-1.0, 1.0]
                    audio_float = audio_data.astype(np.float32) / 32768.0
                    
                    # For stereo, reshape to (samples, channels)
                    if CHANNELS == 2:
                        audio_float = audio_float.reshape(-1, 2)
                    
                    # Feed to source - try different method names
                    if hasattr(source, 'capture_frame'):
                        source.capture_frame(audio_float)
                    elif hasattr(source, 'push_frame'):
                        source.push_frame(audio_float)
                    elif hasattr(source, 'add_frame'):
                        source.add_frame(audio_float)
                    else:
                        print(f"⚠️  AudioSource has no frame feeding method. Available: {dir(source)}")
                        break
                    
                    frame_count += 1
                    if frame_count % 100 == 0:  # Log every 10 seconds
                        print(f"Captured {frame_count} audio frames...")
                    
                except Exception as e:
                    print(f"Error feeding audio frame: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue trying
                    continue
                    
            except asyncio.TimeoutError:
                # Timeout is OK - sox might be waiting for audio
                # Check if process is still alive
                if process.returncode is not None:
                    print(f"sox process exited with code {process.returncode}")
                    break
                # Otherwise continue waiting
                continue
            except Exception as e:
                print(f"Error reading audio: {e}")
                break
                
    except Exception as e:
        print(f"Error in audio capture: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if process:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except:
                process.kill()
                await process.wait()


async def setup_audio_output(track: rtc.Track):
    """Set up audio output to WM8960 speakers by extracting frames and playing via aplay."""
    global audio_output_process
    
    try:
        print("Setting up audio output to WM8960...")
        
        # Start aplay process for raw PCM playback
        aplay_cmd = [
            "aplay",
            "-f", "S16_LE",
            "-c", "1",  # Mono output (LiveKit sends mono)
            "-r", str(SAMPLE_RATE),
            "-D", f"hw:{SOUND_CARD_INDEX},0",
            "-"  # stdin
        ]
        
        print(f"Starting aplay: {' '.join(aplay_cmd)}")
        audio_output_process = await asyncio.create_subprocess_exec(
            *aplay_cmd,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Set up frame handler to extract audio and play
        async def handle_audio_frame(frame: rtc.AudioFrame):
            try:
                # Convert frame to bytes for aplay
                # Frame is likely float32, need to convert to int16
                if hasattr(frame, 'data'):
                    audio_data = frame.data
                elif hasattr(frame, 'samples'):
                    audio_data = frame.samples
                else:
                    # Try to get raw data
                    audio_data = np.array(frame, dtype=np.float32)
                
                # Convert float32 [-1.0, 1.0] to int16
                audio_int16 = (audio_data * 32767).astype(np.int16)
                # Convert to bytes (little-endian)
                audio_bytes = audio_int16.tobytes()
                
                # Write to aplay
                if audio_output_process and audio_output_process.stdin:
                    audio_output_process.stdin.write(audio_bytes)
                    await audio_output_process.stdin.drain()
            except Exception as e:
                print(f"Error playing audio frame: {e}")
        
        # Try to subscribe to audio frames
        if hasattr(track, 'on_frame'):
            track.on_frame(handle_audio_frame)
            print("✅ Audio frame handler set up")
        elif hasattr(track, 'add_sink'):
            # Some versions use sink pattern
            track.add_sink(handle_audio_frame)
            print("✅ Audio sink added")
        else:
            print(f"⚠️  Track doesn't support frame extraction. Available methods: {[m for m in dir(track) if not m.startswith('_')]}")
            print("   Audio output may not work - LiveKit Python SDK may need different approach")
            
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
    async def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"🔊 Audio track received from {participant.identity}")
            # Set up audio playback through WM8960
            await setup_audio_output(track)
    
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


