# Quick Start: Streaming Audio Improvements

This guide shows you how to use the new streaming audio features to improve latency and user experience.

## What's Improved

1. **Streaming ASR** - Process audio in real-time instead of waiting for complete files
2. **Voice Activity Detection (VAD)** - Automatic speech detection (hands-free!)
3. **Streaming TTS** - Play audio as it's generated
4. **Partial Results** - See transcription in real-time

## Quick Integration

### Option 1: Use the Example Streaming Chat Flow

```typescript
import { StreamingChatFlow } from "./examples/streaming-chat-flow";

const flow = new StreamingChatFlow();
flow.start(); // Starts listening automatically with VAD

// It will:
// - Automatically detect when you start speaking
// - Show partial transcripts in real-time
// - Process and respond when you stop speaking
// - Play TTS responses as they're generated
```

### Option 2: Integrate into Existing ChatFlow

Replace the button-based recording in `ChatFlow.ts`:

```typescript
import { StreamingAudioWithVAD } from "../device/audio-streaming";
import { StreamingASR } from "../cloud-api/streaming-asr";

// In your ChatFlow class:
private audioStream: StreamingAudioWithVAD;
private asr: StreamingASR;

constructor() {
  this.audioStream = new StreamingAudioWithVAD({
    sampleRate: 16000,
    channels: 1,
  });
  
  this.asr = new StreamingASR({
    server: ASRServer.volcengine,
  });

  // Handle speech detection
  this.audioStream.on("speech-start", () => {
    this.asr.start();
    display({ status: "listening" });
  });

  this.audioStream.on("speech-end", (audioData) => {
    this.asr.sendAudioChunk(audioData);
    this.asr.end().then((text) => {
      // Process user input
    });
  });

  // Real-time partial results
  this.asr.on("partial-result", (text) => {
    display({ text }); // Show what's being recognized
  });
}

// Start listening
startListening() {
  this.audioStream.start(); // No button needed!
}
```

## Configuration

### VAD Sensitivity

Adjust VAD threshold based on your environment:

```typescript
const audioStream = new StreamingAudioWithVAD({
  vadThreshold: 500,        // Lower = more sensitive (picks up quieter speech)
  vadSilenceDuration: 1500, // ms of silence before stopping
  speechDuration: 200,      // ms of speech before starting
});
```

### ASR Server

Currently supports:
- **Volcengine** (recommended) - Has WebSocket streaming built-in
- Others can be added by implementing streaming interface

Set in `.env`:
```
ASR_SERVER=volcengine
VOLCENGINE_APP_ID=your_app_id
VOLCENGINE_ACCESS_TOKEN=your_token
```

## Benefits Over Current System

| Feature | Current | Streaming |
|---------|---------|-----------|
| Latency | 2-3 seconds | <500ms |
| Button Required | Yes | No (VAD) |
| Partial Results | No | Yes |
| Real-time Feedback | No | Yes |
| Hands-free | No | Yes |

## Migration Path

1. **Phase 1**: Add streaming ASR alongside existing file-based (fallback)
2. **Phase 2**: Add VAD as optional mode (keep button as fallback)
3. **Phase 3**: Make streaming default, file-based as fallback

## Troubleshooting

### VAD Not Detecting Speech

- Increase `vadThreshold` (try 300-800)
- Check microphone levels: `arecord -l` and `alsamixer`
- Ensure quiet environment or add noise gate

### Streaming ASR Not Working

- Verify Volcengine credentials in `.env`
- Check WebSocket connection: `client.on("error")` handler
- Fall back to file-based ASR if needed

### Audio Quality Issues

- Ensure sample rate matches (16kHz recommended)
- Check ALSA configuration: `aplay -l` and `arecord -l`
- Verify sound card index: `SOUND_CARD_INDEX=1` in `.env`

## Next Steps

1. Test VAD sensitivity in your environment
2. Integrate streaming ASR into your ChatFlow
3. Add streaming TTS for faster responses
4. Consider adding wake word detection for even better UX

## Alternative: Simpler Live Voice APIs

If you want something even simpler than implementing streaming yourself:

- **Deepgram Streaming** - Very simple WebSocket API
- **AssemblyAI Streaming** - Easy to use, good docs
- **Google Speech-to-Text Streaming** - Reliable, well-documented

These can replace the ASR component entirely with minimal code changes.

