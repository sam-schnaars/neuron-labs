"""
GROK Voice Agent Client for Raspberry Pi
Connects to the GROK agent and handles voice input/output using the Pi's microphone and speakers.
"""

import asyncio
import os
import sys
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
    
    @room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.TrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print(f"🔊 Audio track received from {participant.identity}")
            # Audio will play automatically through the default audio output
    
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


