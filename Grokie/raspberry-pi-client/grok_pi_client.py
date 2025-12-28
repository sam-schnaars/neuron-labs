"""
GROK Voice Agent Client for Raspberry Pi
Connects to the GROK agent and handles voice input/output using the Pi's microphone and speakers.
Simplified to match web client approach.
"""

import asyncio
import os
import sys
import subprocess
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
        # Handle audio tracks (like web client does)
        if track.kind == rtc.TrackKind.KIND_AUDIO and isinstance(track, rtc.RemoteAudioTrack):
            print(f"\n🔊 Audio track received from {participant.identity}")
            print(f"   Track: {track.name}")
            
            # Simple approach: just attach the track (like web client)
            # The Python SDK should handle playback automatically
            try:
                audio_element = track.attach()
                print(f"✅ Audio track attached")
                print(f"   🔊 Audio should play automatically")
                print(f"   Audio element type: {type(audio_element)}")
            except Exception as e:
                print(f"❌ Failed to attach audio track: {e}")
                import traceback
                traceback.print_exc()
    
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
        await room.disconnect()
        print("👋 Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
