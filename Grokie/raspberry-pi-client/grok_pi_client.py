"""
GROK Voice Agent Client for Raspberry Pi
Connects to the GROK agent and handles voice input/output using the Pi's microphone and speakers.
Simplified to match web client approach.
"""

import asyncio
import os
import sys
import subprocess
import threading
import queue
from dotenv import load_dotenv
from livekit import rtc, api

# Load environment variables
load_dotenv()

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")
ROOM_NAME = os.getenv("LIVEKIT_ROOM", "test-room")
PARTICIPANT_NAME = os.getenv("PARTICIPANT_NAME", "raspberry-pi")


def generate_token(room_name: str, participant_name: str) -> str:
    """Generate LiveKit access token."""
    token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(participant_name) \
        .with_name("Raspberry Pi") \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
    
    return token.to_jwt()


def setup_audio_output():
    """Set up audio output similar to whisplay (find sound card and set volume)."""
    try:
        # Find the sound card index for wm8960soundcard (like whisplay does)
        result = subprocess.run(
            ["awk", "/wm8960soundcard/ {print $1}", "/proc/asound/cards"],
            capture_output=True,
            text=True
        )
        card_index = result.stdout.strip().split('\n')[0] if result.stdout.strip() else None
        
        # Default to 1 if not found
        if not card_index or not card_index.isdigit():
            card_index = "1"
        
        print(f"🔊 Using sound card index: {card_index}")
        
        # Set volume (similar to whisplay: amixer -c $card_index set Speaker 114)
        subprocess.run(
            ["amixer", "-c", card_index, "set", "Speaker", "114"],
            check=False,
            capture_output=True
        )
        print(f"✅ Audio volume set")
        
        return card_index
    except Exception as e:
        print(f"⚠️  Warning: Could not configure audio: {e}")
        print("   Audio may still work with default settings")
        return "1"


class ALSAAudioPlayer:
    """Plays audio frames through ALSA using aplay."""
    def __init__(self, sound_card_index="1", sample_rate=48000, channels=2):
        self.sound_card_index = sound_card_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.process = None
        self.running = False
        self.audio_queue = queue.Queue()
        self.worker_thread = None
        
    def start(self):
        """Start the audio player."""
        if self.running:
            return
            
        try:
            # Start aplay process
            cmd = [
                "aplay",
                "-f", "S16_LE",
                "-c", str(self.channels),
                "-r", str(self.sample_rate),
                "-D", f"hw:{self.sound_card_index},0",
                "-"  # Read from stdin
            ]
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            self.running = True
            
            # Start worker thread to write audio data
            self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
            self.worker_thread.start()
            
            print(f"✅ ALSA audio player started ({self.channels}ch, {self.sample_rate}Hz)")
            return True
        except Exception as e:
            print(f"❌ Failed to start ALSA audio player: {e}")
            return False
    
    def _audio_worker(self):
        """Worker thread that writes audio data to aplay."""
        while self.running:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                if self.process and self.process.stdin:
                    self.process.stdin.write(audio_data)
                    self.process.stdin.flush()
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    print(f"⚠️  Audio write error: {e}")
                break
    
    def write_frame(self, audio_frame):
        """Write an audio frame to the player."""
        if not self.running:
            return
            
        try:
            # Convert AudioFrame to bytes
            # AudioFrame has samples property that's a list of int16 values
            if hasattr(audio_frame, 'samples'):
                import numpy as np
                samples = np.array(audio_frame.samples, dtype=np.int16)
                audio_data = samples.tobytes()
                self.audio_queue.put(audio_data)
            elif hasattr(audio_frame, 'data'):
                self.audio_queue.put(audio_frame.data)
            else:
                # Try to get raw bytes
                audio_data = bytes(audio_frame)
                self.audio_queue.put(audio_data)
        except Exception as e:
            print(f"⚠️  Error processing audio frame: {e}")
    
    def stop(self):
        """Stop the audio player."""
        self.running = False
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None
        if self.worker_thread:
            self.worker_thread.join(timeout=1)


