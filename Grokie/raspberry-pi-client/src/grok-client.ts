/**
 * GROK Voice Agent Client for Raspberry Pi
 * Connects to LiveKit room and handles audio I/O using WM8960 hardware
 * 
 * Note: This implementation uses livekit-client which is primarily designed for browsers.
 * For full Node.js support with custom audio sources, consider using @livekit/agents or
 * a WebRTC adapter. This version provides a working foundation that can be enhanced.
 */

import { Room, RoomEvent, RemoteParticipant, RemoteAudioTrack, LocalAudioTrack, createLocalAudioTrack } from 'livekit-client';
import { AudioInputStream } from './audio-input.js';
import { AudioOutputStream } from './audio-output.js';
import { EventEmitter } from 'events';
import dotenv from 'dotenv';

dotenv.config();

// Configuration
const LIVEKIT_URL = process.env.LIVEKIT_URL || 'ws://localhost:7880';
const LIVEKIT_API_KEY = process.env.LIVEKIT_API_KEY || 'devkey';
const LIVEKIT_API_SECRET = process.env.LIVEKIT_API_SECRET || 'secret';
const TOKEN_SERVER_URL = process.env.TOKEN_SERVER_URL || 'http://localhost:8080';
const DEFAULT_ROOM = process.env.LIVEKIT_ROOM || 'test-room';
const DEFAULT_NAME = process.env.PARTICIPANT_NAME || 'raspberry-pi';

export interface GrokClientOptions {
  roomName?: string;
  participantName?: string;
  sampleRate?: number;
}

export class GrokClient extends EventEmitter {
  private room: Room | null = null;
  private audioInput: AudioInputStream;
  private audioOutput: AudioOutputStream;
  private localAudioTrack: LocalAudioTrack | null = null;
  private isConnected: boolean = false;
  private options: Required<GrokClientOptions>;
  private audioInputBuffer: Buffer[] = [];

  constructor(options: GrokClientOptions = {}) {
    super();
    this.options = {
      roomName: options.roomName || DEFAULT_ROOM,
      participantName: options.participantName || DEFAULT_NAME,
      sampleRate: options.sampleRate || 24000,
    };

    // Initialize audio I/O
    this.audioInput = new AudioInputStream({
      sampleRate: this.options.sampleRate,
      channels: 1,
      format: 'raw',
    });

    this.audioOutput = new AudioOutputStream({
      useMpg123: true, // Use mpg123 for MP3 audio from LiveKit
    });

    // Set up audio input handlers
    this.audioInput.on('error', (error) => {
      console.error('Audio input error:', error);
      this.emit('error', error);
    });

    // Set up audio output handlers
    this.audioOutput.on('error', (error) => {
      console.error('Audio output error:', error);
      this.emit('error', error);
    });
  }

