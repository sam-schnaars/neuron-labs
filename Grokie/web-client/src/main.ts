import { Room, RoomEvent, RemoteParticipant, LocalAudioTrack, RemoteAudioTrack, createLocalAudioTrack } from 'livekit-client';

// Configuration - update these to match your LiveKit server
const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL || 'ws://localhost:7880';
const LIVEKIT_API_KEY = import.meta.env.VITE_LIVEKIT_API_KEY || 'devkey';
const LIVEKIT_API_SECRET = import.meta.env.VITE_LIVEKIT_API_SECRET || 'secret';

let room: Room | null = null;
let localAudioTrack: LocalAudioTrack | null = null;
let audioContext: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let animationFrameId: number | null = null;
let isSpeaking = false;

// Session tracking for billing
let sessionStartTime: number | null = null;
let sessionTimerInterval: number | null = null;
const COST_PER_MINUTE = 0.05; // $0.05 per minute

// Get DOM elements
const statusEl = document.getElementById('status')!;
const statusTextEl = document.getElementById('statusText')!;
const connectBtn = document.getElementById('connectBtn') as HTMLButtonElement;
const disconnectBtn = document.getElementById('disconnectBtn') as HTMLButtonElement;
const infoEl = document.getElementById('info')!;
const faceCanvas = document.getElementById('faceCanvas') as HTMLCanvasElement;
const ctx = faceCanvas.getContext('2d')!;
const billingInfoEl = document.getElementById('billingInfo')!;
const sessionTimeEl = document.getElementById('sessionTime')!;
const sessionCostEl = document.getElementById('sessionCost')!;

// Default values
const DEFAULT_ROOM = 'test-room';
const DEFAULT_NAME = 'User';

// Face drawing constants
const CANVAS_SIZE = 280;
const CENTER_X = CANVAS_SIZE / 2;
const CENTER_Y = CANVAS_SIZE / 2;
const EYE_RADIUS = 12;
const EYE_Y = CENTER_Y - 50;
const LEFT_EYE_X = CENTER_X - 40;
const RIGHT_EYE_X = CENTER_X + 40;
const MOUTH_CENTER_X = CENTER_X + 5; // Slightly to the right
const MOUTH_CENTER_Y = CENTER_Y + 40;
const MOUTH_WIDTH = 80;
const MOUTH_HEIGHT = 40;
const MOUTH_CURVE = 0.5; // Base curve for the smile

// Draw the smiley face
function drawFace(mouthOpenness: number = 0) {
  // Clear canvas
  ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
  
  // Draw background (dark teal circle)
  ctx.fillStyle = '#1a4d5e';
  ctx.beginPath();
  ctx.arc(CENTER_X, CENTER_Y, CANVAS_SIZE / 2, 0, Math.PI * 2);
  ctx.fill();
  
  // Draw eyes (white circles)
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.arc(LEFT_EYE_X, EYE_Y, EYE_RADIUS, 0, Math.PI * 2);
  ctx.fill();
  
  ctx.beginPath();
  ctx.arc(RIGHT_EYE_X, EYE_Y, EYE_RADIUS, 0, Math.PI * 2);
  ctx.fill();
  
  // Draw mouth (animated curved line)
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 8;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  
  // Calculate mouth curve based on speaking
  // When speaking, the mouth opens wider (more curve variation)
  const curveVariation = mouthOpenness * 0.6; // Max 60% variation for more visible animation
  const currentCurve = MOUTH_CURVE + curveVariation;
  
  // Draw curved smile
  ctx.beginPath();
  const startX = MOUTH_CENTER_X - MOUTH_WIDTH / 2;
  const endX = MOUTH_CENTER_X + MOUTH_WIDTH / 2;
  const controlY = MOUTH_CENTER_Y - (MOUTH_HEIGHT * currentCurve);
  
  ctx.moveTo(startX, MOUTH_CENTER_Y);
  ctx.quadraticCurveTo(MOUTH_CENTER_X, controlY, endX, MOUTH_CENTER_Y);
  ctx.stroke();
}

