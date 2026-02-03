import { Room, RoomEvent, RemoteAudioTrack, LocalAudioTrack, createLocalAudioTrack } from 'livekit-client';

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
let isConnecting = false;
let isDisconnecting = false;

// Default values - use unique room per connection so agent is dispatched every time (room_config is applied when room is created)
const DEFAULT_NAME = 'User';

function getRoomName(): string {
  return `investobot-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

// Get DOM elements
const toggleGrokieBtn = document.getElementById('toggleGrokieBtn') as HTMLButtonElement;
const statusIndicator = document.getElementById('statusIndicator') as HTMLElement;
const faceCircle = document.getElementById('faceCircle') as SVGCircleElement;
const leftEye = document.getElementById('leftEye') as SVGEllipseElement;
const rightEye = document.getElementById('rightEye') as SVGEllipseElement;
const mouth = document.getElementById('mouth') as SVGEllipseElement;

// API base URL
const tokenServerUrl = import.meta.env.VITE_TOKEN_SERVER_URL || '/api';
const apiBase = tokenServerUrl.replace(/\/token$/, '').replace(/\/$/, '') || '/api';

// Views
const homeView = document.getElementById('homeView') as HTMLElement;
const pitchDetailView = document.getElementById('pitchDetailView') as HTMLElement;
const sessionView = document.getElementById('sessionView') as HTMLElement;
const pitchesList = document.getElementById('pitchesList') as HTMLUListElement;
const pitchContent = document.getElementById('pitchContent') as HTMLPreElement;
const pitchContactLine = document.getElementById('pitchContactLine') as HTMLElement | null;
const btnPitchInvestobot = document.getElementById('btnPitchInvestobot') as HTMLButtonElement;
const btnBackFromPitch = document.getElementById('btnBackFromPitch') as HTMLButtonElement;
const btnBackToPitches = document.getElementById('btnBackToPitches') as HTMLButtonElement;
const rubricView = document.getElementById('rubricView') as HTMLElement;
const btnBackFromRubric = document.getElementById('btnBackFromRubric') as HTMLButtonElement;
const btnStartPitch = document.getElementById('btnStartPitch') as HTMLButtonElement;
const pitchTimerBar = document.getElementById('pitchTimerBar') as HTMLElement;
const pitchTimer = document.getElementById('pitchTimer') as HTMLElement;
const pitchTimerInstruction = document.getElementById('pitchTimerInstruction') as HTMLElement;
const scoreSheetOverlay = document.getElementById('scoreSheetOverlay') as HTMLElement;
const scoreSheetDescription = document.getElementById('scoreSheetDescription') as HTMLElement;
const scoreSheetTotal = document.getElementById('scoreSheetTotal') as HTMLElement;
const scoreSheetRubric = document.getElementById('scoreSheetRubric') as HTMLPreElement;
const btnDoneScore = document.getElementById('btnDoneScore') as HTMLButtonElement;
const shareContactCheckbox = document.getElementById('shareContactCheckbox') as HTMLInputElement | null;
const shareContactEmailWrap = document.getElementById('shareContactEmailWrap') as HTMLElement | null;
const shareContactEmail = document.getElementById('shareContactEmail') as HTMLInputElement | null;
const shareContactStatus = document.getElementById('shareContactStatus') as HTMLElement | null;




let pitchTimerIntervalId: ReturnType<typeof setInterval> | null = null;
const PITCH_TIMER_SECONDS = 63;
let currentRoomName: string | null = null;

type View = 'home' | 'pitch' | 'session' | 'rubric';

function showView(view: View) {
  homeView?.classList.toggle('active', view === 'home');
  pitchDetailView?.classList.toggle('active', view === 'pitch');
  sessionView?.classList.toggle('active', view === 'session');
  rubricView?.classList.toggle('active', view === 'rubric');
}

type PitchItem = { id: string; sessionId: string; filename: string; description: string; score?: number; rubric?: string; savedAt?: string };

async function loadPitches(): Promise<PitchItem[]> {
  try {
    const res = await fetch(`${apiBase}/pitches`);
    const data = await res.json();
    return (data.pitches ?? []) as PitchItem[];
  } catch (e) {
    console.error('Failed to load pitches:', e);
    return [];
  }
}

function renderPitchesList(items: PitchItem[]) {
  if (!pitchesList) return;
  if (items.length === 0) {
    pitchesList.innerHTML = '<li class="empty">No saved pitches yet. Click "Pitch Investobot" to start.</li>';
    return;
  }
  pitchesList.innerHTML = items
    .map((p) => {
      const label = p.description || p.filename.replace(/^pitch_|\.md$/g, '').replace(/_/g, ' ') || 'Pitch';
      const safeLabel = escapeHtml(label);
      const scoreBadge =
        typeof p.score === 'number'
          ? p.score <= 5
            ? `<span class="pitch-score">${Number(p.score).toFixed(1)}/5</span>`
            : `<span class="pitch-score">${Math.round(p.score * 100)}</span>`
          : '';
      return `<li data-id="${p.id}" data-session="${p.sessionId}" data-filename="${p.filename}">${scoreBadge}<div class="pitch-content-wrap"><span class="pitch-label">${safeLabel}</span></div></li>`;
    })
    .join('');
  pitchesList.querySelectorAll('li[data-id]').forEach((el) => {
    el.addEventListener('click', () => {
      const session = (el as HTMLElement).dataset.session;
      const filename = (el as HTMLElement).dataset.filename;
      if (session && filename) openPitch(session, filename);
    });
  });
}

function escapeHtml(s: string): string {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function extractContactFromPitchText(text: string): string | null {
  const m = text.match(/^contact:\s*(.+)$/m);
  return m ? m[1].trim() : null;
}

async function openPitch(sessionId: string, filename: string) {
  try {
    const res = await fetch(`${apiBase}/pitch?session=${encodeURIComponent(sessionId)}&filename=${encodeURIComponent(filename)}`);
    const text = await res.text();
    if (!res.ok) throw new Error(text || 'Failed to load pitch');
    if (pitchContent) {
      pitchContent.textContent = text;
      showView('pitch');
    }
    const contact = extractContactFromPitchText(text);
    if (pitchContactLine) {
      if (contact) {
        pitchContactLine.innerHTML = `<strong>Contact:</strong> ${escapeHtml(contact)}`;
        pitchContactLine.removeAttribute('aria-hidden');
      } else {
        pitchContactLine.textContent = '';
        pitchContactLine.setAttribute('aria-hidden', 'true');
      }
    }
  } catch (e) {
    console.error('Failed to load pitch:', e);
    if (pitchContent) pitchContent.textContent = 'Failed to load this pitch.';
    if (pitchContactLine) {
      pitchContactLine.textContent = '';
      pitchContactLine.setAttribute('aria-hidden', 'true');
    }
    showView('pitch');
  }
}

function formatPitchTimer(seconds: number): string {
  if (seconds >= 0) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
  const abs = Math.abs(seconds);
  const m = Math.floor(abs / 60);
  const s = abs % 60;
  return `-${m}:${s.toString().padStart(2, '0')}`;
}

function startPitchTimer() {
  stopPitchTimer();
  if (pitchTimerBar) pitchTimerBar.removeAttribute('aria-hidden');
  let remaining = PITCH_TIMER_SECONDS;
  const tick = () => {
    if (!pitchTimer) return;
    pitchTimer.textContent = formatPitchTimer(remaining);
    pitchTimer.classList.toggle('negative', remaining < 0);
    remaining -= 1;
  };
  tick();
  pitchTimerIntervalId = setInterval(tick, 1000);
}

function stopPitchTimer() {
  if (pitchTimerIntervalId !== null) {
    clearInterval(pitchTimerIntervalId);
    pitchTimerIntervalId = null;
  }
  if (pitchTimerBar) {
    pitchTimerBar.setAttribute('aria-hidden', 'true');
  }
}

function showScoreSheet(description: string, score: number, rubric: string) {
  if (scoreSheetDescription) scoreSheetDescription.textContent = description;
  if (scoreSheetTotal) {
    scoreSheetTotal.textContent = score <= 5 ? `${Number(score).toFixed(1)}/5` : `${Math.round(score * 100)}`;
  }
  if (scoreSheetRubric) scoreSheetRubric.textContent = rubric || '—';
  if (scoreSheetOverlay) {
    scoreSheetOverlay.removeAttribute('aria-hidden');
    scoreSheetOverlay.classList.add('active');
  }
  // Reset share-contact form for this pitch
  if (shareContactCheckbox) shareContactCheckbox.checked = false;
  if (shareContactEmail) shareContactEmail.value = '';
  setShareContactStatus('');
  shareContactEmailWrap?.classList.remove('visible');
}

function hideScoreSheet() {
  if (scoreSheetOverlay) {
    scoreSheetOverlay.setAttribute('aria-hidden', 'true');
    scoreSheetOverlay.classList.remove('active');
  }
}

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
    
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const average = sum / dataArray.length;
    
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

async function connect(roomNameOverride?: string) {
  if (isConnecting || isAgentEnabled) return;
  isConnecting = true;
  toggleGrokieBtn.disabled = true;

  try {
    if (room) {
      await disconnect();
      await new Promise((r) => setTimeout(r, 500));
    }

    updateStatus('Connecting...', false);

    const stream = await requestMicrophonePermission();
    stream.getTracks().forEach((track) => track.stop());

    const newRoom = new Room({
      adaptiveStream: true,
      dynacast: true,
    });
    room = newRoom;

    newRoom.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
      if (room !== newRoom) return;
      try {
        const str = new TextDecoder().decode(payload);
        const msg = JSON.parse(str) as { type?: string; description?: string; score?: number; rubric?: string };
        if (msg.type === 'pitch_saved') {
          showScoreSheet(msg.description ?? '—', msg.score ?? 0, msg.rubric ?? '');
        }
      } catch (_e) { /* ignore */ }
    });

    newRoom.on(RoomEvent.Connected, async () => {
      console.log('Connected to room:', newRoom.name);
      if (room !== newRoom) return;
      updateStatus('Connected', true);
      
      try {
        localAudioTrack = await createLocalAudioTrack();
        if (room !== newRoom) {
          localAudioTrack?.stop();
          localAudioTrack = null;
          return;
        }
        await newRoom.localParticipant.publishTrack(localAudioTrack!);
        console.log('Microphone track published');
      } catch (error) {
        console.error('Error publishing microphone:', error);
      }
    });

    newRoom.on(RoomEvent.Disconnected, () => {
      if (room !== newRoom) return;
      console.log('Disconnected from room');
      updateStatus('Disconnected', false);
      localAudioTrack = null;
      
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
      
      faceCircle.style.transform = 'scale(1)';
      mouth.setAttribute('ry', '8');
      mouth.setAttribute('rx', '20');
      mouth.classList.remove('speaking');
    });

    newRoom.on(RoomEvent.TrackSubscribed, (track, _publication) => {
      if (track.kind === 'audio' && track instanceof RemoteAudioTrack) {
        const audioElement = track.attach() as HTMLAudioElement;
        audioElement.style.display = 'none';
        document.body.appendChild(audioElement);
        audioElement.play().catch(console.error);
        
        audioElement.addEventListener('playing', () => {
          startAudioAnalysis(audioElement);
        });
      }
    });

    const roomName = roomNameOverride ?? getRoomName();
    currentRoomName = roomName;
    const token = await generateToken(roomName, DEFAULT_NAME);
    await newRoom.connect(LIVEKIT_URL, token, {
      autoSubscribe: true,
    });
  } catch (error) {
    console.error('Connection error:', error);
    updateStatus('Connection Failed', false);
    if (room) {
      try {
        await disconnect();
      } catch (e) {
        console.error('Cleanup disconnect error:', e);
      }
    }
    throw error;
  } finally {
    isConnecting = false;
    toggleGrokieBtn.disabled = false;
  }
}

async function disconnect() {
  if (isDisconnecting) return;
  isDisconnecting = true;

  const roomToDisconnect = room;
  const trackToStop = localAudioTrack;
  room = null;
  currentRoomName = null;
  localAudioTrack = null;
  stopPitchTimer();

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

  document.querySelectorAll('audio').forEach(el => el.remove());
  updateStatus('Disconnected', false);
  faceCircle.style.transform = 'scale(1)';
  mouth.setAttribute('ry', '8');
  mouth.setAttribute('rx', '20');
  mouth.classList.remove('speaking');

  try {
    if (trackToStop) trackToStop.stop();
  } catch (e) {
    console.error('Error stopping track:', e);
  }
  try {
    if (roomToDisconnect) await roomToDisconnect.disconnect();
  } catch (e) {
    console.error('Error disconnecting room:', e);
  } finally {
    isDisconnecting = false;
  }
}

// ========== AGENT TOGGLE ==========

async function toggleGrokie() {
  if (isAgentEnabled) {
    if (isConnecting) return;
    toggleGrokieBtn.disabled = true;
    try {
      await disconnect();
      await new Promise((r) => setTimeout(r, 400));
    } catch (e) {
      console.error('Disconnect error:', e);
    } finally {
      isAgentEnabled = false;
      toggleGrokieBtn.textContent = 'Talk to Investobot';
      toggleGrokieBtn.classList.remove('active');
      toggleGrokieBtn.disabled = false;
    }
  } else {
    try {
      await connect();
      isAgentEnabled = true;
      toggleGrokieBtn.textContent = 'End session';
      toggleGrokieBtn.classList.add('active');
    } catch (error) {
      console.error('Failed to connect:', error);
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      updateStatus(`Connection Failed: ${errorMsg}`, false);
    }
  }
}

// ========== VIEW NAVIGATION ==========

function goHome() {
  if (isAgentEnabled) {
    disconnect().then(() => {
      isAgentEnabled = false;
      if (toggleGrokieBtn) {
        toggleGrokieBtn.textContent = 'Talk to Investobot';
        toggleGrokieBtn.classList.remove('active');
      }
      showView('home');
      loadPitches().then(renderPitchesList);
    }).catch(console.error);
  } else {
    showView('home');
    loadPitches().then(renderPitchesList);
  }
}

function isValidEmail(s: string): boolean {
  const trimmed = (s || '').trim();
  return trimmed.length > 0 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);
}

function setShareContactStatus(message: string, isError = false) {
  if (!shareContactStatus) return;
  shareContactStatus.textContent = message;
  shareContactStatus.classList.toggle('error', isError);
}

async function submitShareContact(email: string, roomName: string): Promise<boolean> {
  try {
    const res = await fetch(`${apiBase}/share-contact`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), room: roomName }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { error?: string }).error || `Request failed: ${res.status}`);
    }
    return true;
  } catch (e) {
    console.error('Failed to share contact:', e);
    return false;
  }
}

async function startPitchSession() {
  const roomName = getRoomName();
  showView('session');
  startPitchTimer();
  updateStatus('Connecting...', false);
  try {
    await connect(roomName);
    isAgentEnabled = true;
    if (toggleGrokieBtn) {
      toggleGrokieBtn.textContent = 'End session';
      toggleGrokieBtn.classList.add('active');
    }
  } catch (e) {
    console.error('Failed to connect:', e);
    const msg = e instanceof Error ? e.message : 'Connection failed';
    updateStatus(msg, false);
    if (toggleGrokieBtn) {
      toggleGrokieBtn.textContent = 'Talk to Investobot';
      toggleGrokieBtn.classList.remove('active');
    }
  }
}

// ========== LAYOUT MODE (portrait / landscape) ==========

const LAYOUT_STORAGE_KEY = 'vesty-layout';
const layoutToggle = document.getElementById('layoutToggle');
type LayoutMode = 'portrait' | 'landscape';

function getLayoutMode(): LayoutMode {
  const saved = localStorage.getItem(LAYOUT_STORAGE_KEY);
  return saved === 'portrait' ? 'portrait' : 'landscape';
}

function setLayoutMode(mode: LayoutMode) {
  document.body.setAttribute('data-layout', mode);
  localStorage.setItem(LAYOUT_STORAGE_KEY, mode);
  if (layoutToggle) {
    layoutToggle.title = mode === 'portrait'
      ? 'Back to normal (landscape)'
      : 'Rotate for portrait — flip laptop 90° to view upright';
    layoutToggle.setAttribute('aria-label', mode === 'portrait'
      ? 'Layout: rotated for portrait. Click to return to normal.'
      : 'Layout: normal. Click to rotate for viewing with laptop flipped to portrait.');
  }
}

function initLayoutMode() {
  setLayoutMode(getLayoutMode());
}
layoutToggle?.addEventListener('click', () => {
  setLayoutMode(getLayoutMode() === 'landscape' ? 'portrait' : 'landscape');
});

// ========== INITIALIZATION ==========

initLayoutMode();
showView('home');
loadPitches().then(renderPitchesList);

btnPitchInvestobot?.addEventListener('click', () => showView('rubric'));
btnBackFromRubric?.addEventListener('click', () => showView('home'));
shareContactCheckbox?.addEventListener('change', () => {
  shareContactEmailWrap?.classList.toggle('visible', shareContactCheckbox.checked);
  if (!shareContactCheckbox.checked) setShareContactStatus('');
});
btnStartPitch?.addEventListener('click', startPitchSession);
btnBackFromPitch?.addEventListener('click', () => { showView('home'); loadPitches().then(renderPitchesList); });
btnBackToPitches?.addEventListener('click', goHome);
btnDoneScore?.addEventListener('click', async () => {
  if (shareContactCheckbox?.checked) {
    const email = shareContactEmail?.value?.trim() ?? '';
    if (!isValidEmail(email)) {
      setShareContactStatus('Please enter a valid email address.', true);
      return;
    }
    if (!currentRoomName) {
      setShareContactStatus('Session ended. Contact could not be saved.', true);
      return;
    }
    setShareContactStatus('Saving…');
    const ok = await submitShareContact(email, currentRoomName);
    if (!ok) {
      setShareContactStatus('Could not save. Try again or continue.', true);
      return;
    }
  }
  hideScoreSheet();
  goHome();
});

toggleGrokieBtn?.addEventListener('click', toggleGrokie);

updateStatus('Disconnected', false);

window.addEventListener('beforeunload', () => {
  if (room) {
    disconnect();
  }
});