  /**
   * Generate access token from backend server
   */
  private async generateToken(roomName: string, participantName: string): Promise<string> {
    const tokenEndpoint = `${TOKEN_SERVER_URL}/api/token`;
    
    console.log('Requesting token from:', tokenEndpoint);
    
    try {
      const response = await fetch(tokenEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ room: roomName, name: participantName })
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Token server error: ${errorText}`);
      }

      const data = await response.json();
      
      if (!data.token || typeof data.token !== 'string') {
        throw new Error('Invalid token received from server');
      }
      
      console.log('Token received successfully');
      return data.token;
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('Cannot reach token server. Make sure the server is running.');
      }
      throw error;
    }
  }


  /**
   * Connect to LiveKit room
   */
  async connect(): Promise<void> {
    if (this.isConnected) {
      console.warn('Already connected');
      return;
    }

    try {
      console.log('Generating access token...');
      const token = await this.generateToken(this.options.roomName, this.options.participantName);
      
      console.log('Creating room instance...');
      this.room = new Room({
        adaptiveStream: true,
        dynacast: true,
      });

      // Set up event handlers
      this.room.on(RoomEvent.Connected, async () => {
        console.log('✅ Connected to room:', this.options.roomName);
        this.isConnected = true;
        this.emit('connected');
        await this.setupAudioTracks();
      });

      this.room.on(RoomEvent.Disconnected, () => {
        console.log('❌ Disconnected from room');
        this.isConnected = false;
        this.cleanup();
        this.emit('disconnected');
      });

      this.room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
        console.log('👤 Participant connected:', participant.identity);
        this.emit('participantConnected', participant);
      });

      this.room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === 'audio' && participant !== this.room?.localParticipant) {
          console.log('🔊 Audio track subscribed from:', participant.identity);
          this.handleRemoteAudioTrack(track as RemoteAudioTrack);
        }
      });

      console.log('Connecting to LiveKit server...');
      await this.room.connect(LIVEKIT_URL, token, {
        autoSubscribe: true,
      });

    } catch (error) {
      console.error('Connection error:', error);
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Set up audio tracks after connection
   * Note: In Node.js, createLocalAudioTrack() may not work the same way as in browsers.
   * This is a placeholder that will need adjustment based on your LiveKit setup.
   */
  private async setupAudioTracks(): Promise<void> {
    try {
      // Start audio input stream
      console.log('Starting audio input stream...');
      this.audioInput.start();

      // Note: createLocalAudioTrack() in Node.js may require a WebRTC adapter
      // or may not be available. This is a limitation of livekit-client in Node.js.
      // For production, consider using @livekit/agents SDK which has better Node.js support.
      
      try {
        // Try to create a local audio track
        // This may fail in Node.js without proper WebRTC setup
        this.localAudioTrack = await createLocalAudioTrack({
          audio: {
            sampleRate: this.options.sampleRate,
            channelCount: 1,
          }
        });
        
        if (this.localAudioTrack && this.room) {
          await this.room.localParticipant.publishTrack(this.localAudioTrack);
          console.log('✅ Microphone track published');
        }
      } catch (error) {
        console.warn('⚠️  Could not create browser-style audio track (expected in Node.js)');
        console.warn('   Consider using @livekit/agents SDK for full Node.js audio support');
        console.warn('   Error:', error instanceof Error ? error.message : String(error));
        
        // Continue anyway - we can still receive audio
        // The audio input stream is running and can be bridged to LiveKit
        // with additional WebRTC adapter setup
      }

    } catch (error) {
      console.error('Error setting up audio tracks:', error);
      this.emit('error', error);
    }
  }

  /**
   * Handle remote audio track (agent's voice)
   * In Node.js, we need to extract audio data differently than in browsers
   */
  private handleRemoteAudioTrack(track: RemoteAudioTrack): void {
    console.log('Setting up remote audio playback...');
    
    try {
      // In browser: track.attach() returns HTMLAudioElement
      // In Node.js: we need to get the audio stream data
      
      // Try to get the MediaStreamTrack if available
      const mediaStreamTrack = (track as any).mediaStreamTrack;
      
      if (mediaStreamTrack) {
        // If we have a MediaStreamTrack, we might be able to process it
        // This depends on Node.js WebRTC support
        console.log('MediaStreamTrack available, attempting to process...');
        
        // For now, log that we received the track
        // Full implementation would require WebRTC adapter or @livekit/agents
        console.log('Track info:', {
          kind: track.kind,
          sid: track.sid,
          enabled: track.isMuted,
        });
      } else {
        // Fallback: The track might provide audio data through other means
        console.log('Track info:', {
          kind: track.kind,
          sid: track.sid,
        });
        console.log('⚠️  Note: Audio playback requires WebRTC adapter or @livekit/agents SDK');
      }
      
      // TODO: Extract audio data from track and feed to audioOutput.playChunk()
      // This requires:
      // 1. WebRTC adapter for Node.js, OR
      // 2. Using @livekit/agents SDK which has built-in audio handling
      
    } catch (error) {
      console.error('Error handling remote audio track:', error);
      this.emit('error', error);
    }
  }

  /**
   * Disconnect from room
   */
  async disconnect(): Promise<void> {
    if (!this.isConnected && !this.room) {
      return;
    }

    console.log('Disconnecting...');
    this.cleanup();

    if (this.room) {
      await this.room.disconnect();
      this.room = null;
    }

    this.isConnected = false;
    this.emit('disconnected');
  }

  /**
   * Cleanup resources
   */
  private cleanup(): void {
    if (this.audioInput.recording) {
      this.audioInput.stop();
    }
    
    if (this.audioOutput.playing) {
      this.audioOutput.stop();
    }

    if (this.localAudioTrack) {
      this.localAudioTrack.stop();
      this.localAudioTrack = null;
    }
  }

  /**
   * Check if connected
   */
  get connected(): boolean {
    return this.isConnected;
  }
}