// Initialize face drawing
drawFace();

// Analyze audio and update mouth animation
function analyzeAudio() {
  if (!analyser || !audioContext || audioContext.state === 'closed') {
    return;
  }
  
  // Resume if suspended
  if (audioContext.state === 'suspended') {
    audioContext.resume().catch(console.error);
  }
  
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  analyser.getByteTimeDomainData(dataArray); // Use time domain for better speech detection
  
  // Calculate RMS (Root Mean Square) for volume detection
  let sum = 0;
  for (let i = 0; i < bufferLength; i++) {
    const normalized = (dataArray[i] - 128) / 128;
    sum += normalized * normalized;
  }
  const rms = Math.sqrt(sum / bufferLength);
  
  // Convert RMS to a 0-1 range, with threshold for speech detection
  const normalized = Math.min(rms * 15, 1); // Scale factor for better sensitivity
  isSpeaking = normalized > 0.03; // Lower threshold for better sensitivity
  
  // Debug logging (can be removed later)
  if (normalized > 0.05) {
    console.log('Audio detected:', { rms, normalized, isSpeaking });
  }
  
  // Smooth mouth animation with more responsive smoothing
  const targetOpenness = isSpeaking ? Math.min(normalized * 1.5, 1) : 0;
  const currentOpenness = parseFloat(faceCanvas.dataset.mouthOpenness || '0');
  const smoothedOpenness = currentOpenness * 0.6 + targetOpenness * 0.4; // More responsive
  
  faceCanvas.dataset.mouthOpenness = smoothedOpenness.toString();
  
  drawFace(smoothedOpenness);
  
  animationFrameId = requestAnimationFrame(analyzeAudio);
}

// Setup audio analysis for remote audio track using MediaStreamTrack
function setupAudioAnalysis(track: RemoteAudioTrack) {
  // Only setup once
  if (analyser && audioContext && audioContext.state !== 'closed') {
    console.log('Audio analysis already set up');
    return;
  }
  
  // Clean up existing context if needed
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close();
  }
  
  try {
    audioContext = new AudioContext();
    console.log('AudioContext created, state:', audioContext.state);
    
    // Resume audio context if suspended (browser autoplay policy)
    if (audioContext.state === 'suspended') {
      audioContext.resume().then(() => {
        console.log('AudioContext resumed');
      }).catch(console.error);
    }
    
    // Get the MediaStreamTrack from the RemoteAudioTrack
    const mediaStreamTrack = track.mediaStreamTrack;
    if (!mediaStreamTrack) {
      console.error('No MediaStreamTrack available');
      return;
    }
    
    // Create a MediaStream from the track
    const mediaStream = new MediaStream([mediaStreamTrack]);
    
    // Create source from MediaStream
    const source = audioContext.createMediaStreamSource(mediaStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.3; // Lower for more responsive animation
    
    source.connect(analyser);
    // Don't connect to destination to avoid feedback
    
    console.log('Audio analysis setup complete');
    
    // Start animation loop
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
    }
    analyzeAudio();
  } catch (error) {
    console.error('Error setting up audio analysis:', error);
  }
}

// Update status display
function updateStatus(status: 'disconnected' | 'connecting' | 'connected', message: string) {
  statusEl.className = `status ${status}`;
  statusTextEl.textContent = message;
}

// Format time as MM:SS
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Start session timer
function startSessionTimer() {
  sessionStartTime = Date.now();
  billingInfoEl.style.display = 'block';
  
  // Update every second
  sessionTimerInterval = window.setInterval(() => {
    if (sessionStartTime) {
      const elapsedSeconds = (Date.now() - sessionStartTime) / 1000;
      const elapsedMinutes = elapsedSeconds / 60;
      const cost = elapsedMinutes * COST_PER_MINUTE;
      
      sessionTimeEl.textContent = formatTime(elapsedSeconds);
      sessionCostEl.textContent = cost.toFixed(2);
    }
  }, 1000);
}

