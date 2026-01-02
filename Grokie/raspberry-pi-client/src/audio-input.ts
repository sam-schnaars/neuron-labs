/**
 * Audio Input Stream using ALSA/sox for WM8960 microphone
 * Streams raw PCM audio from the microphone to LiveKit
 */

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import dotenv from "dotenv";

dotenv.config();

const soundCardIndex = process.env.SOUND_CARD_INDEX || "1";

export interface AudioInputOptions {
  sampleRate?: number;
  channels?: number;
  format?: "raw";
  chunkSize?: number; // bytes per chunk
}

export class AudioInputStream extends EventEmitter {
  private process: ChildProcess | null = null;
  private isRecording: boolean = false;
  private options: Required<AudioInputOptions>;

  constructor(options: AudioInputOptions = {}) {
    super();
    this.options = {
      sampleRate: options.sampleRate || 24000,
      channels: options.channels || 1,
      format: options.format || "raw",
      chunkSize: options.chunkSize || 4800, // ~100ms at 24kHz mono (24000 * 0.1 * 2 bytes)
    };
  }

  /**
   * Start streaming audio from microphone using sox
   */
  start(): void {
    if (this.isRecording) {
      console.warn("Audio stream already recording");
      return;
    }

    this.isRecording = true;
    
    // Use sox to stream raw PCM audio from ALSA
    // -t alsa: ALSA input
    // default: use default ALSA device
    // -r: sample rate (24kHz for LiveKit compatibility)
    // -c: channels (1 = mono)
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

    console.log(`Starting audio input: sox ${args.join(" ")}`);
    this.process = spawn("sox", args);

    this.process.stdout?.on("data", (chunk: Buffer) => {
      this.emit("data", chunk);
    });

    this.process.stderr?.on("data", (data: Buffer) => {
      const message = data.toString();
      // sox outputs info to stderr, but we can ignore most of it
      if (message.includes("error") || message.includes("Error")) {
        console.error("sox error:", message);
        this.emit("error", new Error(message));
      }
    });

    this.process.on("close", (code) => {
      this.isRecording = false;
      if (code !== 0 && code !== null) {
        console.error(`sox process exited with code ${code}`);
        this.emit("error", new Error(`sox exited with code ${code}`));
      }
      this.emit("end", code);
    });

    this.process.on("error", (error) => {
      this.isRecording = false;
      console.error("Failed to start sox process:", error);
      this.emit("error", error);
    });

    this.emit("start");
    console.log("Audio input stream started");
  }

  /**
   * Stop streaming audio
   */
  stop(): void {
    if (!this.isRecording || !this.process) {
      return;
    }

    console.log("Stopping audio input stream");
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

