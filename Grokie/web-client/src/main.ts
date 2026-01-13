import { Room, RoomEvent, RemoteParticipant, LocalAudioTrack, RemoteAudioTrack, createLocalAudioTrack } from 'livekit-client';

// Configuration
const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || 'ws://localhost:7880';
const LIVEKIT_API_KEY = import.meta.env.VITE_LIVEKIT_API_KEY || 'devkey';
const LIVEKIT_API_SECRET = import.meta.env.VITE_LIVEKIT_API_SECRET || 'secret';

let room: Room | null = null;
let localAudioTrack: LocalAudioTrack | null = null;
let audioContext: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let animationFrameId: number | null = null;
let isSpeaking = false;

// Agent state
let isAgentEnabled = false;

// Default values
const DEFAULT_ROOM = 'test-room';
const DEFAULT_NAME = 'User';

// Get DOM elements
const chatContainer = document.getElementById('chatContainer')!;
const toggleGrokieBtn = document.getElementById('toggleGrokieBtn') as HTMLButtonElement;

// API base URL
const tokenServerUrl = import.meta.env.VITE_TOKEN_SERVER_URL || '/api';

// Transcription state for chat - track last message per participant for 1:1 turns
const lastMessageByParticipant = new Map<string, HTMLElement>();

// ========== CHAT DISPLAY FUNCTIONS ==========