// Stop session timer
function stopSessionTimer() {
  if (sessionTimerInterval) {
    clearInterval(sessionTimerInterval);
    sessionTimerInterval = null;
  }
  
  // Show final cost
  if (sessionStartTime) {
    const elapsedSeconds = (Date.now() - sessionStartTime) / 1000;
    const elapsedMinutes = elapsedSeconds / 60;
    const cost = elapsedMinutes * COST_PER_MINUTE;
    
    infoEl.innerHTML = `
      <strong>✅ Session ended!</strong><br>
      Duration: ${formatTime(elapsedSeconds)} | Cost: ~$${cost.toFixed(2)}<br><br>
      <strong>💡 Billing Info:</strong><br>
      • You are charged <strong>$0.05/minute</strong> while connected<br>
      • Click "Stop Session" when done to save credits<br>
      • The timer shows your current session cost
    `;
  }
  
  sessionStartTime = null;
  billingInfoEl.style.display = 'none';
  sessionTimeEl.textContent = '0:00';
  sessionCostEl.textContent = '0.00';
}

// Generate access token from backend server
async function generateToken(roomName: string, participantName: string): Promise<string> {
  // Use proxy in dev, or direct URL in production
  const tokenServerUrl = import.meta.env.VITE_TOKEN_SERVER_URL || '/api';
  const tokenEndpoint = `${tokenServerUrl}/token`;
  
  console.log('Requesting token from:', tokenEndpoint);
  console.log('Request body:', { room: roomName, name: participantName });
  
  try {
    const response = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ room: roomName, name: participantName })
    });
    
    console.log('Response status:', response.status, response.statusText);
    console.log('Response headers:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = 'Failed to generate token';
      try {
        const error = JSON.parse(errorText);
        errorMessage = error.error || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    console.log('Token response:', { hasToken: !!data.token, tokenType: typeof data.token, tokenLength: data.token?.length });
    
    if (!data.token) {
      console.error('No token in response:', data);
      throw new Error('Server did not return a token. Response: ' + JSON.stringify(data));
    }
    
    if (typeof data.token !== 'string') {
      console.error('Token is not a string:', typeof data.token, data);
      throw new Error(`Invalid token format: expected string, got ${typeof data.token}. Response: ${JSON.stringify(data)}`);
    }
    
    if (data.token.length < 10) {
      console.error('Token seems too short:', data.token);
      throw new Error('Token appears to be invalid (too short)');
    }
    
    console.log('Token received successfully, length:', data.token.length);
    return data.token;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Cannot reach token server. Make sure the server is running on port 8080 (run: npm run server)');
    }
    throw error;
  }
}

// Request microphone permission first
async function requestMicrophonePermission(): Promise<MediaStream> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return stream;
  } catch (error) {
    console.error('Microphone permission denied:', error);
    throw new Error('Microphone access is required. Please allow microphone access and try again.');
  }
}

