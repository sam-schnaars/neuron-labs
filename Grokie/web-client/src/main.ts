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
let remoteAudioSource: MediaStreamAudioSourceNode | null = null;

// Agent state
let isAgentEnabled = false;

// Default values
const DEFAULT_ROOM = 'test-room';
const DEFAULT_NAME = 'User';

// Get DOM elements
const toggleGrokieBtn = document.getElementById('toggleGrokieBtn') as HTMLButtonElement;
const statusIndicator = document.getElementById('statusIndicator') as HTMLElement;
const faceCircle = document.getElementById('faceCircle') as SVGCircleElement;
const leftEye = document.getElementById('leftEye') as SVGEllipseElement;
const rightEye = document.getElementById('rightEye') as SVGEllipseElement;
const mouth = document.getElementById('mouth') as SVGEllipseElement;
const profileContainer = document.getElementById('profileContainer') as HTMLElement;
const profileImage = document.getElementById('profileImage') as HTMLImageElement;
const profileName = document.getElementById('profileName') as HTMLElement;
const profileTitle = document.getElementById('profileTitle') as HTMLElement;
const profileLinkedIn = document.getElementById('profileLinkedIn') as HTMLAnchorElement;

// API base URL
const tokenServerUrl = import.meta.env.VITE_TOKEN_SERVER_URL || '/api';

// ========== FACE ANIMATION ==========

function updateStatus(status: string, connected: boolean) {
  statusIndicator.textContent = status;
  statusIndicator.className = `status-indicator ${connected ? 'connected' : 'disconnected'}`;
}

function animateFace(audioLevel: number) {
  // Normalize audio level (0-255 to 0-1)
  const normalizedLevel = Math.min(audioLevel / 255, 1);
  
  // Only animate if there's significant audio
  const threshold = 0.1;
  const isSpeaking = normalizedLevel > threshold;
  
  if (isSpeaking) {
    // Animate face based on audio level
    const scale = 1 + (normalizedLevel * 0.1); // Slight scale up when speaking
    faceCircle.style.transform = `scale(${scale})`;
    
    // Animate mouth based on audio level
    const mouthHeight = 8 + (normalizedLevel * 15); // Mouth opens more with louder audio
    const mouthWidth = 20 + (normalizedLevel * 10);
    mouth.setAttribute('ry', mouthHeight.toString());
    mouth.setAttribute('rx', mouthWidth.toString());
    
    // Blink eyes occasionally
    if (Math.random() < 0.05) {
      leftEye.classList.add('speaking');
      rightEye.classList.add('speaking');
      setTimeout(() => {
        leftEye.classList.remove('speaking');
        rightEye.classList.remove('speaking');
      }, 300);
    }
    
    // Add mouth animation class
    mouth.classList.add('speaking');
  } else {
    // Return to neutral state
    faceCircle.style.transform = 'scale(1)';
    mouth.setAttribute('ry', '8');
    mouth.setAttribute('rx', '20');
    mouth.classList.remove('speaking');
  }
}

function startAudioAnalysis(audioElement: HTMLAudioElement) {
  if (audioContext) {
    audioContext.close();
  }
  
  audioContext = new AudioContext();
  
  // Create analyser node
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.8;
  
  // Connect audio element to analyser
  try {
    const source = audioContext.createMediaElementSource(audioElement);
    source.connect(analyser);
    analyser.connect(audioContext.destination);
    remoteAudioSource = source;
  } catch (error) {
    console.error('Error creating audio source:', error);
    // Fallback: try to analyze the audio element directly
    if (audioElement.captureStream) {
      const stream = audioElement.captureStream();
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
    }
  }
  
  // Start animation loop
  const dataArray = new Uint8Array(analyser.frequencyBinCount);
  
  function analyzeAudio() {
    if (!analyser || !audioContext || audioContext.state === 'closed') {
      return;
    }
    
    analyser.getByteFrequencyData(dataArray);
    
    // Calculate average audio level
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const average = sum / dataArray.length;
    
    // Animate face
    animateFace(average);
    
    animationFrameId = requestAnimationFrame(analyzeAudio);
  }
  
  analyzeAudio();
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
    updateStatus('Connecting...', false);
    
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
      updateStatus('Connected', true);
      
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
      updateStatus('Disconnected', false);
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
        remoteAudioSource = null;
      }
      
      // Reset face to neutral
      faceCircle.style.transform = 'scale(1)';
      mouth.setAttribute('ry', '8');
      mouth.setAttribute('rx', '20');
      mouth.classList.remove('speaking');
    });

    room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
      console.log('Participant connected:', participant.identity);
      
      participant.on('trackSubscribed', (track) => {
        if (track.kind === 'audio' && track instanceof RemoteAudioTrack) {
          const audioElement = track.attach() as HTMLAudioElement;
          audioElement.style.display = 'none'; // Hide audio element
          document.body.appendChild(audioElement);
          audioElement.play().catch(console.error);
          
          // Start analyzing audio for face animation
          audioElement.addEventListener('playing', () => {
            startAudioAnalysis(audioElement);
          });
        }
      });
    });

    room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
      if (track.kind === 'audio' && participant !== room?.localParticipant && track instanceof RemoteAudioTrack) {
        const audioElement = track.attach() as HTMLAudioElement;
        audioElement.style.display = 'none'; // Hide audio element
        document.body.appendChild(audioElement);
        audioElement.play().catch(console.error);
        
        // Start analyzing audio for face animation
        audioElement.addEventListener('playing', () => {
          startAudioAnalysis(audioElement);
        });
      }
    });

    // Listen for data messages from the agent
    room.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
      console.log('📨 Data message received!', {
        participant: participant?.identity,
        kind,
        topic,
        payloadLength: payload.length
      });
      
      try {
        const data = JSON.parse(new TextDecoder().decode(payload));
        console.log('✅ Parsed data message:', data);
        
        if (data.type === 'show_profile') {
          console.log('🎯 Showing profile for:', data.name);
          showProfile(data);
        } else {
          console.log('⚠️ Unknown data message type:', data.type);
        }
      } catch (error) {
        console.error('❌ Error parsing data message:', error);
        console.error('Raw payload:', payload);
      }
    });

    // Generate token and connect
    const token = await generateToken(DEFAULT_ROOM, DEFAULT_NAME);
    await room.connect(LIVEKIT_URL, token, {
      autoSubscribe: true,
    });

  } catch (error) {
    console.error('Connection error:', error);
    updateStatus('Connection Failed', false);
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
    remoteAudioSource = null;
  }

  // Remove all audio elements
  document.querySelectorAll('audio').forEach(el => el.remove());
  
  // Reset face
  updateStatus('Disconnected', false);
  faceCircle.style.transform = 'scale(1)';
  mouth.setAttribute('ry', '8');
  mouth.setAttribute('rx', '20');
  mouth.classList.remove('speaking');
}

