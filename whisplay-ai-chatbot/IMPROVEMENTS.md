# Audio System Improvements for Live Voice

## Current Limitations

1. **File-based recording**: Records entire audio to file, then processes (adds ~1-2s latency)
2. **Button-based interaction**: Requires manual button press/release
3. **No real-time feedback**: No partial transcripts while speaking
4. **Sentence-by-sentence TTS**: Waits for complete sentences before playing
5. **No Voice Activity Detection**: Can't automatically detect when user starts/stops speaking

## Recommended Improvements (Simpler than Grok)

### 1. **Streaming ASR (High Impact, Medium Complexity)**

**Current**: Records to file → reads file → sends to ASR
**Improved**: Stream audio chunks directly to WebSocket ASR

**Benefits**:
- Reduces latency by 1-2 seconds
- Enables real-time partial transcripts
- Works with existing Volcengine WebSocket ASR

**Implementation**:
- Use `sox` with stdout pipe instead of file output
- Stream chunks to Volcengine ASR WebSocket (already supports this!)
- Handle incremental results

### 2. **Voice Activity Detection (VAD) (High Impact, Low Complexity)**

**Current**: Button press/release to start/stop
**Improved**: Automatic detection of speech start/stop

**Benefits**:
- Hands-free operation
- Better UX (no button needed)
- Can still keep button as fallback

**Implementation Options**:
- **Simple**: Use `sox` silence detection (already partially there!)
- **Better**: Use `webrtc-vad` or `@ricky0123/vad-node` (lightweight VAD library)
- **Best**: Use Volcengine's built-in VAD (already in workflow: `"vad"`)

### 3. **Streaming TTS Playback (Medium Impact, Low Complexity)**

**Current**: Wait for complete sentence → generate TTS → play
**Improved**: Stream TTS chunks and play as they arrive

**Benefits**:
- Faster perceived response time
- More natural conversation flow
- Works with Volcengine WebSocket TTS (already exists!)

**Implementation**:
- Use existing `volcengine-tts-ws.ts` (already streams!)
- Modify `StreamResponsor` to play chunks incrementally
- Buffer small chunks before playing to avoid choppiness

### 4. **Incremental ASR Results (Medium Impact, Low Complexity)**

**Current**: Wait for complete recognition result
**Improved**: Show partial transcripts in real-time

**Benefits**:
- Better user feedback
- User can see what's being recognized
- Can interrupt if wrong

**Implementation**:
- Volcengine ASR already supports partial results
- Modify callback to handle `result_type: "incremental"` in workflow
- Update display with partial text

### 5. **Audio Stream Wrapper (Low Impact, High Value)**

**Current**: File I/O overhead
**Improved**: Direct stream from microphone to processing

**Benefits**:
- Lower latency
- Less disk I/O
- Cleaner architecture

**Implementation**:
- Create `AudioStream` class that wraps `sox` stdout
- Pipe directly to WebSocket or buffer
- Handle backpressure and errors

## Implementation Priority

### Phase 1: Quick Wins (1-2 days)
1. **Streaming ASR** - Biggest latency reduction
2. **Incremental ASR Results** - Better UX, easy to add

### Phase 2: UX Improvements (2-3 days)
3. **VAD** - Hands-free operation
4. **Streaming TTS** - Faster responses

### Phase 3: Polish (1-2 days)
5. **Audio Stream Wrapper** - Cleaner architecture

## Alternative: Simpler Live Voice APIs

If you want something simpler than Grok but still live:

1. **Deepgram Streaming** - Simple WebSocket API, good docs
2. **AssemblyAI Streaming** - Very easy to use
3. **Google Speech-to-Text Streaming** - Reliable, well-documented
4. **Azure Speech Services** - Good streaming support

These are simpler than Grok's LiveKit setup but still provide real-time streaming.

## Code Examples

See the implementation files in `src/device/audio-streaming.ts` and `src/cloud-api/streaming-asr.ts` for reference implementations.

