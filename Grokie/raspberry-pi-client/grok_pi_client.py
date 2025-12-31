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
    
    # Create MediaDevices for audio output (the proper way in Python SDK)
    devices = rtc.MediaDevices()
    
    # Try to open audio output device
    audio_player = None
    try:
        print("Setting up audio output device...")
        audio_player = devices.open_output()
        print("✅ Audio output device opened")
    except Exception as e:
        print(f"⚠️  Could not open audio output device: {e}")
        print("   Will try to use ALSA directly as fallback")
        audio_player = None
    
    # Fallback: Create ALSA audio player if MediaDevices failed
    alsa_player = None
    if audio_player is None:
        alsa_player = ALSAAudioPlayer(sound_card_index=card_index, sample_rate=48000, channels=2)
    
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
    
    # Track if audio player has been started
    audio_player_started = False
    
    async def start_audio_player_if_needed():
        """Async helper to start audio player."""
        nonlocal audio_player_started
        if not audio_player_started and audio_player is not None:
            try:
                if hasattr(audio_player, 'start'):
                    if asyncio.iscoroutinefunction(audio_player.start):
                        await audio_player.start()
                    else:
                        audio_player.start()
                audio_player_started = True
                print(f"✅ Audio playback started")
            except Exception as e:
                print(f"⚠️  Error starting player: {e}")
                import traceback
                traceback.print_exc()
    
    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        nonlocal audio_player_started  # Declare as nonlocal since we may assign to it
        
        # Handle audio tracks - Use MediaDevices player (proper Python SDK way)
        if track.kind == rtc.TrackKind.KIND_AUDIO and isinstance(track, rtc.RemoteAudioTrack):
            print(f"\n🔊 Audio track received from {participant.identity}")
            print(f"   Track: {track.name}")
            
            # Use MediaDevices player if available (preferred method)
            if audio_player is not None:
                try:
                    audio_player.add_track(track)
                    print(f"✅ Audio track added to MediaDevices player")
                    
                    # Start playback if not already started (use create_task for async)
                    if not audio_player_started:
                        try:
                            # Get the running event loop
                            loop = asyncio.get_running_loop()
                            loop.create_task(start_audio_player_if_needed())
                        except RuntimeError:
                            # Fallback: try to get any event loop
                            try:
                                loop = asyncio.get_event_loop()
                                if loop.is_running():
                                    loop.create_task(start_audio_player_if_needed())
                                else:
                                    # If loop exists but not running, schedule it
                                    asyncio.run(start_audio_player_if_needed())
                            except Exception as e:
                                print(f"⚠️  Could not start audio player asynchronously: {e}")
                                # Try synchronous start as fallback
                                try:
                                    if hasattr(audio_player, 'start') and not asyncio.iscoroutinefunction(audio_player.start):
                                        audio_player.start()
                                        audio_player_started = True
                                        print(f"✅ Audio playback started (synchronous)")
                                except Exception as e2:
                                    print(f"⚠️  Synchronous start also failed: {e2}")
                    else:
                        print(f"✅ Audio playback already active")
                    print(f"   🔊 Audio should play through default output device")
                except Exception as e:
                    print(f"⚠️  Error adding track to player: {e}")
                    import traceback
                    traceback.print_exc()
            elif alsa_player is not None:
                # Fallback to ALSA player - start it and subscribe to frames
                print(f"   ⚠️  MediaDevices not available, using ALSA fallback")
                try:
                    # Start the ALSA player
                    if not alsa_player.running:
                        alsa_player.start()
                        print(f"✅ ALSA audio player started")
                    
                    # Subscribe to audio frames from the track
                    def on_audio_frame(frame: rtc.AudioFrame):
                        """Callback to handle audio frames from the track."""
                        try:
                            alsa_player.write_frame(frame)
                        except Exception as e:
                            # Silently handle errors to avoid spam
                            pass
                    
                    # Register frame callback
                    # LiveKit Python SDK uses "frame" event for RemoteAudioTrack
                    try:
                        track.on("frame", on_audio_frame)
                        print(f"✅ Audio frame subscription set up for ALSA player")
                        print(f"   🔊 Audio should play through ALSA device")
                    except AttributeError:
                        # Try alternative method if "on" doesn't exist
                        try:
                            track.add_frame_listener(on_audio_frame)
                            print(f"✅ Audio frame subscription set up for ALSA player (listener)")
                            print(f"   🔊 Audio should play through ALSA device")
                        except AttributeError:
                            print(f"⚠️  Could not subscribe to audio frames - track doesn't support frame callbacks")
                            print(f"   Track type: {type(track)}")
                            print(f"   Available methods: {[m for m in dir(track) if not m.startswith('_')]}")
                    except Exception as frame_error:
                        print(f"⚠️  Error subscribing to audio frames: {frame_error}")
                        print(f"   Audio playback may not work with ALSA fallback")
                except Exception as e:
                    print(f"⚠️  Error setting up ALSA player: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"❌ No audio playback method available")
    
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
            # Use MediaDevices to capture from default microphone (like web client)
            # This automatically captures audio from the system microphone
            microphone_track = await devices.open_input()
            await room.local_participant.publish_track(microphone_track, rtc.TrackPublishOptions())
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
        # Clean up audio players
        if alsa_player:
            alsa_player.stop()
        if audio_player:
            try:
                await audio_player.aclose()
            except:
                pass
        await room.disconnect()
        print("👋 Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