// ========== PROFILE DISPLAY ==========

function showProfile(profileData: {
  name: string;
  title: string;
  linkedin: string;
  image: string;
}) {
  console.log('🖼️ showProfile called with:', profileData);
  
  // Hide the face animation
  const faceWrapper = document.querySelector('.face-wrapper') as HTMLElement;
  if (faceWrapper) {
    faceWrapper.style.display = 'none';
    console.log('✅ Hidden face wrapper');
  }
  
  // Set profile data
  profileName.textContent = profileData.name;
  profileTitle.textContent = profileData.title;
  profileLinkedIn.href = profileData.linkedin;
  console.log('✅ Set profile text data');
  
  // Load image - try multiple paths
  const imagePaths = [
    profileData.image,
    `/keith-pic.jpeg`,  // Direct server endpoint
    `http://localhost:8080/keith-pic.jpeg`,  // Server endpoint with port
    `../${profileData.image}`,
    `../../${profileData.image}`,
    `./${profileData.image}`,
  ];
  
  // Try to load image from various paths
  const tryLoadImage = (pathIndex: number) => {
    if (pathIndex >= imagePaths.length) {
      console.warn('Could not load profile image from any path');
      profileImage.style.display = 'none';
      return;
    }
    
    const img = new Image();
    img.onload = () => {
      profileImage.src = img.src;
      profileImage.style.display = 'block';
      console.log('✅ Profile image loaded from:', img.src);
    };
    img.onerror = () => {
      console.warn('❌ Failed to load image from:', imagePaths[pathIndex]);
      tryLoadImage(pathIndex + 1);
    };
    console.log(`🖼️ Trying to load image from: ${imagePaths[pathIndex]}`);
    img.src = imagePaths[pathIndex];
  };
  
  tryLoadImage(0);
  
  // Show profile container
  profileContainer.classList.add('visible');
  console.log('✅ Profile container made visible');
  console.log('📋 Final profile data:', {
    name: profileName.textContent,
    title: profileTitle.textContent,
    linkedin: profileLinkedIn.href,
    imageSrc: profileImage.src
  });
}

function hideProfile() {
  profileContainer.classList.remove('visible');
  
  // Show the face animation again
  const faceWrapper = document.querySelector('.face-wrapper') as HTMLElement;
  if (faceWrapper) {
    faceWrapper.style.display = 'flex';
  }
}

// ========== AGENT TOGGLE ==========

async function toggleGrokie() {
  if (isAgentEnabled) {
    // Disable agent
    await disconnect();
    isAgentEnabled = false;
    toggleGrokieBtn.textContent = 'turn grokie';
    toggleGrokieBtn.classList.remove('active');
  } else {
    // Enable agent
    try {
      await connect();
      isAgentEnabled = true;
      toggleGrokieBtn.textContent = 'turn ';
      toggleGrokieBtn.classList.add('active');
    } catch (error) {
      console.error('Failed to connect:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      updateStatus(`Connection Failed: ${errorMsg}`, false);
    }
  }
}

// ========== INITIALIZATION ==========

// Setup agent toggle
toggleGrokieBtn.addEventListener('click', toggleGrokie);

// Initialize status
updateStatus('Disconnected', false);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (room) {
    disconnect();
  }
});
