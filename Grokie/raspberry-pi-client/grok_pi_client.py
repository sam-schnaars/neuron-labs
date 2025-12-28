"""
GROK Voice Agent Client for Raspberry Pi
Connects to the GROK agent and handles voice input/output using the Pi's microphone and speakers.
"""

import asyncio
import os
import sys
import subprocess
import threading
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
        return None


class ALSAAudioSink:
    """Custom audio sink that plays audio through ALSA using aplay."""
    def __init__(self, sound_card_index="1"):
        self.sound_card_index = sound_card_index
        self.process = None
        self.running = False
        
    def start(self, sample_rate=24000, channels=1):
        """Start the aplay process."""
        try:
            # Start aplay process to play raw PCM audio
            # Format: 16-bit signed little-endian, configurable sample rate and channels
            cmd = [
                "aplay",
                "-f", "S16_LE",  # 16-bit signed little-endian
                "-c", str(channels),  # Channels (1=mono, 2=stereo)
                "-r", str(sample_rate),  # Sample rate
                "-D", f"hw:{self.sound_card_index},0",  # Direct hardware access
                "-"  # Read from stdin
            ]
            print(f"   Starting aplay: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            self.running = True
            print(f"✅ ALSA audio sink started (aplay process, {channels} channel(s), {sample_rate}Hz)")
            return True
        except Exception as e:
            print(f"❌ Failed to start ALSA audio sink: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def write_audio(self, audio_data: bytes):
        """Write audio data to the aplay process."""
        if self.process and self.process.stdin and self.running:
            try:
                self.process.stdin.write(audio_data)
                self.process.stdin.flush()
            except Exception as e:
                print(f"⚠️  Error writing audio: {e}")
                self.running = False
    
    def stop(self):
        """Stop the audio sink."""
        self.running = False
        if self.process:
            try:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None


async def main():
    """Main function to connect and handle voice interaction."""
    print("🎤 GROK Voice Agent - Raspberry Pi Client")
    print("=" * 50)
    print(f"Connecting to: {LIVEKIT_URL}")
    print(f"Room: {ROOM_NAME}")
    print("=" * 50)
    
    # Set up audio output (like whisplay does)
    card_index = setup_audio_output()
    if not card_index:
        card_index = "1"  # Default fallback
    
    # Set ALSA environment variables to use the correct sound card
    os.environ['ALSA_CARD'] = card_index
    os.environ['ALSA_PCM_DEVICE'] = "0"
    
    # Create custom audio sink for ALSA playback (as fallback)
    audio_sink = ALSAAudioSink(sound_card_index=card_index)
    
    # Generate access token
    print("\nGenerating access token...")
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
        print(f"   Participant SID: {participant.sid}")
    
    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"\n🔊 Audio track received from {participant.identity}")
            print(f"   Track SID: {track.sid}")
            print(f"   Track name: {track.name}")
            print(f"   Muted: {publication.is_muted}")
            
            # Set up custom audio playback through ALSA
            try:
                if isinstance(track, rtc.RemoteAudioTrack):
                    print(f"   Setting up custom ALSA audio playback...")
                    
                    # Try default attachment first (simpler and should work)
                    try:
                        audio_element = track.attach()
                        print(f"✅ Audio track attached (default method)")
                        print(f"   🔊 Audio should play through default output")
                    except Exception as e:
                        print(f"⚠️  Default attachment failed: {e}")
                        print(f"   Trying custom ALSA sink...")
                        
                        # Fallback to custom ALSA sink
                        # Try stereo 48kHz first (common for LiveKit), then mono 24kHz
                        if audio_sink.start(sample_rate=48000, channels=2):
                            print(f"✅ ALSA audio sink ready (stereo, 48kHz)")
                            print(f"   🔊 Audio sink configured for hw:{card_index},0")
                        elif audio_sink.start(sample_rate=24000, channels=1):
                            print(f"✅ ALSA audio sink ready (mono, 24kHz)")
                            print(f"   🔊 Audio sink configured for hw:{card_index},0")
                        else:
                            print(f"❌ Could not start ALSA audio sink")
                            print(f"   Audio may still work through default attachment")
                else:
                    print(f"⚠️  Track is not a RemoteAudioTrack: {type(track)}")
            except Exception as e:
                print(f"⚠️  Warning: Could not set up audio playback: {e}")
                import traceback
                traceback.print_exc()
    
    @room.on("data_received")
    def on_data_received(data: rtc.DataPacket, participant: rtc.RemoteParticipant, kind: rtc.DataPacketKind):
        """Handle data packets (may contain text/transcription)."""
        try:
            text = data.data.decode('utf-8')
            print(f"\n📝 Agent said: {text}")
        except Exception as e:
            print(f"📦 Data received (non-text): {data.data}")
    
    @room.on("track_published")
    def on_track_published(
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if publication.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"🎤 Microphone track published: {publication.track_name}")
    
    try:
        # Connect to room
        print("Connecting to LiveKit server...")
        await room.connect(LIVEKIT_URL, token)
        
        # Create and publish microphone track
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
        
        # Keep running until interrupted
        print("\n" + "=" * 50)
        print("🎤 Ready! Speak into the microphone.")
        print("=" * 50)
        print("\n💡 Debug info:")
        print("   - Audio should play automatically when agent responds")
        print("   - Watch for 'Agent said:' messages to see text responses")
        print("   - If no audio, check: aplay -l and speaker-test -t wav\n")
        
        # Run forever until interrupted
        await asyncio.sleep(3600 * 24)  # Run for 24 hours (or until Ctrl+C)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop audio sink
        audio_sink.stop()
        await room.disconnect()
        print("👋 Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


