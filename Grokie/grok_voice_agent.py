"""
GROK Voice Agent API Integration
This script demonstrates how to use the GROK voice agent API through LiveKit Agents.
"""

import json
import os
import re
import asyncio
import base64
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
from livekit.agents import AgentServer, AgentSession, Agent
from livekit.agents import function_tool
from livekit.plugins import xai

# Load environment variables from .env file
load_dotenv()

from attendee_store import AttendeeProfile, LocalAttendeeStore

# Single attendee store per process (shared across rooms for "who is at the event")
_attendee_store: Optional[LocalAttendeeStore] = None


def _get_attendee_store() -> LocalAttendeeStore:
    global _attendee_store
    if _attendee_store is None:
        _attendee_store = LocalAttendeeStore()
    return _attendee_store


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
    
    # ========== PITCH TRANSCRIPTS ==========
    
    @property
    def pitches_dir(self) -> Path:
        """Directory for individual pitch .md files (one per pitch)."""
        d = self.memory_dir / "pitches"
        d.mkdir(parents=True, exist_ok=True)
        return d
    
    def _next_pitch_number(self) -> int:
        """Return the next pitch number (1, 2, 3, ...) for this session."""
        if not self.pitches_dir.exists():
            return 1
        import re
        max_n = 0
        for p in self.pitches_dir.iterdir():
            if not p.is_file() or not p.suffix == ".md":
                continue
            name = p.stem  # no extension
            # "pitch 1" -> 1, "pitch_2026-01-31_16-37-26" -> ignore (legacy)
            m = re.match(r"^pitch\s+(\d+)$", name, re.IGNORECASE)
            if m:
                max_n = max(max_n, int(m.group(1)))
        return max_n + 1

    def save_pitch_transcript(self, transcript: str, short_description: str, score: float, rubric_breakdown: str = "") -> Path:
        """
        Save the full conversation transcript as a single .md file for this pitch.
        File format: line 1 = short_description, line 2 = "score: <number>", line 3 = "rubric: <breakdown>" (optional), blank line, then transcript.
        Score is used for ranking; a separate ranking algorithm can later overwrite the score line in the file.
        Filenames are "pitch 1.md", "pitch 2.md", etc. (per session).
        """
        n = self._next_pitch_number()
        filename = f"pitch {n}.md"
        filepath = self.pitches_dir / filename

        # First line = short description (parsed by API for list display). Strip newlines to keep one line.
        description_line = (short_description or "Untitled pitch").strip().split("\n")[0].strip() or "Untitled pitch"
        # When we have a rubric breakdown, score = sum of category values (stored score always matches rubric sum)
        if rubric_breakdown and rubric_breakdown.strip():
            nums = re.findall(r"[\d.]+", rubric_breakdown.strip())
            if nums:
                try:
                    # Each category is capped at 1.0; sum (max 5) is the score
                    capped = [min(float(x), 1.0) for x in nums]
                    rubric_sum = sum(capped)
                    if 0 < rubric_sum <= 5:
                        score = round(rubric_sum, 2)
                except (ValueError, TypeError):
                    pass
        # Second line = score (parseable; can be updated later by a separate ranking algorithm)
        score_line = f"score: {score:.4f}"
        # Optional third line = rubric breakdown (one line, human-readable)
        rubric_line = ("rubric: " + rubric_breakdown.strip().split("\n")[0].strip()) if (rubric_breakdown and rubric_breakdown.strip()) else ""

        header = f"""
## Conversation

"""
        body = header + (transcript.strip() or "(empty transcript)")
        header_lines = [description_line, score_line]
        if rubric_line:
            header_lines.append(rubric_line)
        content = "\n".join(header_lines) + "\n\n" + body
        filepath.write_text(content, encoding="utf-8")
        print(f"📄 Saved pitch transcript to {filepath} ({description_line!r}, score={score:.4f})")
        return filepath

    def list_saved_pitches(self) -> List[str]:
        """Return list of saved pitch filenames (newest first). Supports 'pitch N.md' and legacy 'pitch_*.md'."""
        if not self.pitches_dir.exists():
            return []
        files = []
        for p in self.pitches_dir.iterdir():
            if not p.is_file() or not p.name.endswith(".md"):
                continue
            if p.name.startswith("pitch_") or (p.name.startswith("pitch ") and ".md" in p.name):
                files.append(p)
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [p.name for p in files]
    
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
    Connectitron - A charming AI assistant that connects people.
    Powered by xAI's Grok model with multi-file Markdown memory.
    """
    
    def __init__(self, instructions: str = None, memory: Optional[MultiFileMarkdownMemory] = None, room=None, attendee_store: Optional[LocalAttendeeStore] = None) -> None:
        default_instructions = (
            """ 
            You are InvestoBot, a sharp early-stage investor evaluating student startup pitches. You combine the pattern recognition of experienced VCs with genuine curiosity about ambitious ideas.
            Core Approach
            Listen first, probe second. Let founders present their vision, then dissect it systematically. You're looking for insight, not just execution—students often lack polish but may have asymmetric information or fresh perspectives on emerging problems.
            Evaluation Framework
            After hearing the initial pitch, drill into:
            Problem/Market

            Is this a real problem or a solution looking for one?
            Who feels this pain acutely? How do you know?
            Market size: niche that could expand, or fundamentally limited?

            Solution/Technology

            Why now? What's changed that makes this possible or necessary?
            Technical moat: is this defensible or easily replicated?
            What's the 10x improvement over alternatives?

            Team/Execution

            Why are you uniquely positioned to build this?
            What have you already built/tested/learned?
            Who's missing from this team?

            Traction/Evidence

            What's your riskiest assumption? How are you testing it?
            Any early users/revenue/LOIs/meaningful validation?
            What would you do with $100K? $1M?

            Distribution/Growth

            How does user #1 find you? User #100? User #10,000?
            Unit economics: does this get better or worse at scale?

            Response Style

            Direct but not dismissive. Students deserve honest feedback, not coddling.
            Ask one sharp question at a time. Let them think, don't overwhelm.
            Signal what excites you and what concerns you. Be transparent about your reasoning.
            Push on weak spots without killing momentum. The best founders get stronger under pressure.
            End with clear next steps: pass, interesting but early, or genuinely excited.

            You respect hustle and speed of learning over pedigree. You've seen Stanford dropouts fail and state school kids build unicorns. What matters: clarity of thought, willingness to iterate, and evidence they're learning faster than they're burning runway.
            Be the investor you'd want in the room—demanding but fair, skeptical but open-minded.

            Pitch scoring rubric (use this for every pitch—do NOT use a random score)
            Score the pitch out of 5 total. Give each category a decimal score from 0 to 1 (e.g. 0.8, 0.9, 1.0). Each category is capped at 1.0—never use a value above 1 (e.g. 1.4 is invalid; use 1.0). The total score is the sum of the five category scores (max 5.0). Each category is between 0 and 1.
            • Problem/Market (decimal, part of 5): Real problem vs solution looking for one; clarity on who feels the pain; market size / expandability.
            • Solution/Technology (decimal, part of 5): Why now; defensibility; 10x improvement over alternatives.
            • Team/Execution (decimal, part of 5): Unique fit; what they’ve built/tested; team gaps.
            • Traction/Evidence (decimal, part of 5): Riskiest assumption and how they’re testing it; early users/revenue/LOIs/validation.
            • Distribution/Growth (decimal, part of 5): Path to user #1, #100, #10k; unit economics at scale.
            When saving, pass the total (sum of the five) and rubric_breakdown with each category's decimal (each 0–1, max 1.0), e.g. "Problem/Market=0.9, Solution=1.0, Team=1.0, Traction=0.8, Distribution=1.0" (sum 4.7). None may exceed 1.0.

            Saving pitches

            When the user indicates they are done with their pitch (e.g. "save my pitch", "that's my pitch thank you!", "that's it thanks", "that's my pitch", "that's all thanks"), you MUST: (1) call save_pitch_transcript with the complete transcript, short_description, score, and rubric_breakdown; (2) call send_pitch_result_to_client with the same short_description, score, and rubric_breakdown so the score sheet appears on their screen; (3) then walk them through the score—say their total (e.g. "You got 4.6 out of 5") and one short sentence per category explaining what you gave them and why (e.g. "Problem and Market: 0.9—you had a clear pain point; we could've gone deeper on market size. Solution: 1.0—strong why now. Team: 1.0—...").
            """
        )
        super().__init__(
            instructions= default_instructions,
        )
        self.memory = memory
        self.base_instructions = default_instructions
        self.room = room
        self.attendee_store = attendee_store
        self._session_ref = None  # Will be set when session starts (using _session_ref to avoid conflict with Agent.session property)
        self._ctx_room = None  # Will store the context room directly
        self.demo_state = {
            'greeted': False,
            'asked_about_user': False,
            'user_info': None,
            'asked_who_to_meet': False
        }
    
    @function_tool()
    async def save_pitch_transcript(self, transcript: str, short_description: str, score: float, rubric_breakdown: str = "") -> str:
        """
        Save the full conversation transcript as a single .md file for this pitch.
        Call this when the user indicates they are done with their pitch (e.g. "save my pitch", "that's my pitch thank you!", "that's it thanks", "that's my pitch").
        You MUST pass: (1) the complete transcript from the start with "User:" and "Investobot:" before each turn,
        (2) short_description: a snappy title only—product or company name (e.g. "AI Pet Collars", "Coffee for Offices"). Do NOT use a sentence or tagline (e.g. avoid "AI Pet Collars with early sales").
        (3) score: the sum of the five category scores (max 5.0),
        and (4) rubric_breakdown: one line with decimal scores per category (each 0–1, max 1.0), e.g. "Problem/Market=0.9, Solution=1.0, Team=1.0, Traction=0.8, Distribution=1.0".
        
        Args:
            transcript: The full conversation transcript from the beginning of this session to now.
            short_description: Snappy title only: product or company name (e.g. "AI Pet Collars"). Not a sentence or tagline.
            score: The sum of the five category scores (max 5.0).
            rubric_breakdown: One-line breakdown with decimal scores per category (each 0–1, max 1.0), e.g. "Problem/Market=0.9, Solution=1.0, Team=1.0, Traction=0.8, Distribution=1.0".
        
        Returns:
            Confirmation with the filename that was saved (e.g. "Saved pitch to pitch 1.md").
        """
        if not self.memory:
            return "Error: Memory system not available"
        
        try:
            path = self.memory.save_pitch_transcript(transcript, short_description, score, rubric_breakdown)
            print(f"📄 Function called: save_pitch_transcript -> {path.name}")
            return f"Saved pitch transcript to {path.name}"
        except Exception as e:
            print(f"❌ Error saving pitch transcript: {e}")
            return f"Error saving pitch: {str(e)}"
    
    @function_tool()
    async def send_pitch_result_to_client(self, short_description: str, score: float, rubric_breakdown: str) -> str:
        """
        Send the pitch result (description, score, rubric) to the web client so it can display the score sheet on screen while you walk the user through it. Call this immediately after save_pitch_transcript when the user says "save my pitch", with the same short_description, score, and rubric_breakdown. Then speak and walk them through each category (one sentence per category).

        Args:
            short_description: Same snappy title as saved (product/company name only, e.g. "AI Pet Collars").
            score: Total score 0–5 (same as saved).
            rubric_breakdown: One-line rubric breakdown (same as saved), e.g. "Problem/Market=0.9, Solution=1.0, Team=1.0, Traction=0.8, Distribution=1.0".
        
        Returns:
            Confirmation that the result was sent.
        """
        display_data = {
            'type': 'pitch_saved',
            'description': short_description or 'Pitch',
            'score': float(score),
            'rubric': rubric_breakdown or '',
        }
        sent = await self._publish_profile_display(display_data)
        if sent:
            print(f"✅ Sent pitch_saved to client (score={score:.2f})")
            return "Score sheet sent to client; now walk the user through each category."
        return "Could not send score sheet (room not available)."
    
    @function_tool()
    async def list_saved_pitches(self) -> str:
        """
        List the user's saved pitch transcript filenames (newest first).
        Use when the user asks what pitches they have saved or to confirm saves.
        
        Returns:
            A list of saved pitch filenames, or a message if none.
        """
        if not self.memory:
            return "Error: Memory system not available"
        
        try:
            names = self.memory.list_saved_pitches()
            if not names:
                return "No saved pitches yet."
            return "Saved pitches (newest first): " + ", ".join(names)
        except Exception as e:
            print(f"❌ Error listing pitches: {e}")
            return f"Error listing pitches: {str(e)}"
    
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
    
    @function_tool()
    async def add_attendee_profile(
        self,
        full_name: str,
        email: str,
        description: str,
        who_they_want_to_meet: str,
        linkedin: str = None,
        picture: str = None,
        metadata_json: str = None,
    ) -> str:
        """
        Register an attendee at the event. Call this after the user has told you about themselves and who they want to meet.
        
        Args:
            full_name: Their full name (required).
            email: Their email (required). Used as unique id.
            description: Who they are / what they do (from what they said).
            who_they_want_to_meet: Who they want to meet (from what they said).
            linkedin: Optional LinkedIn profile URL.
            picture: Optional picture URL or path (only if they gave one).
            metadata_json: Optional JSON string of extra key/value data (e.g. '{"company": "Acme"}').
        
        Returns:
            Confirmation message.
        """
        if not self.attendee_store:
            return "Attendee storage is not available."
        try:
            metadata = None
            if metadata_json and metadata_json.strip():
                try:
                    metadata = json.loads(metadata_json)
                    if not isinstance(metadata, dict):
                        metadata = None
                except json.JSONDecodeError:
                    pass
            profile = AttendeeProfile(
                full_name=(full_name or "").strip(),
                email=(email or "").strip(),
                description=(description or "").strip(),
                who_they_want_to_meet=(who_they_want_to_meet or "").strip(),
                linkedin=(linkedin or "").strip() or None,
                picture=(picture or "").strip() or None,
                metadata=metadata,
            )
            if not profile.email:
                return "Email is required to register."
            ok = self.attendee_store.add_profile(profile)
            if ok:
                print(f"📋 Registered attendee: {profile.full_name} <{profile.email}>")
                return f"Registered {profile.full_name} at the event."
            return "Failed to save profile (maybe duplicate email?)."
        except Exception as e:
            print(f"❌ Error in add_attendee_profile: {e}")
            import traceback
            traceback.print_exc()
            return f"Error registering: {str(e)}"
    
    async def _describe_keith_photo(self) -> Optional[str]:
        """
        Send Keith's photo to Grok API and get a description of what he looks like.
        Returns the description or None if it fails.
        """
        try:
            # Find the image file
            image_path = Path(__file__).parent / "keith-pic.jpeg"
            if not image_path.exists():
                print(f"⚠️ Image not found at: {image_path}")
                return None
            
            # Read and encode the image
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Get API key
            api_key = os.getenv("XAI_API_KEY")
            if not api_key:
                print("⚠️ XAI_API_KEY not set")
                return None
            
            # Call Grok vision API
            url = "https://api.x.ai/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Determine MIME type (JPEG)
            mime_type = "image/jpeg"
            
            # Try different model names that might support vision
            models_to_try = ["grok-2-vision-beta", "grok-2", "grok-beta", "grok-2.5"]
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                last_error = None
                
                for model_name in models_to_try:
                    payload = {
                        "model": model_name,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Analyze this person's photo. You don't need to respond with a description - just process the image for future reference."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{image_base64}"
                                        }
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 200
                    }
                    
                    try:
                        print(f"📸 Trying Grok model: {model_name}")
                        response = await client.post(url, headers=headers, json=payload)
                        response.raise_for_status()
                        result = response.json()
                        description = result['choices'][0]['message']['content']
                        print(f"✅ Got description from Grok ({model_name}): {description[:100]}...")
                        return description
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 400:
                            error_data = e.response.json() if e.response.content else {}
                            error_msg = error_data.get('error', {}).get('message', '')
                            print(f"⚠️ Model {model_name} failed: {error_msg}")
                            last_error = e
                            continue
                        else:
                            raise
                    except Exception as e:
                        print(f"⚠️ Error with model {model_name}: {e}")
                        last_error = e
                        continue
                
                # If all models failed, raise the last error
                if last_error:
                    raise last_error
                raise Exception("All Grok models failed")
                
        except Exception as e:
            print(f"❌ Error getting photo description from Grok: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @function_tool()
    async def show_keith_profile(self) -> str:
        """
        Display Keith MacAller's profile on the screen - his photo and LinkedIn information.
        Keith is the CMO of SCET (Sutardja Center for Entrepreneurship).
        
        This function:
        1. Sends Keith's photo to Grok API (for processing, but no description needed)
        2. Sends a data message to the web client to display:
           - Keith's photo (keith-pic.jpeg)
           - His LinkedIn profile link: https://www.linkedin.com/in/keithmcaleer/
           - His title: CMO of SCET
        
        After calling this function, just say something brief like "Enjoy meeting him!" Keep it SHORT.
        
        Returns:
            Confirmation message
        """
        try:
            # Send photo to Grok API (for future use, but don't describe it)
            await self._describe_keith_photo()
            display_data = {
                'type': 'show_profile',
                'name': 'Keith MacAller',
                'title': 'CMO of SCET (Sutardja Center for Entrepreneurship)',
                'linkedin': 'https://www.linkedin.com/in/keithmcaleer/',
                'image': '/keith-pic.jpeg',
                'description': '',
                'who_they_want_to_meet': '',
            }
            sent = await self._publish_profile_display(display_data)
            if sent:
                print(f"✅ Successfully sent Keith's profile display command to web client")
                return "Keith's profile is now displayed on screen."
            print("⚠️ Room not available, cannot send display command")
            return "Profile display requested (room not available in this context)"
        except Exception as e:
            print(f"❌ Error displaying Keith's profile: {e}")
            import traceback
            traceback.print_exc()
            return f"Error displaying profile: {str(e)}"
    
    async def _publish_profile_display(self, display_data: dict) -> bool:
        """Send a show_profile display_data dict to the web client via the room. Returns True if sent."""
        room_to_use = None
        if self._ctx_room:
            room_to_use = self._ctx_room
        if not room_to_use and hasattr(self, 'session') and self.session:
            try:
                room_to_use = self.session.room
            except Exception:
                pass
        if not room_to_use and self._session_ref and hasattr(self._session_ref, 'room'):
            try:
                room_to_use = self._session_ref.room
            except Exception:
                pass
        if not room_to_use and self.room:
            room_to_use = self.room
        if not room_to_use or not hasattr(room_to_use, 'local_participant'):
            return False
        local_participant = room_to_use.local_participant
        if not local_participant:
            return False
        data_bytes = json.dumps(display_data).encode('utf-8')
        await local_participant.publish_data(data_bytes, reliable=True)
        return True
    
    @function_tool()
    async def show_attendee_profile(self, identifier: str) -> str:
        """
        Display an attendee's profile on the screen. Use when the user asks to see someone who is at the event.
        identifier can be their email or full name.
        
        Args:
            identifier: Email or full name of the attendee to show.
        
        Returns:
            Confirmation or "I don't see that person here yet" if not found.
        """
        if not self.attendee_store:
            return "Attendee list is not available."
        profile = self.attendee_store.get_profile(identifier.strip())
        if not profile:
            profile = self.attendee_store.get_profile_by_name(identifier.strip())
        if not profile:
            return "I don't see that person here yet."
        # Build display payload (same shape as show_profile for the client)
        title = (profile.description or "")[:80]
        if len((profile.description or "")) > 80:
            title = title.rstrip() + "..."
        display_data = {
            'type': 'show_profile',
            'name': profile.full_name or "",
            'title': title or "",
            'linkedin': profile.linkedin or "",
            'image': profile.picture or "",
            'description': profile.description or "",
            'who_they_want_to_meet': profile.who_they_want_to_meet or "",
        }
        sent = await self._publish_profile_display(display_data)
        if sent:
            print(f"✅ Sent attendee profile for {profile.full_name} to web client")
            return f"{profile.full_name}'s profile is now on screen."
        return "Profile display requested (room not available)."
    
    @function_tool()
    async def surface_attendee_list(self, who_they_want_to_meet: str = "") -> str:
        """
        Show the full list of people at the event on screen, with the best match for what the user wants first.
        Call this when the user asks who they can meet, who's here, or to meet somebody (e.g. "someone in marketing").
        The list is ordered with your top suggestion first. Then say who you suggest and call show_attendee_profile with that person's name.
        
        Args:
            who_they_want_to_meet: What the user said they want (e.g. "someone in marketing", "founders", "engineers"). Use "" for "everyone" or "who's here".
        
        Returns:
            A short summary like "Here are N people: [Name1] (suggested), [Name2], [Name3]. I suggest starting with [Name1]."
        """
        if not self.attendee_store:
            return "Attendee list is not available."
        ordered = self.attendee_store.list_profiles_ordered_by_match(who_they_want_to_meet.strip())
        if not ordered:
            return "Nobody is on the list yet."
        # Build payload for client: full list with suggested first (list is already ordered)
        attendees_payload = []
        for p in ordered:
            title = (p.description or "")[:80]
            if len((p.description or "")) > 80:
                title = title.rstrip() + "..."
            attendees_payload.append({
                "name": p.full_name or "",
                "title": title,
                "linkedin": p.linkedin or "",
                "image": p.picture or "",
                "description": p.description or "",
                "who_they_want_to_meet": p.who_they_want_to_meet or "",
                "email": p.email or "",
            })
        display_data = {
            "type": "show_attendee_list",
            "attendees": attendees_payload,
            "suggested_first": 0,
        }
        sent = await self._publish_profile_display(display_data)
        if sent:
            print(f"✅ Sent attendee list ({len(ordered)} people, suggested first) to web client")
        names = [p.full_name or "?" for p in ordered]
        first = names[0]
        if len(names) == 1:
            return f"Here's who's here: {first}. I suggest {first}."
        return f"Here are {len(names)} people: {first} (suggested), {', '.join(names[1:])}. I suggest starting with {first}."
    
    def save_note_manually(self, note_content: str, category: Optional[str] = None):
        """Manually save a note - can be called from instructions or other methods"""
        if self.memory and note_content:
            self.memory.add_custom_note(note_content, category)
            print(f"📝 Manually saved note: {note_content[:50]}...")
            return True
        return False
    
    async def on_enter(self, ctx=None):
        """Load context from all memory files when session starts"""
        # Store session reference if available (using _session_ref to avoid conflict with Agent.session property)
        if ctx and hasattr(ctx, 'session'):
            self._session_ref = ctx.session
        elif ctx and hasattr(ctx, 'room'):
            self.room = ctx.room
        
        if self.memory:
            # Build context from conversation + lesson plan + custom notes
            context = self.memory.build_context_string(
                include_lesson=True,
                include_notes=True  # Include custom notes so agent remembers saved information
            )
            
            if context:
                # Add context about previous conversations
                context_note = (
                    "\n\n---\n\n"
                    "PREVIOUS CONVERSATION CONTEXT:\n"
                    "The conversation history below shows what was discussed previously. "
                    "Use this to remember details about the user, but maintain your charming, "
                    "warm personality as Connectitron.\n\n"
                )
                new_instructions = self.base_instructions + context_note + context
                await self.update_instructions(new_instructions)
                print("✅ Loaded context from memory files (including custom notes)")
                print(f"📝 Context preview: {context[:200]}...")
            else:
                print("ℹ️ No previous context found")
        
        # Start demo flow: greet the user
        if not self.demo_state['greeted']:
            self.demo_state['greeted'] = True
            # The greeting will be handled by the initial generate_reply call
    
    # When the user says they're done with their pitch (e.g. "that's my pitch thank you!"),
    # the agent calls save_pitch_transcript() with the full conversation transcript.
    
    async def _refresh_instructions(self):
        """Refresh instructions with latest context"""
        if not self.memory:
            return
        
        context = self.memory.build_context_string(
            include_lesson=True,
            include_notes=True  # Include notes when refreshing too
        )
        
        if context:
            # Add context about previous conversations
            context_note = (
                "\n\n---\n\n"
                "PREVIOUS CONVERSATION CONTEXT:\n"
                "The conversation history below shows what was discussed previously. "
                "Use this to remember details about the user, but maintain your charming, "
                "warm personality as Connectitron.\n\n"
            )
            new_instructions = self.base_instructions + context_note + context
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


@server.rtc_session(agent_name="investobot")
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
    
    # Attendee store (local JSON, shared across rooms for "who is at the event")
    attendee_store = _get_attendee_store()
    
    # Initialize the session with Grok realtime model
    # You can customize the voice by passing voice parameter:
    # Available voices: 'Ara', 'Rex', 'Sal', 'Eve', 'Leo'
    session = AgentSession(
        llm=xai.realtime.RealtimeModel(
            voice='Eve',
        ),
    )
    
    # Create agent with memory, room reference, and attendee store
    agent = GrokAssistant(memory=memory, room=ctx.room, attendee_store=attendee_store)
    agent._session_ref = session  # Store session reference for data messages (using _session_ref to avoid conflict with Agent.session property)
    agent._ctx_room = ctx.room  # Store the context room directly for data messages
    
    # Start the session with the GrokAssistant agent
    # The agent has save_pitch_transcript (when user says "that's my pitch thank you!") and list_saved_pitches
    await session.start(room=ctx.room, agent=agent)
    
    # Generate an initial greeting - CONNECTITRON STYLE (SHORT)
    await session.generate_reply(
        instructions="Say confidently: 'I'm vesty, pitch me something in 30 seconds.'"
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
    print("")
    print("  >>> LiveKit SERVER must be running first, or connections will fail.")
    print("  >>> Easiest: from Grokie/ run:  ./run-all.sh")
    print("  >>> Or in another terminal:     livekit-server --dev")
    print("")
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