// Connect to room
async function connect() {
  try {
    updateStatus('connecting', 'Requesting microphone access...');
    connectBtn.disabled = true;
    infoEl.innerHTML = '<strong>Please allow microphone access when prompted...</strong>';

    // Request microphone permission first - this will show the browser prompt
    const stream = await requestMicrophonePermission();
    
    // Stop the stream immediately - we'll create the track properly after connecting
    stream.getTracks().forEach(track => track.stop());

    updateStatus('connecting', 'Connecting to agent...');
    infoEl.innerHTML = '<strong>Connecting to GROK agent...</strong>';

    // Create room instance
    room = new Room({
      adaptiveStream: true,
      dynacast: true,
    });

    // Set up event handlers
    room.on(RoomEvent.Connected, async () => {
      updateStatus('connected', '🔴 LIVE - Billing Active');
      connectBtn.disabled = true;
      disconnectBtn.disabled = false;
      connectBtn.classList.add('talking');
      infoEl.innerHTML = '<strong>🎤 You\'re connected! Start speaking - GROK will respond.</strong><br><br><span style="color: #856404;">💰 You are being charged $0.05/min while connected.</span>';
      console.log('Connected to room:', DEFAULT_ROOM);
      
      // Start billing timer
      startSessionTimer();

      // Now create and publish microphone track after connection
      try {
        localAudioTrack = await createLocalAudioTrack();
        await room!.localParticipant.publishTrack(localAudioTrack);
        console.log('Microphone track published');
      } catch (error) {
        console.error('Error publishing microphone:', error);
        updateStatus('connected', 'Connected but microphone error');
        infoEl.innerHTML = '<strong style="color: #c33;">Connected but microphone failed. Please refresh and try again.</strong>';
      }
    });

    room.on(RoomEvent.Disconnected, () => {
      updateStatus('disconnected', 'Disconnected - Not Billing');
      connectBtn.disabled = false;
      disconnectBtn.disabled = true;
      connectBtn.classList.remove('talking');
      localAudioTrack = null;
      console.log('Disconnected from room');
      
      // Stop billing timer
      stopSessionTimer();
      
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
      drawFace(0); // Reset to default smile
    });

    room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
      console.log('Participant connected:', participant.identity);
      
      // When agent connects, set up audio playback
      participant.on('trackSubscribed', (track) => {
        if (track.kind === 'audio' && track instanceof RemoteAudioTrack) {
          const audioElement = track.attach() as HTMLAudioElement;
          document.body.appendChild(audioElement);
          audioElement.play().catch(console.error);
          // Setup audio analysis for mouth animation using the track directly
          setupAudioAnalysis(track);
        }
      });
    });

    room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
      if (track.kind === 'audio' && participant !== room?.localParticipant && track instanceof RemoteAudioTrack) {
        const audioElement = track.attach() as HTMLAudioElement;
        document.body.appendChild(audioElement);
        audioElement.play().catch(console.error);
        // Setup audio analysis for mouth animation using the track directly
        console.log('Setting up audio analysis for remote track');
        setupAudioAnalysis(track);
      }
    });

    // Generate token and connect
    updateStatus('connecting', 'Generating access token...');
    const token = await generateToken(DEFAULT_ROOM, DEFAULT_NAME);
    
    // Ensure token is a string
    if (typeof token !== 'string' || !token) {
      throw new Error('Invalid token received from server');
    }
    
    console.log('Token generated, connecting to:', LIVEKIT_URL);
    updateStatus('connecting', 'Connecting to LiveKit server...');
    
    await room.connect(LIVEKIT_URL, token, {
      autoSubscribe: true,
    });

  } catch (error) {
    console.error('Connection error:', error);
    updateStatus('disconnected', 'Connection failed');
    connectBtn.disabled = false;
    connectBtn.classList.remove('talking');
    
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    
    let troubleshooting = 'Make sure:<br>';
    if (errorMessage.includes('token server')) {
      troubleshooting += '1. Token server is running (npm run server in web-client folder)<br>';
    }
    troubleshooting += '2. LiveKit server is running (livekit-server --dev)<br>';
    troubleshooting += '3. GROK agent is running (python grok_voice_agent.py)';
    
    infoEl.innerHTML = `<strong style="color: #c33;">Connection failed: ${errorMessage}</strong><br>${troubleshooting}`;
    
    if (room) {
      await disconnect();
    }
  }
}

// Disconnect from room
async function disconnect() {
  // Stop billing timer first
  stopSessionTimer();
  
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
  drawFace(0); // Reset to default smile

  // Remove all audio elements
  document.querySelectorAll('audio').forEach(el => el.remove());
  
  // Update UI
  updateStatus('disconnected', 'Disconnected - Not Billing');
  connectBtn.disabled = false;
  disconnectBtn.disabled = true;
}

// Event listeners
connectBtn.addEventListener('click', connect);
disconnectBtn.addEventListener('click', disconnect);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  disconnect();
});

