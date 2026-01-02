/**
 * Audio Output Stream using ALSA/mpg123 or aplay for WM8960 speakers
 * Receives audio from LiveKit and plays it through the speakers
 */

import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import dotenv from "dotenv";

dotenv.config();

const soundCardIndex = process.env.SOUND_CARD_INDEX || "1";

export interface AudioOutputOptions {
  useMpg123?: boolean; // Use mpg123 for MP3, otherwise use aplay for PCM
}

export class AudioOutputStream extends EventEmitter {
  private process: ChildProcess | null = null;
  private isPlaying: boolean = false;
  private options: Required<AudioOutputOptions>;
  private useMpg123: boolean;

  constructor(options: AudioOutputOptions = {}) {
    super();
    this.options = {
      useMpg123: options.useMpg123 ?? true, // Default to mpg123 for MP3
    };
    this.useMpg123 = this.options.useMpg123;
  }

  /**
   * Initialize the audio player process
   */
  private initializePlayer(): void {
    if (this.process) {
      return; // Already initialized
    }

    if (this.useMpg123) {
      // Use mpg123 for MP3 audio (LiveKit typically sends Opus/MP3)
      this.process = spawn("mpg123", [
        "-",
        "--scale",
        "2",
        "-o",
        "alsa",
        "-a",
        `hw:${soundCardIndex},0`,
      ]);

      this.process.stdout?.on("data", (data) => {
        // mpg123 outputs info to stdout
      });

      this.process.stderr?.on("data", (data) => {
        const message = data.toString();
        if (message.includes("error") || message.includes("Error")) {
          console.error("mpg123 error:", message);
        }
      });
    } else {
      // Use aplay for raw PCM audio
      this.process = spawn("aplay", [
        "-f", "S16_LE",
        "-c", "1",
        "-r", "24000",
        "-D", `hw:${soundCardIndex},0`,
        "-", // read from stdin
      ]);

      this.process.stderr?.on("data", (data) => {
        const message = data.toString();
        if (message.includes("error") || message.includes("Error")) {
          console.error("aplay error:", message);
        }
      });
    }

    this.process.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        console.error(`Audio player exited with code ${code}`);
        this.emit("error", new Error(`Player exited with code ${code}`));
      }
      this.isPlaying = false;
      this.process = null;
    });

    this.process.on("error", (error) => {
      console.error("Failed to start audio player:", error);
      this.isPlaying = false;
      this.process = null;
      this.emit("error", error);
    });

    console.log(`Audio output initialized (${this.useMpg123 ? "mpg123" : "aplay"})`);
  }

  /**
   * Play audio chunk
   */
  playChunk(chunk: Buffer): void {
    if (!this.process) {
      this.initializePlayer();
    }

    if (!this.process) {
      console.error("Audio player not initialized");
      return;
    }

    try {
      this.isPlaying = true;
      this.process.stdin?.write(chunk);
    } catch (error) {
      console.error("Error writing audio chunk:", error);
      this.emit("error", error);
    }
  }

  /**
   * Stop playing audio
   */
  stop(): void {
    if (this.process) {
      console.log("Stopping audio output");
      try {
        this.process.stdin?.end();
        this.process.kill("SIGTERM");
      } catch (error) {
        // Ignore errors during cleanup
      }
      this.process = null;
      this.isPlaying = false;
    }
  }

  /**
   * Restart the player (useful if it crashed)
   */
  restart(): void {
    this.stop();
    setTimeout(() => {
      this.initializePlayer();
    }, 100);
  }

  /**
   * Check if currently playing
   */
  get playing(): boolean {
    return this.isPlaying;
  }
}

