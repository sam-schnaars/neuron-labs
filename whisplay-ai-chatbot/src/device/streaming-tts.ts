/**
 * Streaming TTS Playback
 * 
 * This module provides streaming TTS playback that plays audio
 * chunks as they arrive instead of waiting for complete sentences.
 */

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import dotenv from "dotenv";
import { TTSResult } from "../type";

dotenv.config();

const soundCardIndex = process.env.SOUND_CARD_INDEX || "1";

export interface StreamingTTSOptions {
  useWavPlayer?: boolean;
  bufferSize?: number; // ms to buffer before playing
}

export class StreamingTTSPlayer extends EventEmitter {
  private mp3Process: ChildProcess | null = null;
  private wavProcess: ChildProcess | null = null;
  private isPlaying: boolean = false;
  private audioQueue: Buffer[] = [];
  private options: Required<StreamingTTSOptions>;

  constructor(options: StreamingTTSOptions = {}) {
    super();
    this.options = {
      useWavPlayer: options.useWavPlayer || false,
      bufferSize: options.bufferSize || 200, // 200ms buffer
    };

    this.initializePlayer();
  }

  private initializePlayer(): void {
    if (this.options.useWavPlayer) {
      // WAV files use sox play (spawned per file)
      // No persistent process needed
      return;
    }

    // MP3 uses persistent mpg123 process
    this.mp3Process = spawn("mpg123", [
      "-",
      "--scale",
      "2",
      "-o",
      "alsa",
      "-a",
      `hw:${soundCardIndex},0`,
    ]);

    this.mp3Process.stdout?.on("data", (data) => {
      // mpg123 outputs info to stdout
    });

    this.mp3Process.stderr?.on("data", (data) => {
      // Errors go to stderr
      console.error("TTS player error:", data.toString());
    });

    this.mp3Process.on("exit", (code) => {
      if (code !== 0 && this.isPlaying) {
        this.emit("error", new Error(`Player exited with code ${code}`));
      }
      this.isPlaying = false;
    });
  }

  /**
   * Play audio chunk immediately (for streaming)
   */
  playChunk(chunk: Buffer, isLast: boolean = false): void {
    if (this.options.useWavPlayer) {
      // For WAV, we need to accumulate and play as file
      // This is less ideal for streaming
      this.audioQueue.push(chunk);
      if (isLast) {
        this.playWavFile(Buffer.concat(this.audioQueue));
        this.audioQueue = [];
      }
      return;
    }

    // For MP3, stream directly to mpg123
    if (!this.mp3Process || !this.mp3Process.stdin) {
      console.error("TTS player not initialized");
      return;
    }

    if (!this.isPlaying) {
      this.isPlaying = true;
      this.emit("play-start");
    }

    try {
      this.mp3Process.stdin.write(chunk);
      if (isLast) {
        // Small delay to ensure last chunk is processed
        setTimeout(() => {
          this.isPlaying = false;
          this.emit("play-end");
        }, 100);
      }
    } catch (error) {
      console.error("Error writing to TTS player:", error);
      this.emit("error", error);
    }
  }

  /**
   * Play complete audio file (for compatibility)
   */
  playFile(result: TTSResult): Promise<void> {
    return new Promise((resolve, reject) => {
      if (result.filePath) {
        // WAV file
        this.playWavFile(result.filePath).then(resolve).catch(reject);
      } else if (result.buffer || result.base64) {
        // MP3 buffer
        const buffer = result.buffer || Buffer.from(result.base64!, "base64");
        this.playChunk(buffer, true);
        
        // Wait for duration
        setTimeout(() => {
          resolve();
        }, result.duration || 1000);
      } else {
        resolve();
      }
    });
  }

  private playWavFile(filePathOrBuffer: string | Buffer): Promise<void> {
    return new Promise((resolve, reject) => {
      const args = typeof filePathOrBuffer === "string" 
        ? [filePathOrBuffer]
        : ["-t", "wav", "-"];

      const process = spawn("play", args);
      
      if (typeof filePathOrBuffer !== "string" && Buffer.isBuffer(filePathOrBuffer)) {
        process.stdin?.write(filePathOrBuffer);
        process.stdin?.end();
      }

      process.on("close", (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`Playback failed with code ${code}`));
        }
      });

      process.on("error", reject);
    });
  }

  /**
   * Stop playback
   */
  stop(): void {
    if (this.mp3Process && this.mp3Process.stdin) {
      try {
        this.mp3Process.stdin.end();
      } catch (e) {
        // Ignore
      }
    }

    if (this.wavProcess) {
      this.wavProcess.kill();
      this.wavProcess = null;
    }

    this.isPlaying = false;
    this.audioQueue = [];
    this.emit("stop");
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.stop();
    if (this.mp3Process) {
      this.mp3Process.kill();
      this.mp3Process = null;
    }
  }
}

