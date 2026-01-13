"""
GROK Voice Agent API Integration
This script demonstrates how to use the GROK voice agent API through LiveKit Agents.
"""

import os
import re
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
from livekit.agents import AgentServer, AgentSession, Agent
from livekit.agents import function_tool
from livekit.plugins import xai

# Load environment variables from .env file
load_dotenv()


class MultiFileMarkdownMemory:
    """Manages three Markdown files: conversation history, lesson plan, and custom notes"""
    
    def __init__(self, room_name: str, user_name: str):
        self.room_name = room_name
        self.user_name = user_name
        self.memory_dir = Path("conversation_memory") / room_name / user_name
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Three separate Markdown files
        self.conversation_file = self.memory_dir / "conversation_history.md"
        self.lesson_plan_file = self.memory_dir / "lesson_plan.md"
        self.custom_notes_file = self.memory_dir / "custom_notes.md"
        
        self.messages = []
        self.load_all()
    
    def load_all(self):
        """Load all three files"""
        self._init_conversation_file()
        self._init_lesson_plan_file()
        self._init_custom_notes_file()
        self._load_conversation_history()
    
    # ========== CONVERSATION HISTORY ==========
    
    def _init_conversation_file(self):
        """Initialize conversation history file"""
        if not self.conversation_file.exists():
            header = f"""# Conversation History

**Room:** {self.room_name}  
**User:** {self.user_name}  
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Messages

"""
            self.conversation_file.write_text(header, encoding='utf-8')
    
    def _load_conversation_history(self):
        """Load conversation messages from Markdown"""
        if self.conversation_file.exists():
            try:
                content = self.conversation_file.read_text(encoding='utf-8')
                self.messages = self._parse_conversation_markdown(content)
                print(f"📂 Loaded {len(self.messages)} messages from conversation history")
            except Exception as e:
                print(f"❌ Error loading conversation: {e}")
                self.messages = []
    
    def _parse_conversation_markdown(self, content: str) -> List[Dict]:
        """Parse conversation Markdown to extract messages"""
        messages = []
        # Match: ### User: or ### Assistant: followed by content and timestamp
        pattern = r'###\s+(User|Assistant):\s*\n\n(.+?)\n\n\*\*Time:\*\*\s+(.+?)\n\n---'
        
        for match in re.finditer(pattern, content, re.DOTALL):
            role = match.group(1).lower()
            role = "assistant" if role == "assistant" else "user"
            content_text = match.group(2).strip()
            timestamp = match.group(3).strip()
            
            messages.append({
                'role': role,
                'content': content_text,
                'timestamp': timestamp
            })
        
        return messages
    
    def add_conversation_message(self, role: str, content: str):
        """Add a message to conversation history"""
        timestamp = datetime.now().isoformat()
        message = {
            'role': role,
            'content': content,
            'timestamp': timestamp
        }
        self.messages.append(message)
        
        # Limit to last 200 messages
        if len(self.messages) > 200:
            self.messages = self.messages[-200:]
        
        # Append to file
        role_label = "User" if role == "user" else "Assistant"
        time_str = datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        message_block = f"""### {role_label}:

{content}

**Time:** {time_str}

---

"""
        
        with open(self.conversation_file, 'a', encoding='utf-8') as f:
            f.write(message_block)
        
        print(f"💾 Saved {role} message to conversation history")
    
    def get_recent_messages(self, max_messages: int = 10) -> List[Dict]:
        """Get recent conversation messages"""
        return self.messages[-max_messages:] if self.messages else []
    
    # ========== LESSON PLAN ==========
    
    def _init_lesson_plan_file(self):
        """Initialize lesson plan file"""
        if not self.lesson_plan_file.exists():
            header = f"""# Lesson Plan

**User:** {self.user_name}  
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Current Lesson

*No lesson plan yet. Start a lesson to create a plan.*

---

## Lesson History

"""
            self.lesson_plan_file.write_text(header, encoding='utf-8')
    
    def get_lesson_plan(self) -> str:
        """Get current lesson plan content"""
        if self.lesson_plan_file.exists():
            return self.lesson_plan_file.read_text(encoding='utf-8')
        return ""
    
    def update_lesson_plan(self, content: str, append: bool = False):
        """Update or append to lesson plan"""
        if append:
            # Append to current lesson section
            current = self.get_lesson_plan()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Find the "## Current Lesson" section and append
            if "## Current Lesson" in current:
                # Insert before "---" separator
                new_content = current.replace(
                    "---\n\n## Lesson History",
                    f"{content}\n\n**Updated:** {timestamp}\n\n---\n\n## Lesson History"
                )
            else:
                new_content = current + f"\n\n{content}\n\n**Updated:** {timestamp}\n"
        else:
            # Replace current lesson section
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_content = f"""# Lesson Plan

**User:** {self.user_name}  
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Last Updated:** {timestamp}

---

## Current Lesson

{content}

**Updated:** {timestamp}

---

## Lesson History

"""
        
        self.lesson_plan_file.write_text(new_content, encoding='utf-8')
        print(f"📚 Updated lesson plan")
    
    def add_to_lesson_history(self, lesson_summary: str):
        """Add completed lesson to history"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        history_entry = f"""
