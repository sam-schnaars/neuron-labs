# Streaming ASR Alternatives (Better Than Volcengine)

Since Volcengine's streaming support is limited, here are better alternatives for true streaming with partial results:

## 1. Deepgram Streaming (Recommended) ⭐

**Why**: Simplest API, excellent docs, great latency, partial results built-in

### Implementation

```typescript
// src/cloud-api/deepgram-asr.ts
import WebSocket from "ws";
import { EventEmitter } from "events";

export class DeepgramStreamingASR extends EventEmitter {
  private ws: WebSocket | null = null;
  private apiKey: string;

  constructor(apiKey: string) {
    super();
    this.apiKey = apiKey;
  }

  start(): void {
    this.ws = new WebSocket("wss://api.deepgram.com/v1/listen", {
      headers: {
        Authorization: `Token ${this.apiKey}`,
      },
    });

    this.ws.on("open", () => {
      console.log("Deepgram WebSocket connected");
      this.emit("connected");
    });

    this.ws.on("message", (data: WebSocket.Data) => {
      const result = JSON.parse(data.toString());
      
      if (result.channel?.alternatives?.[0]) {
        const text = result.channel.alternatives[0].transcript;
        const isFinal = result.is_final || false;
        
        if (isFinal) {
          this.emit("final-result", text);
        } else {
          this.emit("partial-result", text);
        }
      }
    });

    this.ws.on("error", (error) => {
      this.emit("error", error);
    });
  }

  sendAudioChunk(chunk: Buffer): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(chunk);
    }
  }

  end(): Promise<string> {
    return new Promise((resolve) => {
      if (this.ws) {
        this.ws.close();
      }
      
      this.once("final-result", (text) => {
        resolve(text);
      });
      
      setTimeout(() => resolve(""), 2000);
    });
  }

  stop(): void {
    if (this.ws) {
      this.ws.close();
    }
  }
}
```

### Usage

```typescript
import { DeepgramStreamingASR } from "./cloud-api/deepgram-asr";

const asr = new DeepgramStreamingASR(process.env.DEEPGRAM_API_KEY!);

asr.on("partial-result", (text) => {
  console.log("Partial:", text); // Real-time!
});

asr.on("final-result", (text) => {
  console.log("Final:", text);
});

asr.start();
// Send audio chunks...
asr.sendAudioChunk(audioChunk);
```

## 2. AssemblyAI Streaming

**Why**: Very easy to use, good documentation

```typescript
import WebSocket from "ws";

export class AssemblyAIStreamingASR extends EventEmitter {
  private ws: WebSocket | null = null;

  async start(): Promise<void> {
    // Get temporary token
    const response = await fetch("https://api.assemblyai.com/v2/realtime/token", {
      method: "POST",
      headers: {
        Authorization: process.env.ASSEMBLYAI_API_KEY!,
      },
    });
    
    const { token } = await response.json();

    this.ws = new WebSocket(`wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000&token=${token}`);

    this.ws.on("open", () => {
      this.emit("connected");
    });

    this.ws.on("message", (data: WebSocket.Data) => {
      const message = JSON.parse(data.toString());
      
      if (message.message_type === "PartialTranscript") {
        this.emit("partial-result", message.text);
      } else if (message.message_type === "FinalTranscript") {
        this.emit("final-result", message.text);
      }
    });
  }

  sendAudioChunk(chunk: Buffer): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ audio_data: chunk.toString("base64") }));
    }
  }
}
```

## 3. Google Speech-to-Text Streaming

**Why**: Reliable, well-documented, good for production

```typescript
import { SpeechClient } from "@google-cloud/speech";

export class GoogleStreamingASR extends EventEmitter {
  private client: SpeechClient;
  private recognizeStream: any;

  constructor() {
    this.client = new SpeechClient();
  }

  start(): void {
    this.recognizeStream = this.client
      .streamingRecognize({
        config: {
          encoding: "LINEAR16",
          sampleRateHertz: 16000,
          languageCode: "en-US",
        },
        interimResults: true, // Get partial results!
      })
      .on("data", (data: any) => {
        const result = data.results[0];
        if (result) {
          const text = result.alternatives[0].transcript;
          if (result.isFinalAlternatives) {
            this.emit("final-result", text);
          } else {
            this.emit("partial-result", text);
          }
        }
      });
  }

  sendAudioChunk(chunk: Buffer): void {
    if (this.recognizeStream) {
      this.recognizeStream.write({ audioContent: chunk });
    }
  }

  stop(): void {
    if (this.recognizeStream) {
      this.recognizeStream.end();
    }
  }
}
```

## Comparison

| Feature | Volcengine | Deepgram | AssemblyAI | Google |
|---------|-----------|----------|------------|--------|
| Partial Results | ❌ (needs fix) | ✅ | ✅ | ✅ |
| Streaming Chunks | ✅ | ✅ | ✅ | ✅ |
| Ease of Use | Medium | ⭐ Easy | ⭐ Easy | Medium |
| Documentation | Limited | ⭐ Excellent | ⭐ Good | Good |
| Cost | Varies | Pay-as-you-go | Pay-as-you-go | Pay-as-you-go |
| Latency | Good | ⭐ Excellent | Good | Good |

## Recommendation

**For quick implementation**: Use **Deepgram** - it's the simplest and has the best docs.

**For production**: **Google Speech-to-Text** - most reliable and well-supported.

**If you want to stick with Volcengine**: Fix the `result_type` to "incremental" and handle `is_final` flag, but test if the API actually supports it.

## Quick Migration

1. Pick an alternative (Deepgram recommended)
2. Replace `StreamingASR` class to use the new provider
3. Update environment variables
4. Test - should work immediately with partial results!




