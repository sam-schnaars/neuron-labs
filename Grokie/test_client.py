"""
Simple test client to connect to the GROK voice agent.
This requires a LiveKit server to be running.
"""

import asyncio
import os
from dotenv import load_dotenv
from livekit import rtc
from livekit import api

# Load environment variables
load_dotenv()


async def connect_to_agent():
    """
    Connect to the LiveKit room where the agent is running.
    """
    # Get LiveKit credentials from environment or use defaults for local dev
    url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    api_key = os.getenv("LIVEKIT_API_KEY", "devkey")
    api_secret = os.getenv("LIVEKIT_API_SECRET", "secret")
    room_name = os.getenv("LIVEKIT_ROOM", "test-room")
    
    print(f"Connecting to LiveKit server at {url}...")
    print(f"Room: {room_name}")
    
    # Create access token
    token = api.AccessToken(api_key, api_secret) \
        .with_identity("user-123") \
        .with_name("Test User") \
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    
    # Connect to room
    room = rtc.Room()
    
    @room.on("connected")
    def on_connected():
        print("✅ Connected to room! The agent should greet you shortly.")
        print("You can now speak to the GROK agent.")
    
    @room.on("disconnected")
    def on_disconnected():
        print("❌ Disconnected from room")
    
    @room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        print(f"👤 Participant connected: {participant.identity}")
    
    try:
        await room.connect(url, token.to_jwt())
        print("\n🎤 Connection established! Start speaking...")
        print("Press Ctrl+C to disconnect\n")
        
        # Keep connection alive
        await asyncio.sleep(3600)  # Run for 1 hour
    except KeyboardInterrupt:
        print("\n\nDisconnecting...")
    except Exception as e:
        print(f"❌ Error connecting: {e}")
        print("\nMake sure:")
        print("1. LiveKit server is running (e.g., 'livekit-server --dev')")
        print("2. Your agent script is running")
        print("3. Environment variables are set correctly")
    finally:
        await room.disconnect()


if __name__ == "__main__":
    asyncio.run(connect_to_agent())