async def main():
    """Main function to connect and handle voice interaction."""
    print("🎤 GROK Voice Agent - Raspberry Pi Client")
    print("=" * 50)
    print(f"Connecting to: {LIVEKIT_URL}")
    print(f"Room: {ROOM_NAME}")
    print("=" * 50)
    
    # Set up audio output (like whisplay does)
    card_index = setup_audio_output()
    
    # Set ALSA environment variables
    os.environ['ALSA_CARD'] = card_index
    os.environ['ALSA_PCM_DEVICE'] = "0"
    
    # Create audio player for ALSA playback
    audio_player = ALSAAudioPlayer(sound_card_index=card_index, sample_rate=48000, channels=2)
    
    # Generate access token
    print("\nGenerating access token...")
    token = generate_token(ROOM_NAME, PARTICIPANT_NAME)
    
    # Create room
    room = rtc.Room()
    
    # Set up event handlers (simplified like web client)
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
        print(f"   Participant SID: {participant.sid}")
    
    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        # Handle audio tracks - Python SDK doesn't have attach(), need to handle frames
        if track.kind == rtc.TrackKind.KIND_AUDIO and isinstance(track, rtc.RemoteAudioTrack):
            print(f"\n🔊 Audio track received from {participant.identity}")
            print(f"   Track: {track.name}")
            
            # Start ALSA audio player
            if not audio_player.running:
                if audio_player.start():
                    print(f"✅ ALSA audio player ready")
                else:
                    print(f"❌ Failed to start audio player")
                    return
            
            # Set up frame handler to capture and play audio
            # The Python SDK uses a different API than the browser SDK
            print(f"   Checking available track methods...")
            track_methods = [m for m in dir(track) if not m.startswith('_') and 'frame' in m.lower()]
            print(f"   Frame-related methods: {track_methods}")
            
            # Try to set up frame handling
            frame_handler_set = False
            
            # Method 1: Check if track has add_sink or similar
            if hasattr(track, 'add_sink'):
                try:
                    def audio_sink(frame: rtc.AudioFrame):
                        audio_player.write_frame(frame)
                    track.add_sink(audio_sink)
                    frame_handler_set = True
                    print(f"✅ Audio sink added via add_sink()")
                except Exception as e:
                    print(f"   add_sink failed: {e}")
            
            # Method 2: Try frame_received event
            if not frame_handler_set:
                try:
                    @track.on("frame_received")
                    def on_audio_frame(frame: rtc.AudioFrame):
                        audio_player.write_frame(frame)
                    frame_handler_set = True
                    print(f"✅ Frame handler registered (frame_received event)")
                except (AttributeError, TypeError) as e:
                    print(f"   frame_received event not available: {e}")
            
            # Method 3: Try accessing stream directly
            if not frame_handler_set:
                if hasattr(track, 'stream'):
                    print(f"   Track has stream attribute: {type(track.stream)}")
                if hasattr(track, 'media_stream_track'):
                    print(f"   Track has media_stream_track: {type(track.media_stream_track)}")
            
            if frame_handler_set:
                print(f"   🔊 Audio will play through ALSA when frames arrive")
            else:
                print(f"   ⚠️  Could not set up frame handler")
                print(f"   💡 Audio playback may not work - checking track API...")
                # Print all public methods for debugging
                all_methods = [m for m in dir(track) if not m.startswith('_')]
                print(f"   Available methods: {', '.join(all_methods[:10])}...")
    
    @room.on("data_received")
    def on_data_received(data: rtc.DataPacket, participant: rtc.RemoteParticipant, kind: rtc.DataPacketKind):
        """Handle data packets (may contain text/transcription)."""
        try:
            text = data.data.decode('utf-8')
            print(f"\n📝 Agent said: {text}")
        except Exception as e:
            print(f"📦 Data received (non-text): {len(data.data)} bytes")
    
    @room.on("track_published")
    def on_track_published(
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if publication.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"🎤 Microphone track published: {publication.track_name}")
    
    try:
        # Connect to room with auto-subscribe (like web client)
        print("Connecting to LiveKit server...")
        await room.connect(
            LIVEKIT_URL, 
            token,
            options=rtc.RoomOptions(
                auto_subscribe=True,  # Automatically subscribe to all tracks
            )
        )
        
        # Create and publish microphone track (after connection, like web client)
        print("Setting up microphone...")
        try:
            # Use default microphone
            source = rtc.AudioSource(24000, 1)  # 24kHz, mono
            track = rtc.LocalAudioTrack.create_audio_track("microphone", source)
            await room.local_participant.publish_track(track, rtc.TrackPublishOptions())
            print("✅ Microphone ready!")
        except Exception as e:
            print(f"⚠️  Warning: Could not set up microphone: {e}")
            print("   Audio input may not work, but you can still receive audio.")
            import traceback
            traceback.print_exc()
        
        # Keep running until interrupted
        print("\n" + "=" * 50)
        print("🎤 Ready! Speak into the microphone.")
        print("=" * 50)
        print("\n💡 The agent should respond when you speak.")
        print("   Watch for 'Agent said:' messages to see text responses.\n")
        
        # Run forever until interrupted
        await asyncio.sleep(3600 * 24)  # Run for 24 hours (or until Ctrl+C)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        audio_player.stop()
        await room.disconnect()
        print("👋 Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
