/**
 * Example: Streaming Chat Flow
 * 
 * This demonstrates how to use the streaming audio improvements
 * for a more responsive voice interaction experience.
 */

import { StreamingAudioWithVAD, AudioInputStream } from "../device/audio-streaming";
import { StreamingASR } from "../cloud-api/streaming-asr";
import { StreamingTTSPlayer } from "../device/streaming-tts";
import { display } from "../device/display";
import { chatWithLLMStream } from "../cloud-api/server";
import { ASRServer } from "../type";

/**
 * Example: Streaming voice chat with VAD
 * 
 * This replaces the button-based recording with automatic
 * voice activity detection and streaming ASR.
 */
export class StreamingChatFlow {
  private audioStream: StreamingAudioWithVAD;
  private asr: StreamingASR;
  private tts: StreamingTTSPlayer;
  private isActive: boolean = false;

  constructor() {
    // Initialize streaming audio with VAD
    this.audioStream = new StreamingAudioWithVAD({
      sampleRate: 16000,
      channels: 1,
      vadThreshold: 500, // Adjust based on your environment
      vadSilenceDuration: 1500, // 1.5 seconds of silence to stop
    });

    // Initialize streaming ASR
    this.asr = new StreamingASR({
      server: ASRServer.volcengine,
    });

    // Initialize streaming TTS
    this.tts = new StreamingTTSPlayer({
      useWavPlayer: false, // Use MP3 streaming
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    // Handle speech detection
    this.audioStream.on("speech-start", () => {
      console.log("🎤 Speech detected, starting recognition...");
      display({
        status: "listening",
        RGB: "#00ff00",
        text: "Listening...",
      });
      this.asr.start();
    });

    // Handle speech end
    this.audioStream.on("speech-end", (audioData: Buffer) => {
      console.log("🔇 Speech ended, processing...");
      display({
        status: "recognizing",
        RGB: "#ff6800",
      });
      
      // Send final audio chunk and get result
      this.asr.sendAudioChunk(audioData);
      this.asr.end().then((text) => {
        if (text) {
          this.handleUserInput(text);
        } else {
          this.resetToListening();
        }
      });
    });

    // Handle partial ASR results (real-time feedback)
    this.asr.on("partial-result", (text: string) => {
      display({
        status: "listening",
        text: text,
        RGB: "#00ff00",
      });
    });

    // Handle final ASR result
    this.asr.on("final-result", (text: string) => {
      console.log("✅ Recognized:", text);
      display({
        status: "recognizing",
        text: text,
      });
    });

    // Handle audio chunks during speech
    this.audioStream.on("audio-chunk", (chunk: Buffer) => {
      if (this.asr) {
        this.asr.sendAudioChunk(chunk);
      }
    });

    // Handle errors
    this.audioStream.on("error", (error: Error) => {
      console.error("Audio stream error:", error);
      this.resetToListening();
    });

    this.asr.on("error", (error: Error) => {
      console.error("ASR error:", error);
      this.resetToListening();
    });
  }

  private async handleUserInput(text: string): Promise<void> {
    display({
      status: "answering",
      RGB: "#0000ff",
      text: "Thinking...",
    });

    // Get LLM response with streaming
    let fullResponse = "";
    let currentSentence = "";

    await chatWithLLMStream(
      [{ role: "user", content: text }],
      // Partial text callback
      (partialText: string) => {
        currentSentence += partialText;
        fullResponse += partialText;
        
        // Check if we have a complete sentence
        const sentenceEnd = /[.!?]\s/.exec(currentSentence);
        if (sentenceEnd) {
          const sentence = currentSentence.substring(0, sentenceEnd.index + 1).trim();
          currentSentence = currentSentence.substring(sentenceEnd.index + 1);
          
          if (sentence) {
            // Stream TTS for this sentence
            this.speakSentence(sentence);
          }
        }

        display({
          status: "answering",
          text: fullResponse,
          RGB: "#0000ff",
        });
      },
      // End callback
      () => {
        // Speak remaining text
        if (currentSentence.trim()) {
          this.speakSentence(currentSentence.trim());
        }
      },
      // Thinking callback (optional)
      undefined,
      // Function call callback (optional)
      undefined
    );
  }

  private async speakSentence(text: string): Promise<void> {
    // For now, use existing TTS processor
    // In full implementation, you'd use streaming TTS here
    const { ttsProcessor } = await import("../cloud-api/server");
    const result = await ttsProcessor(text);
    
    if (result.duration > 0) {
      await this.tts.playFile(result);
    }
  }

  private resetToListening(): void {
    display({
      status: "resting",
      RGB: "#000055",
      text: "Ready to listen...",
    });
  }

  /**
   * Start the streaming chat flow
   */
  start(): void {
    if (this.isActive) {
      console.warn("Chat flow already active");
      return;
    }

    this.isActive = true;
    console.log("🎙️ Starting streaming chat flow...");
    this.resetToListening();
    this.audioStream.start();
  }

  /**
   * Stop the streaming chat flow
   */
  stop(): void {
    if (!this.isActive) {
      return;
    }

    this.isActive = false;
    this.audioStream.stop();
    this.asr.stop();
    this.tts.stop();
    console.log("🛑 Stopped streaming chat flow");
  }
}

/**
 * Usage example:
 * 
 * const flow = new StreamingChatFlow();
 * flow.start();
 * 
 * // Later, to stop:
 * flow.stop();
 */

