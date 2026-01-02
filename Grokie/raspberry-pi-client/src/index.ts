/**
 * Main entry point for GROK Voice Agent Raspberry Pi Client
 * Runs the client with WM8960 audio hardware support
 */

// Polyfill for browser APIs that livekit-client expects in Node.js
import { cpus } from 'os';

// Try to load WebRTC adapter (wrtc package) - must be synchronous
try {
  const wrtc = require('wrtc');
  // Use wrtc's WebRTC implementation
  if (wrtc && typeof wrtc.RTCPeerConnection !== 'undefined') {
    (globalThis as any).RTCPeerConnection = wrtc.RTCPeerConnection;
    (globalThis as any).RTCSessionDescription = wrtc.RTCSessionDescription;
    (globalThis as any).RTCIceCandidate = wrtc.RTCIceCandidate;
    (globalThis as any).MediaStream = wrtc.MediaStream;
    (globalThis as any).MediaStreamTrack = wrtc.MediaStreamTrack;
    console.log('✅ WebRTC adapter (wrtc) loaded');
  }
} catch (error) {
  console.warn('⚠️  WebRTC adapter (wrtc) not found. Install with: npm install wrtc');
  console.warn('   Or use the Python client: python3 grok_pi_client.py');
  console.warn('   Note: wrtc installation on Raspberry Pi may require additional build tools');
}

if (typeof globalThis.navigator === 'undefined') {
  (globalThis as any).navigator = {
    userAgent: 'Node.js',
    platform: process.platform,
    hardwareConcurrency: cpus().length,
  };
}

import { GrokClient } from './grok-client.js';
import dotenv from 'dotenv';

dotenv.config();

// Handle graceful shutdown
let client: GrokClient | null = null;

async function main() {
  console.log('🎤 GROK Voice Agent - Raspberry Pi Client');
  console.log('='.repeat(50));
  console.log(`Using sound card index: ${process.env.SOUND_CARD_INDEX || '1'}`);
  console.log(`LiveKit URL: ${process.env.LIVEKIT_URL || 'ws://localhost:7880'}`);
  console.log(`Room: ${process.env.LIVEKIT_ROOM || 'test-room'}`);
  console.log('='.repeat(50));
  console.log('');

  try {
    // Create client instance
    client = new GrokClient({
      roomName: process.env.LIVEKIT_ROOM,
      participantName: process.env.PARTICIPANT_NAME,
      sampleRate: 24000, // 24kHz for LiveKit compatibility
    });

    // Set up event handlers
    client.on('connected', () => {
      console.log('');
      console.log('✅ Connected! Microphone is active - start speaking!');
      console.log('Press Ctrl+C to disconnect');
      console.log('');
    });

    client.on('disconnected', () => {
      console.log('Disconnected from room');
    });

    client.on('participantConnected', (participant) => {
      console.log(`👤 Agent connected: ${participant.identity}`);
    });

    client.on('error', (error) => {
      console.error('Client error:', error);
    });

    // Connect to room
    await client.connect();

    // Keep running until interrupted
    // The client will handle the connection and audio streaming

  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n\n🛑 Shutting down...');
  if (client) {
    await client.disconnect();
  }
  console.log('👋 Goodbye!');
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\n\n🛑 Shutting down...');
  if (client) {
    await client.disconnect();
  }
  console.log('👋 Goodbye!');
  process.exit(0);
});

// Start the client
main().catch((error) => {
  console.error('Unhandled error:', error);
  process.exit(1);
});