function addChatMessage(role: 'user' | 'assistant', text: string, isInterim: boolean = false) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role} ${isInterim ? 'interim' : ''}`;
  
  const label = role === 'user' ? 'You' : 'Grokie';
  
  messageDiv.innerHTML = `
    <div class="chat-bubble">
      <div class="chat-label">${label}</div>
      <div class="chat-text">${text}</div>
    </div>
  `;
  
  chatContainer.appendChild(messageDiv);
  
  // Track last message by participant
  if (!isInterim) {
    lastMessageByParticipant.set(role, messageDiv);
  }
  
  scrollChatToBottom();
  return messageDiv;
}

function scrollChatToBottom() {
  // Use setTimeout with requestAnimationFrame to ensure DOM is fully updated
  setTimeout(() => {
    requestAnimationFrame(() => {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    });
  }, 0);
}

async function loadChatHistory() {
  try {
    const response = await fetch(`${tokenServerUrl}/markdown/conversation_history?room=${DEFAULT_ROOM}`);
    if (!response.ok) {
      chatContainer.innerHTML = '<div class="chat-message assistant"><div class="chat-bubble"><div class="chat-text">No conversation history yet. Start talking to Grokie!</div></div></div>';
      return;
    }
    
    const content = await response.text();
    if (!content) {
      chatContainer.innerHTML = '<div class="chat-message assistant"><div class="chat-bubble"><div class="chat-text">No conversation history yet. Start talking to Grokie!</div></div></div>';
      return;
    }
    
    // Parse conversation history markdown
    // Pattern: ### User: or ### Assistant: followed by content
    const messagePattern = /###\s+(User|Assistant):\s*\n\n(.+?)(?=\n\n\*\*Time:\*\*|###|$)/gs;
    const messages: Array<{ role: 'user' | 'assistant'; content: string }> = [];
    
    let match;
    while ((match = messagePattern.exec(content)) !== null) {
      const role = match[1].toLowerCase() === 'user' ? 'user' : 'assistant';
      const messageContent = match[2].trim();
      messages.push({ role, content: messageContent });
    }
    
    // Display messages
    chatContainer.innerHTML = '';
    if (messages.length === 0) {
      chatContainer.innerHTML = '<div class="chat-message assistant"><div class="chat-bubble"><div class="chat-text">No conversation history yet. Start talking to Grokie!</div></div></div>';
    } else {
      messages.forEach(msg => {
        addChatMessage(msg.role, msg.content);
      });
    }
  } catch (error) {
    console.error('Error loading chat history:', error);
    chatContainer.innerHTML = '<div class="chat-message assistant"><div class="chat-bubble"><div class="chat-text">Error loading conversation history.</div></div></div>';
  }
}

// ========== TRANSCRIPTION HANDLER ==========

function setupTranscriptionHandler(room: Room) {
  try {
    room.registerTextStreamHandler('lk.transcription', async (reader, participantInfo) => {
      try {
        const message = await reader.readAll();
        const attributes = reader.info?.attributes || {};
        const isTranscription = attributes['lk.transcribed_track_id'] != null;
        const isFinal = attributes['lk.transcription_final'] === 'true';
        
        if (!isTranscription || !message) {
          return;
        }
        
        // Determine if this is from user or assistant
        const isUser = participantInfo.identity === DEFAULT_NAME || 
                      participantInfo.identity === room.localParticipant.identity;
        const role = isUser ? 'user' : 'assistant';
        
        // For 1:1 turns, track by role only - one message per role at a time
        // Check if we have a last message from this role
        const lastMessage = lastMessageByParticipant.get(role);
        
        if (lastMessage && lastMessage.classList.contains('interim')) {
          // Update existing interim message
          const textEl = lastMessage.querySelector('.chat-text');
          if (textEl) {
            textEl.textContent = message;
          }
          
          if (isFinal) {
            // Mark as final - this completes the turn
            lastMessage.classList.remove('interim');
          }
        } else if (isFinal) {
          // New final message = new turn - create new message
          // Only create if this is final (not interim) to ensure 1:1 turns
          const messageDiv = addChatMessage(role, message, false);
          lastMessageByParticipant.set(role, messageDiv);
        } else if (!lastMessage) {
          // First message from this participant (interim)
          const messageDiv = addChatMessage(role, message, true);
          lastMessageByParticipant.set(role, messageDiv);
        }
        // If we have a final message and receive another interim, ignore it
        // (shouldn't happen, but handle gracefully)
      } catch (error) {
        console.error('Error reading transcription:', error);
      }
    });
    
    console.log('Transcription handler registered');
  } catch (error) {
    console.error('Error setting up transcription handler:', error);
  }
}

// ========== LIVEKIT CONNECTION FUNCTIONS ==========

async function generateToken(roomName: string, participantName: string): Promise<string> {
  const tokenEndpoint = `${tokenServerUrl}/token`;
  
  try {
    const response = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ room: roomName, name: participantName })
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || 'Failed to generate token');
    }
    
    const data = await response.json();
    if (!data.token || typeof data.token !== 'string') {
      throw new Error('Invalid token received from server');
    }
    
    return data.token;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Cannot reach token server. Make sure the server is running.');
    }
    throw error;
  }
}

async function requestMicrophonePermission(): Promise<MediaStream> {
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    console.error('Microphone permission denied:', error);
    throw new Error('Microphone access is required. Please allow microphone access and try again.');
  }
}

async function connect() {
  try {
    // Request microphone permission
    const stream = await requestMicrophonePermission();
    stream.getTracks().forEach(track => track.stop());

    // Create room instance
    room = new Room({
      adaptiveStream: true,
      dynacast: true,
    });

    // Set up event handlers
    room.on(RoomEvent.Connected, async () => {
      console.log('Connected to room:', DEFAULT_ROOM);
      
      // Register transcription handler
      setupTranscriptionHandler(room);

      // Create and publish microphone track
      try {
        localAudioTrack = await createLocalAudioTrack();
        await room!.localParticipant.publishTrack(localAudioTrack);
        console.log('Microphone track published');
      } catch (error) {
        console.error('Error publishing microphone:', error);
      }
    });

    room.on(RoomEvent.Disconnected, () => {
      console.log('Disconnected from room');
      localAudioTrack = null;
      
      // Stop audio analysis
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
      }
      if (audioContext) {
        audioContext.close();
        audioContext = null;
        analyser = null;
      }
      isSpeaking = false;
    });

    room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
      console.log('Participant connected:', participant.identity);
      
      participant.on('trackSubscribed', (track) => {
        if (track.kind === 'audio' && track instanceof RemoteAudioTrack) {
          const audioElement = track.attach() as HTMLAudioElement;
          document.body.appendChild(audioElement);
          audioElement.play().catch(console.error);
        }
      });
    });

    room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
      if (track.kind === 'audio' && participant !== room?.localParticipant && track instanceof RemoteAudioTrack) {
        const audioElement = track.attach() as HTMLAudioElement;
        document.body.appendChild(audioElement);
        audioElement.play().catch(console.error);
      }
    });

    // Generate token and connect
    const token = await generateToken(DEFAULT_ROOM, DEFAULT_NAME);
    await room.connect(LIVEKIT_URL, token, {
      autoSubscribe: true,
    });

  } catch (error) {
    console.error('Connection error:', error);
    if (room) {
      await disconnect();
    }
    throw error;
  }
}

async function disconnect() {
  if (localAudioTrack) {
    localAudioTrack.stop();
    localAudioTrack = null;
  }

  if (room) {
    await room.disconnect();
    room = null;
  }

  // Stop audio analysis
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
    analyser = null;
  }
  isSpeaking = false;

  // Remove all audio elements
  document.querySelectorAll('audio').forEach(el => el.remove());
}

// ========== AGENT TOGGLE ==========

async function toggleGrokie() {
  if (isAgentEnabled) {
    // Disable agent
    await disconnect();
    isAgentEnabled = false;
    toggleGrokieBtn.textContent = 'turn grokie on';
    toggleGrokieBtn.classList.remove('active');
  } else {
    // Enable agent
    try {
      await connect();
      isAgentEnabled = true;
      toggleGrokieBtn.textContent = 'turn grokie off';
      toggleGrokieBtn.classList.add('active');
    } catch (error) {
      console.error('Failed to connect:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      addChatMessage('assistant', `Failed to connect: ${errorMsg}`);
    }
  }
}

// ========== INITIALIZATION ==========

// Setup agent toggle
toggleGrokieBtn.addEventListener('click', toggleGrokie);

// Load chat history
loadChatHistory();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (room) {
    disconnect();
  }
});
