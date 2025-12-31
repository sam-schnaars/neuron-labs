"""
GROK Voice Agent API Integration
This script demonstrates how to use the GROK voice agent API through LiveKit Agents.
"""

import os
import asyncio
from dotenv import load_dotenv
from livekit.agents import AgentServer, AgentSession, Agent
from livekit.plugins import xai
from livekit import api, rtc

# Load environment variables from .env file
load_dotenv()

class GrokAssistant(Agent):
    """
    A voice AI assistant powered by xAI's Grok model.
    Customize the instructions to change the assistant's behavior.
    """
    
    def __init__(self, instructions: str = None) -> None:
        default_instructions = (
            "You are Grokie, a funny and quick-witted voice AI assistant. "
            "Always keep your responses short and punchy - just 1-2 sentences each time. "
            "Be humorous, clever, and get straight to the point."
        )
        super().__init__(
            instructions=instructions or default_instructions,
        )


# Initialize the agent server with LiveKit configuration
# Use environment variables or defaults for local development
livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
livekit_key = os.getenv("LIVEKIT_API_KEY", "devkey")
livekit_secret = os.getenv("LIVEKIT_API_SECRET", "secret")
room_name = os.getenv("LIVEKIT_ROOM", "test-room")

server = AgentServer(
    ws_url=livekit_url,
    api_key=livekit_key,
    api_secret=livekit_secret,
)

# Track active sessions to avoid duplicates
active_sessions = {}


async def start_agent_session(room: rtc.Room):
    """
    Start an agent session in a room.
    This is called when a client connects to trigger the agent to join.
    """
    # Check if API key is set
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError(
            "XAI_API_KEY environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    
    # Avoid duplicate sessions for the same room
    if room.name in active_sessions:
        print(f"⚠️  Agent session already active for room: {room.name}")
        return
    
    print(f"\n🎤 Client connected to room: {room.name}, starting agent session...")
    active_sessions[room.name] = True
    
    try:
        # Initialize the session with Grok realtime model
        # You can customize the voice by passing voice parameter:
        # Available voices: 'Ara', 'Rex', 'Sal', 'Eve', 'Leo'
        session = AgentSession(
            llm=xai.realtime.RealtimeModel(
                # voice='Ara',  # Uncomment to specify a voice
            ),
        )
        
        # Start the session with the GrokAssistant agent
        await session.start(room=room, agent=GrokAssistant())
        
        print("✅ Agent session started")
        print("   💡 Agent is ready to receive audio and respond")
        
        # Generate an initial greeting
        print("💬 Generating initial greeting...")
        try:
            await session.generate_reply(
                instructions="Greet the user as Grokie with a funny, quick-witted one-liner. Keep it to 1-2 sentences."
            )
            print("✅ Initial greeting sent")
        except Exception as e:
            print(f"⚠️  Error generating greeting: {e}")
            import traceback
            traceback.print_exc()
        
        # Log when user speaks (if available)
        print("   🎤 Listening for user input...")
        
        # Wait for session to end
        await session.aclose()
        
    except Exception as e:
        print(f"❌ Error in agent session: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Remove from active sessions when done
        if room.name in active_sessions:
            del active_sessions[room.name]
        print(f"👋 Agent session ended for room: {room.name}")


@server.rtc_session()
async def request_handler(req):
    """
    Handle incoming real-time communication session requests.
    This function is called when a new voice session is initiated.
    """
    await start_agent_session(req.room)


async def auto_join_room(room_name: str):
    """
    Automatically join a specific room and start an agent session.
    This is a simpler approach that connects directly to a known room.
    """
    # Skip if we already have an active session for this room
    if room_name in active_sessions:
        print(f"⚠️  Agent session already active for room: {room_name}")
        return
    
    print(f"🔗 Auto-joining room: {room_name}")
    
    try:
        # Create a room connection
        room = rtc.Room()
        
        # Generate token for agent to join
        token = api.AccessToken(livekit_key, livekit_secret) \
            .with_identity("grokie-agent") \
            .with_name("Grokie") \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            ))
        
        # Connect to the room
        await room.connect(livekit_url, token.to_jwt())
        print(f"✅ Agent connected to room: {room_name}")
        print(f"   Waiting for clients to join...")
        
        # Monitor for participants joining
        @room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            if participant.identity != "grokie-agent":
                print(f"👤 Client '{participant.identity}' joined room: {room_name}")
        
        # Start agent session in background (non-blocking)
        asyncio.create_task(start_agent_session(room))
        
    except Exception as e:
        print(f"❌ Error auto-joining room {room_name}: {e}")
        import traceback
        traceback.print_exc()
        if room_name in active_sessions:
            del active_sessions[room_name]


async def main():
    """
    Main entry point for the voice agent server.
    """
    # Check if API key is set
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError(
            "XAI_API_KEY environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    
    # Get LiveKit configuration
    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    livekit_key = os.getenv("LIVEKIT_API_KEY", "devkey")
    livekit_secret = os.getenv("LIVEKIT_API_SECRET", "secret")
    default_room = os.getenv("LIVEKIT_ROOM", "test-room")
    
    print("Starting GROK Voice Agent Server...")
    print(f"LiveKit URL: {livekit_url}")
    print(f"LiveKit API Key: {livekit_key}")
    print(f"Default room: {default_room}")
    print("Make sure your LiveKit server is running!")
    print("For local dev: run 'livekit-server --dev' in another terminal")
    print("\n💡 The agent will auto-join the room when clients connect.")
    print("   You can also use the @server.rtc_session() handler for explicit requests.\n")
    
    # Start auto-join task in background (connects to default room)
    auto_join_task = asyncio.create_task(auto_join_room(default_room))
    
    try:
        # Run the agent server (it's async, so we await it)
        await server.run(devmode=True)
    finally:
        # Cancel auto-join when server stops
        auto_join_task.cancel()
        try:
            await auto_join_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    # Check if running in console mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "console":
        # Use LiveKit CLI console mode for easy voice interaction
        from livekit.agents import cli
        cli_app = cli._build_cli(server)
        cli_app()
    else:
        # Run as regular server
        asyncio.run(main())

