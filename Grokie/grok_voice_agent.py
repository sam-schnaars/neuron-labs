"""
GROK Voice Agent API Integration
This script demonstrates how to use the GROK voice agent API through LiveKit Agents.
"""

import os
import asyncio
from dotenv import load_dotenv
from livekit.agents import AgentServer, AgentSession, Agent
from livekit.plugins import xai

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

server = AgentServer(
    ws_url=livekit_url,
    api_key=livekit_key,
    api_secret=livekit_secret,
)


@server.rtc_session()
async def request_handler(req):
    """
    Handle incoming real-time communication session requests.
    This function is called when a new voice session is initiated.
    """
    # Check if API key is set
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        raise ValueError(
            "XAI_API_KEY environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    
    print(f"\n🎤 New voice session started in room: {req.room.name}")
    
    # Initialize the session with Grok realtime model
    # You can customize the voice by passing voice parameter:
    # Available voices: 'Ara', 'Rex', 'Sal', 'Eve', 'Leo'
    session = AgentSession(
        llm=xai.realtime.RealtimeModel(
            # voice='Ara',  # Uncomment to specify a voice
        ),
    )
    
    # Start the session with the GrokAssistant agent
    await session.start(room=req.room, agent=GrokAssistant())
    
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
    
    print("Starting GROK Voice Agent Server...")
    print(f"LiveKit URL: {livekit_url}")
    print(f"LiveKit API Key: {livekit_key}")
    print("Make sure your LiveKit server is running!")
    print("For local dev: run 'livekit-server --dev' in another terminal")
    print("Server is ready to accept connections...\n")
    
    # Run the agent server (it's async, so we await it)
    await server.run(devmode=True)


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