### Lesson Completed - {timestamp}

{lesson_summary}

---
"""
        
        current = self.get_lesson_plan()
        # Append to lesson history section
        if "## Lesson History" in current:
            new_content = current.replace(
                "## Lesson History",
                f"## Lesson History{history_entry}"
            )
        else:
            new_content = current + f"\n\n## Lesson History{history_entry}"
        
        self.lesson_plan_file.write_text(new_content, encoding='utf-8')
    
    # ========== CUSTOM NOTES ==========
    
    def _init_custom_notes_file(self):
        """Initialize custom notes file"""
        if not self.custom_notes_file.exists():
            header = f"""# Custom Notes

**User:** {self.user_name}  
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Notes

*No custom notes yet. Ask the assistant to add notes for you.*

---

"""
            self.custom_notes_file.write_text(header, encoding='utf-8')
    
    def get_custom_notes(self) -> str:
        """Get custom notes content"""
        if self.custom_notes_file.exists():
            return self.custom_notes_file.read_text(encoding='utf-8')
        return ""
    
    def add_custom_note(self, note: str, category: Optional[str] = None):
        """Add a note to custom notes file"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            current = self.get_custom_notes()
            
            # Create note entry
            if category:
                note_entry = f"""### {category} - {timestamp}

{note}

---
"""
            else:
                note_entry = f"""### Note - {timestamp}

{note}

---
"""
            
            # Insert before the last line (or at end)
            if "## Notes" in current:
                # Check if there's already content after "## Notes"
                notes_section_match = re.search(r'## Notes\s*\n\n(.*?)(?=\n\n---|$)', current, re.DOTALL)
                if notes_section_match and notes_section_match.group(1).strip() and "*No custom notes yet" not in notes_section_match.group(1):
                    # Append to existing notes
                    new_content = current.replace(
                        "## Notes",
                        f"## Notes{note_entry}"
                    )
                else:
                    # Replace the placeholder
                    new_content = current.replace(
                        "*No custom notes yet. Ask the assistant to add notes for you.*",
                        f"{note_entry.strip()}\n\n*No custom notes yet. Ask the assistant to add notes for you.*"
                    )
                    if "*No custom notes yet" not in new_content:
                        # If replacement didn't work, just append
                        new_content = current.replace("## Notes", f"## Notes{note_entry}")
            else:
                new_content = current + f"\n\n## Notes{note_entry}"
            
            self.custom_notes_file.write_text(new_content, encoding='utf-8')
            print(f"📝 Added custom note to {self.custom_notes_file}: {note[:50]}...")
            return True
        except Exception as e:
            print(f"❌ Error adding custom note: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def search_custom_notes(self, keyword: str) -> List[str]:
        """Search custom notes for keyword"""
        content = self.get_custom_notes()
        matches = []
        
        # Simple search - find lines containing keyword
        for line in content.split('\n'):
            if keyword.lower() in line.lower():
                matches.append(line.strip())
        
        return matches
    
    # ========== CONTEXT BUILDING ==========
    
    def build_context_string(self, include_lesson: bool = True, include_notes: bool = False) -> str:
        """Build context string for LLM from all three files"""
        context_parts = []
        
        # Recent conversation
        recent = self.get_recent_messages(max_messages=8)
        if recent:
            conv_context = "## Recent Conversation\n\n"
            for msg in recent[-5:]:
                role = "User" if msg['role'] == 'user' else "You"
                conv_context += f"{role}: {msg['content'][:150]}\n"
            context_parts.append(conv_context)
        
        # Lesson plan
        if include_lesson:
            lesson_content = self.get_lesson_plan()
            if lesson_content and "## Current Lesson" in lesson_content:
                # Extract current lesson section
                lesson_match = re.search(
                    r'## Current Lesson\s*\n\n(.*?)(?=\n\n---|\n\n##)',
                    lesson_content,
                    re.DOTALL
                )
                if lesson_match:
                    lesson_text = lesson_match.group(1).strip()[:500]  # Limit length
                    context_parts.append(f"## Current Lesson Plan\n\n{lesson_text}\n")
        
        # Custom notes (optional, can be large)
        if include_notes:
            notes_content = self.get_custom_notes()
            if notes_content and "## Notes" in notes_content:
                # Extract all notes - find everything after "## Notes"
                # Handle both cases: "## Notes\n\n" and "## Notes###" (no newline)
                notes_match = re.search(
                    r'## Notes\s*\n?\n?(.*?)(?=\n\n---\s*$|\*No custom notes|$)',
                    notes_content,
                    re.DOTALL
                )
                if notes_match:
                    notes_text = notes_match.group(1).strip()
                    # Remove the placeholder text if it exists
                    notes_text = re.sub(r'\*No custom notes yet.*?\*', '', notes_text, flags=re.DOTALL)
                    notes_text = notes_text.strip()
                    
                    if notes_text:
                        # Clean up any formatting issues (like "## Notes###" becoming "###")
                        notes_text = re.sub(r'^###', '###', notes_text)  # Ensure proper heading format
                        
                        # Limit to last 2000 chars to avoid token limits, but keep all important info
                        if len(notes_text) > 2000:
                            # Get the last 2000 characters (most recent notes)
                            notes_text = "...\n\n[Earlier notes truncated]\n\n" + notes_text[-2000:]
                        context_parts.append(f"## Custom Notes (Important Information to Remember)\n\n{notes_text}\n")
        
        return "\n\n".join(context_parts) if context_parts else ""

class GrokAssistant(Agent):
    """
    A voice AI assistant powered by xAI's Grok model with multi-file Markdown memory.
    Manages conversation history, lesson plans, and custom notes.
    """
    
    def __init__(self, instructions: str = None, memory: Optional[MultiFileMarkdownMemory] = None) -> None:
        default_instructions = (
            "You are Grokie, a Japanese language tutor. "
            "You help users learn Japanese through conversation. "
            "Keep responses short and educational (1-2 sentences). "
            "IMPORTANT: When the user asks you to remember something, save a note, or add to notes, "
            "you MUST use the save_note function to save it. "
            "When the user mentions lesson topics or objectives, use the update_lesson_plan function. "
            "You have access to custom notes from previous sessions - use the get_custom_notes function "
            "if you need to recall information that was saved before. "
            "Always use these functions when the user requests memory operations."
        )
        super().__init__(
            instructions=instructions or default_instructions,
        )
        self.memory = memory
        self.base_instructions = instructions or default_instructions
    
    @function_tool()
    async def save_note(self, content: str, category: str = None) -> str:
        """
        Save a note to the user's custom notes file.
        
        Use this when the user asks you to:
        - Remember something
        - Save a note
        - Add to notes
        - Write something down
        - Record information
        
        Args:
            content: The note content to save
            category: Optional category for the note (e.g., "Vocabulary", "Preferences", "Reminder")
        
        Returns:
            Confirmation message
        """
        if not self.memory:
            return "Error: Memory system not available"
        
        try:
            self.memory.add_custom_note(content, category)
            print(f"📝 Function called: save_note({content[:50]}..., category={category})")
            return f"Note saved successfully: {content[:50]}..."
        except Exception as e:
            print(f"❌ Error saving note: {e}")
            return f"Error saving note: {str(e)}"
    
    @function_tool()
    async def update_lesson_plan(self, content: str) -> str:
        """
        Update the current lesson plan.
        
        Use this when the user mentions:
        - Lesson topics
        - Learning objectives
        - What they want to study today
        - Lesson structure or plan
        
        Args:
            content: The lesson plan content or update
        
        Returns:
            Confirmation message
        """
        if not self.memory:
            return "Error: Memory system not available"
        
        try:
            self.memory.update_lesson_plan(content)
            print(f"📚 Function called: update_lesson_plan({content[:50]}...)")
            return f"Lesson plan updated successfully"
        except Exception as e:
            print(f"❌ Error updating lesson plan: {e}")
            return f"Error updating lesson plan: {str(e)}"
    
    @function_tool()
    async def get_custom_notes(self, keyword: str = None) -> str:
        """
        Retrieve custom notes that were previously saved.
        Use this when the user asks about something that might have been saved before,
        or when you need to recall information from previous sessions.
        
        Args:
            keyword: Optional keyword to search for in notes. If not provided, returns all notes.
        
        Returns:
            The relevant notes or all notes if no keyword provided
        """
        if not self.memory:
            return "Error: Memory system not available"
        
        try:
            if keyword:
                # Search for notes containing the keyword
                matches = self.memory.search_custom_notes(keyword)
                if matches:
                    return f"Found notes containing '{keyword}':\n" + "\n".join(matches[:10])  # Limit to 10 matches
                else:
                    return f"No notes found containing '{keyword}'"
            else:
                # Return all notes
                notes_content = self.memory.get_custom_notes()
                if notes_content and "## Notes" in notes_content:
                    # Extract just the notes section
                    notes_match = re.search(r'## Notes(.*?)(?=\n\n---\s*$|\*No custom notes|$)', notes_content, re.DOTALL)
                    if notes_match:
                        notes_text = notes_match.group(1).strip()
                        notes_text = re.sub(r'\*No custom notes yet.*?\*', '', notes_text, flags=re.DOTALL)
                        if notes_text.strip():
                            return f"All saved notes:\n{notes_text.strip()}"
                return "No custom notes found"
        except Exception as e:
            print(f"❌ Error retrieving notes: {e}")
            return f"Error retrieving notes: {str(e)}"
    
    @function_tool()
    async def add_to_conversation_history(self, role: str, content: str) -> str:
        """
        Manually add a message to conversation history.
        This is mainly for debugging or special cases.
        
        Args:
            role: Either "user" or "assistant"
            content: The message content
        
        Returns:
            Confirmation message
        """
        if not self.memory:
            return "Error: Memory system not available"
        
        try:
            self.memory.add_conversation_message(role, content)
            print(f"💬 Function called: add_to_conversation_history(role={role}, content={content[:50]}...)")
            return "Message added to conversation history"
        except Exception as e:
            print(f"❌ Error adding to conversation: {e}")
            return f"Error: {str(e)}"
    
    def save_note_manually(self, note_content: str, category: Optional[str] = None):
        """Manually save a note - can be called from instructions or other methods"""
        if self.memory and note_content:
            self.memory.add_custom_note(note_content, category)
            print(f"📝 Manually saved note: {note_content[:50]}...")
            return True
        return False
    
    async def on_enter(self, ctx=None):
        """Load context from all memory files when session starts"""
        if self.memory:
            # Build context from conversation + lesson plan + custom notes
            context = self.memory.build_context_string(
                include_lesson=True,
                include_notes=True  # Include custom notes so agent remembers saved information
            )
            
            if context:
                new_instructions = self.base_instructions + "\n\n" + context
                await self.update_instructions(new_instructions)
                print("✅ Loaded context from memory files (including custom notes)")
                print(f"📝 Context preview: {context[:200]}...")
            else:
                print("ℹ️ No previous context found")
    
    # Note: We're using function calling instead of lifecycle hooks
    # The agent will explicitly call save_note() and update_lesson_plan() functions
    # when the user requests memory operations
    
    async def _refresh_instructions(self):
        """Refresh instructions with latest context"""
        if not self.memory:
            return
        
        context = self.memory.build_context_string(
            include_lesson=True,
            include_notes=True  # Include notes when refreshing too
        )
        
        if context:
            new_instructions = self.base_instructions + "\n\n" + context
            await self.update_instructions(new_instructions)


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
async def request_handler(ctx):
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
    
    # Get room name from context - ctx has a room attribute
    try:
        room_name = ctx.room.name if ctx.room else 'default-room'
    except AttributeError:
        room_name = 'default-room'
    
    # Use room name as user identifier (each room = one user session)
    # This ensures memory is per-room, which works well for single-user rooms
    user_name = room_name
    
    # Initialize multi-file memory
    memory = MultiFileMarkdownMemory(room_name, user_name)
    print(f"📁 Memory initialized for room: {room_name}, user: {user_name}")
    
    # Initialize the session with Grok realtime model
    # You can customize the voice by passing voice parameter:
    # Available voices: 'Ara', 'Rex', 'Sal', 'Eve', 'Leo'
    session = AgentSession(
        llm=xai.realtime.RealtimeModel(
            voice='Eve',
        ),
    )
    
    # Create agent with memory
    agent = GrokAssistant(memory=memory)
    
    # Start the session with the GrokAssistant agent
    # The agent now has function tools (save_note, update_lesson_plan) that it can call
    # when the user requests memory operations
    await session.start(room=ctx.room, agent=agent)
    
    # Generate an initial greeting
    await session.generate_reply(
        instructions="Greet the user and check if they want to continue their lesson or start a new one."
    )


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

