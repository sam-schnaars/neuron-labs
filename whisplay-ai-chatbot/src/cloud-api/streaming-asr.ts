/**
 * Streaming ASR Implementation
 * 
 * This module provides streaming speech recognition that processes
 * audio chunks in real-time instead of waiting for complete files.
 */

import { VolcengineAsrClient } from "./volcengine/volcengine-asr";
import { byteDanceAppId, byteDanceAccessToken } from "./volcengine/volcengine";
import { byteDanceAppId, byteDanceAccessToken } from "./volcengine/volcengine";
import { ASRServer } from "../type";
import { EventEmitter } from "events";

export interface StreamingASROptions {
  server?: ASRServer;
  onPartialResult?: (text: string) => void;
  onFinalResult?: (text: string) => void;
  onError?: (error: Error) => void;
}

export class StreamingASR extends EventEmitter {
  private client: VolcengineAsrClient | null = null;
  private isStreaming: boolean = false;
  private partialText: string = "";

  constructor(options: StreamingASROptions = {}) {
    super();

    // Only support Volcengine for now (has WebSocket streaming)
    if (options.server === ASRServer.volcengine && byteDanceAppId && byteDanceAccessToken) {
      this.client = new VolcengineAsrClient({
        appid: byteDanceAppId,
        token: byteDanceAccessToken,
        cluster: "volcengine_input_common",
        uid: "01",
      });

      this.setupClient();
    } else {
      console.warn("Streaming ASR only supports Volcengine with WebSocket. Falling back to file-based.");
    }
  }

  private setupClient(): void {
    if (!this.client) return;

    this.client.onOpen = () => {
      console.log("Streaming ASR WebSocket connected");
      this.emit("connected");
    };

    this.client.onMessage = (data: any) => {
      const result = data?.result?.[0];
      if (!result) return;

      const text = result.text || "";
      const isFinal = result.is_final !== false; // Default to final if not specified

      if (isFinal) {
        this.partialText = "";
        this.emit("final-result", text);
      } else {
        this.partialText = text;
        this.emit("partial-result", text);
      }
    };

    this.client.onError = (error: any) => {
      console.error("Streaming ASR error:", error);
      this.emit("error", error);
    };

    this.client.onClose = (code: number, reason: string) => {
      console.log(`Streaming ASR closed: ${code} - ${reason}`);
      this.isStreaming = false;
      this.emit("disconnected", code, reason);
    };
  }

  /**
   * Start streaming audio chunks for recognition
   */
  start(): void {
    if (!this.client) {
      throw new Error("Streaming ASR client not initialized");
    }

    if (this.isStreaming) {
      console.warn("Already streaming");
      return;
    }

    this.isStreaming = true;
    this.partialText = "";
    this.emit("start");
  }

  /**
   * Send audio chunk for recognition
   */
  sendAudioChunk(chunk: Buffer): void {
    if (!this.client || !this.isStreaming) {
      return;
    }

    this.client.send(chunk);
  }

  /**
   * Signal end of audio stream
   */
  async end(): Promise<string> {
    if (!this.client || !this.isStreaming) {
      return "";
    }

    return new Promise((resolve) => {
      // Wait for final result
      const timeout = setTimeout(() => {
        resolve(this.partialText);
        this.isStreaming = false;
      }, 2000);

      this.once("final-result", (text: string) => {
        clearTimeout(timeout);
        resolve(text);
        this.isStreaming = false;
      });

      // Signal end to server
      this.client?.end();
    });
  }

  /**
   * Stop streaming and close connection
   */
  stop(): void {
    if (this.client) {
      this.client.close();
    }
    this.isStreaming = false;
    this.partialText = "";
    this.emit("stop");
  }

  /**
   * Get current partial result
   */
  getPartialResult(): string {
    return this.partialText;
  }
}

/**
 * Helper function to use streaming ASR with audio stream
 */
export async function recognizeStreamingAudio(
  audioChunks: Buffer[],
  options: StreamingASROptions = {}
): Promise<string> {
  const asr = new StreamingASR(options);
  
  return new Promise((resolve, reject) => {
    let finalResult = "";

    asr.on("final-result", (text: string) => {
      finalResult = text;
      resolve(text);
      asr.stop();
    });

    asr.on("error", (error: Error) => {
      reject(error);
      asr.stop();
    });

    asr.start();

    // Send all chunks
    for (const chunk of audioChunks) {
      asr.sendAudioChunk(chunk);
    }

    // End and wait for result
    asr.end().then((text) => {
      if (!finalResult) {
        resolve(text);
      }
    });
  });
}

