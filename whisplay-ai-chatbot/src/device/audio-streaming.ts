/**
 * Streaming Audio Input/Output
 * 
 * This module provides streaming audio capabilities to reduce latency
 * compared to file-based recording/playback.
 */

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import dotenv from "dotenv";

dotenv.config();

const soundCardIndex = process.env.SOUND_CARD_INDEX || "1";
const recordFileFormat = "wav"; // Use WAV for streaming (raw PCM)

export interface AudioStreamOptions {
  sampleRate?: number;
  channels?: number;
  format?: "wav" | "raw";
  chunkSize?: number; // bytes per chunk
}

export class AudioInputStream extends EventEmitter {
  private process: ChildProcess | null = null;
  private isRecording: boolean = false;
  private options: Required<AudioStreamOptions>;

  constructor(options: AudioStreamOptions = {}) {
    super();
    this.options = {
      sampleRate: options.sampleRate || 16000,
      channels: options.channels || 1,
      format: options.format || "raw",
      chunkSize: options.chunkSize || 3200, // ~100ms at 16kHz mono
    };
  }

  /**
   * Start streaming audio from microphone
   */
  start(): void {
    if (this.isRecording) {
      console.warn("Audio stream already recording");
      return;
    }

    this.isRecording = true;
    
    // Use sox to stream raw PCM audio
    // -t alsa: ALSA input
    // -r: sample rate
    // -c: channels
    // -t raw: raw PCM output
    // -e signed-integer: signed integer encoding
    // -b 16: 16-bit
    // -: output to stdout
    const args = [
      "-t", "alsa",
      "default",
      "-r", this.options.sampleRate.toString(),
      "-c", this.options.channels.toString(),
      "-t", "raw",
      "-e", "signed-integer",
      "-b", "16",
      "-", // stdout
    ];

    this.process = spawn("sox", args);

    this.process.stdout?.on("data", (chunk: Buffer) => {
      this.emit("data", chunk);
    });

    this.process.stderr?.on("data", (data: Buffer) => {
      const message = data.toString();
      // sox outputs silence detection info to stderr
      if (message.includes("silence")) {
        this.emit("silence", message);
      }
    });

    this.process.on("close", (code) => {
      this.isRecording = false;
      this.emit("end", code);
    });

    this.process.on("error", (error) => {
      this.isRecording = false;
      this.emit("error", error);
    });

    this.emit("start");
  }

  /**
   * Stop streaming audio
   */
  stop(): void {
    if (!this.isRecording || !this.process) {
      return;
    }

    this.isRecording = false;
    this.process.kill("SIGTERM");
    this.process = null;
  }

  /**
   * Check if currently recording
   */
  get recording(): boolean {
    return this.isRecording;
  }
}

/**
 * Voice Activity Detection using simple energy-based VAD
 */
export class SimpleVAD extends EventEmitter {
  private energyThreshold: number;
  private silenceDuration: number; // ms of silence before considering speech ended
  private speechDuration: number; // ms of speech before considering speech started
  private lastSpeechTime: number = 0;
  private lastSilenceTime: number = 0;
  private isSpeaking: boolean = false;
  private sampleRate: number;

  constructor(options: {
    energyThreshold?: number;
    silenceDuration?: number;
    speechDuration?: number;
    sampleRate?: number;
  } = {}) {
    super();
    this.energyThreshold = options.energyThreshold || 500; // Adjust based on testing
    this.silenceDuration = options.silenceDuration || 1000; // 1 second
    this.speechDuration = options.speechDuration || 200; // 200ms
    this.sampleRate = options.sampleRate || 16000;
  }

  /**
   * Process audio chunk and detect voice activity
   */
  processChunk(chunk: Buffer): void {
    // Calculate RMS (Root Mean Square) energy
    let sum = 0;
    for (let i = 0; i < chunk.length; i += 2) {
      // 16-bit signed integer, little-endian
      const sample = chunk.readInt16LE(i);
      sum += sample * sample;
    }
    const rms = Math.sqrt(sum / (chunk.length / 2));
    const energy = rms;

    const now = Date.now();
    const isSpeech = energy > this.energyThreshold;

    if (isSpeech) {
      this.lastSpeechTime = now;
      if (!this.isSpeaking) {
        // Check if we've had enough speech to start
        if (now - this.lastSilenceTime >= this.speechDuration) {
          this.isSpeaking = true;
          this.emit("speech-start");
        }
      }
    } else {
      this.lastSilenceTime = now;
      if (this.isSpeaking) {
        // Check if we've had enough silence to stop
        if (now - this.lastSpeechTime >= this.silenceDuration) {
          this.isSpeaking = false;
          this.emit("speech-end");
        }
      }
    }

    // Emit energy level for debugging/visualization
    this.emit("energy", energy);
  }

  reset(): void {
    this.isSpeaking = false;
    this.lastSpeechTime = 0;
    this.lastSilenceTime = Date.now();
  }
}

/**
 * Combined streaming audio with VAD
 */
export class StreamingAudioWithVAD extends EventEmitter {
  private audioStream: AudioInputStream;
  private vad: SimpleVAD;
  private buffer: Buffer[] = [];
  private isBuffering: boolean = false;

  constructor(options: AudioStreamOptions & {
    vadThreshold?: number;
    vadSilenceDuration?: number;
  } = {}) {
    super();
    
    this.audioStream = new AudioInputStream(options);
    this.vad = new SimpleVAD({
      energyThreshold: options.vadThreshold,
      silenceDuration: options.vadSilenceDuration,
      sampleRate: options.sampleRate || 16000,
    });

    // Forward audio data
    this.audioStream.on("data", (chunk: Buffer) => {
      this.vad.processChunk(chunk);
      
      if (this.isBuffering) {
        this.buffer.push(chunk);
        this.emit("audio-chunk", chunk);
      }
    });

    // Handle VAD events
    this.vad.on("speech-start", () => {
      this.isBuffering = true;
      this.buffer = [];
      this.emit("speech-start");
    });

    this.vad.on("speech-end", () => {
      this.isBuffering = false;
      const audioData = Buffer.concat(this.buffer);
      this.buffer = [];
      this.emit("speech-end", audioData);
    });

    this.audioStream.on("error", (error) => {
      this.emit("error", error);
    });
  }

  start(): void {
    this.vad.reset();
    this.audioStream.start();
  }

  stop(): void {
    this.audioStream.stop();
    this.vad.reset();
  }

  /**
   * Get all buffered audio since speech started
   */
  getBufferedAudio(): Buffer {
    return Buffer.concat(this.buffer);
  }
}

