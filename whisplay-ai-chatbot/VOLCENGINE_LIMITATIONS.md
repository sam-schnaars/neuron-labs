# Volcengine ASR Streaming - Limitations & Fixes

## Current Issues

After reviewing the code, here are the problems with using Volcengine for true streaming:

### 1. **Result Type is "full" not "incremental"**

**Line 136 in `volcengine-asr.ts`:**
```typescript
result_type: "full",  // ❌ This waits for complete result
```

**Problem**: Volcengine won't return partial results - it waits for the full transcription.

**Fix**: Change to `"incremental"` or `"partial"`:
```typescript
result_type: "incremental",  // ✅ Returns partial results
```

### 2. **Response Parsing Doesn't Check `is_final`**

**Line 254 in `volcengine-asr.ts`:**
```typescript
const astText = data?.result?.[0]?.text || "";
```

**Problem**: Doesn't check if result is partial or final.

**Fix**: Check the `is_final` flag:
```typescript
const result = data?.result?.[0];
const text = result?.text || "";
const isFinal = result?.is_final ?? true; // Default to final if not specified
```

### 3. **Audio Format Mismatch**

**Line 56**: `format: "mp3"` but streaming needs raw PCM
**Line 57**: `codec: "raw"` - this is correct

**Problem**: The format says "mp3" but codec is "raw" - this might confuse the API.

**Fix**: For streaming, should use:
```typescript
format: "pcm",  // or "raw"
codec: "pcm",   // raw PCM
```

## What WILL Work

✅ **Streaming audio chunks** - The WebSocket can receive chunks
✅ **Lower latency** - Sending chunks is faster than file-based
✅ **VAD in workflow** - Already includes VAD: `"audio_in,resample,partition,vad,fe,decode"`

## What WON'T Work (Without Fixes)

❌ **Partial/incremental results** - Currently set to "full" only
❌ **Real-time transcription** - Won't show text as you speak

## Solutions

### Option 1: Fix Volcengine Implementation (Recommended)

Modify `volcengine-asr.ts`:

```typescript
// Line 136 - Change result_type
result_type: "incremental",  // or "partial" depending on API

// Line 254 - Check is_final flag
client.onMessage = (data) => {
  const result = data?.result?.[0];
  if (!result) return;
  
  const text = result.text || "";
  const isFinal = result.is_final ?? true;
  
  if (isFinal) {
    console.log("Final result:", text);
    recognizeResolve(text);
  } else {
    console.log("Partial result:", text);
    // Emit partial result event
    // You'd need to add this to the client
  }
};
```

### Option 2: Use Alternative Streaming ASR APIs

These are simpler and better documented for streaming:

#### **Deepgram Streaming** (Recommended)
- Very simple WebSocket API
- Excellent documentation
- Supports partial results out of the box
- Good latency

#### **AssemblyAI Streaming**
- Easy to use
- Well-documented
- Supports partial results

#### **Google Speech-to-Text Streaming**
- Reliable
- Well-documented
- Supports partial results
- Good for production

#### **OpenAI Whisper API** (if they add streaming)
- Currently file-based only

### Option 3: Hybrid Approach

1. Use Volcengine for **streaming audio chunks** (lower latency)
2. Accept that you'll only get **final results** (not partial)
3. Still get the latency benefit from streaming vs file-based

This is still an improvement! You save 1-2 seconds from not writing/reading files.

## Recommendation

**For true streaming with partial results**: Use Deepgram or AssemblyAI

**For Volcengine with streaming chunks (final results only)**: Fix the implementation to properly stream chunks, but accept final-only results. Still better than file-based!

## Quick Test

To verify if Volcengine supports incremental results:

1. Change `result_type: "incremental"` in the request
2. Check if responses include `is_final: false` for partial results
3. If not, the API might not support it, and you should use an alternative




