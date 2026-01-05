import moment from "moment";
import {
  getCurrentTimeTag,
  getRecordFileDurationMs,
  splitSentences,
} from "./../utils/index";
import { get, noop } from "lodash";
import {
  onButtonPressed,
  onButtonReleased,
  onButtonDoubleClick,
  display,
  getCurrentStatus,
  onCameraCapture,
} from "../device/display";
import { recordAudioManually, recordFileFormat } from "../device/audio";
import {
  recognizeAudio,
  chatWithLLMStream,
  ttsProcessor,
  asrServer,
} from "../cloud-api/server";
import { extractEmojis } from "../utils";
import { StreamResponser } from "./StreamResponsor";
import { cameraDir, recordingsDir } from "../utils/dir";
import { getLatestDisplayImg, setLatestCapturedImg } from "../utils/image";
import { StreamingAudioWithVAD } from "../device/audio-streaming";
import { StreamingASR } from "../cloud-api/streaming-asr";
import { ASRServer } from "../type";
import { byteDanceAppId, byteDanceAccessToken } from "../cloud-api/volcengine/volcengine";
import dotenv from "dotenv";

dotenv.config();

class ChatFlow {
  currentFlowName: string = "";
  recordingsDir: string = "";
  currentRecordFilePath: string = "";
  asrText: string = "";
  streamResponser: StreamResponser;
  partialThinking: string = "";
  thinkingSentences: string[] = [];
  answerId: number = 0;
  enableCamera: boolean = false;
  audioStream: StreamingAudioWithVAD | null = null;
  streamingASR: StreamingASR | null = null;
  useVAD: boolean = true;
  isVADActive: boolean = false;
  isUsingStreamingASR: boolean = false;
  isVADTriggered: boolean = false; // Track if listening was triggered by VAD or button

  constructor(options: { enableCamera?: boolean } = {}) {
    console.log(`[${getCurrentTimeTag()}] ChatBot started.`);
    this.recordingsDir = recordingsDir;
    
    // Initialize VAD if enabled
    this.useVAD = process.env.USE_VAD !== "false";
    
    if (this.useVAD) {
      try {
        // Initialize StreamingAudioWithVAD with configurable options
        const vadThreshold = parseInt(process.env.VAD_THRESHOLD || "500", 10);
        const vadSilenceDuration = parseInt(process.env.VAD_SILENCE_DURATION || "1500", 10);
        
        this.audioStream = new StreamingAudioWithVAD({
          sampleRate: 16000,
          channels: 1,
          vadThreshold,
          vadSilenceDuration,
        });
        
        // Initialize StreamingASR only if Volcengine is configured
        if (asrServer === ASRServer.volcengine && byteDanceAppId && byteDanceAccessToken) {
          this.streamingASR = new StreamingASR({
            server: ASRServer.volcengine,
          });
          this.isUsingStreamingASR = true;
          console.log(`[${getCurrentTimeTag()}] Streaming ASR initialized with Volcengine`);
        } else {
          console.log(`[${getCurrentTimeTag()}] Streaming ASR not available, will use file-based ASR as fallback`);
          this.isUsingStreamingASR = false;
        }
        
        this.setupVADHandlers();
      } catch (error) {
        console.error(`[${getCurrentTimeTag()}] Failed to initialize VAD:`, error);
        this.useVAD = false;
        this.audioStream = null;
        this.streamingASR = null;
      }
    } else {
      console.log(`[${getCurrentTimeTag()}] VAD disabled via USE_VAD=false`);
    }
    
    this.setCurrentFlow("sleep");
    this.streamResponser = new StreamResponser(
      ttsProcessor,
      (sentences: string[]) => {
        if (this.currentFlowName !== "answer") return;
        const fullText = sentences.join(" ");
        display({
          status: "answering",
          emoji: extractEmojis(fullText) || "😊",
          text: fullText,
          RGB: "#0000ff",
          scroll_speed: 3,
        });
      },
      (text: string) => {
        if (this.currentFlowName !== "answer") return;
        display({
          status: "answering",
          text: text || undefined,
          scroll_speed: 3,
        });
      }
    );
    if (options?.enableCamera) {
      this.enableCamera = true;
    }
  }

  setupVADHandlers(): void {
    if (!this.audioStream) return;

    // Handle speech detection
    this.audioStream.on("speech-start", () => {
      if (this.currentFlowName !== "sleep") return;
      console.log(`[${getCurrentTimeTag()}] Speech detected, starting recognition...`);
      this.isVADTriggered = true;
      this.setCurrentFlow("listening");
    });

    // Handle speech end
    this.audioStream.on("speech-end", (audioData: Buffer) => {
      if (this.currentFlowName !== "listening") return;
      console.log(`[${getCurrentTimeTag()}] Speech ended, processing...`);
      
      if (this.isUsingStreamingASR && this.streamingASR) {
        // Send final audio chunk and get result
        this.streamingASR.sendAudioChunk(audioData);
        this.streamingASR.end().then((text) => {
          if (this.currentFlowName !== "listening") return;
          if (text) {
            console.log(`[${getCurrentTimeTag()}] Audio recognized result:`, text);
            this.asrText = text;
            display({ status: "recognizing", text: text });
            this.setCurrentFlow("asr");
          } else {
            console.log(`[${getCurrentTimeTag()}] No text recognized, returning to sleep`);
            this.setCurrentFlow("sleep");
          }
        }).catch((err) => {
          console.error(`[${getCurrentTimeTag()}] Error during streaming ASR:`, err);
          this.setCurrentFlow("sleep");
        });
      } else {
        // Fallback: save to file and use file-based ASR
        // This shouldn't normally happen if VAD is working, but handle it gracefully
        console.log(`[${getCurrentTimeTag()}] Streaming ASR not available, falling back to button mode`);
        this.setCurrentFlow("sleep");
      }
    });

    // Handle audio chunks during speech (for streaming ASR)
    this.audioStream.on("audio-chunk", (chunk: Buffer) => {
      if (this.currentFlowName === "listening" && this.isUsingStreamingASR && this.streamingASR) {
        this.streamingASR.sendAudioChunk(chunk);
      }
    });

    // Handle partial ASR results (real-time feedback)
    if (this.streamingASR) {
      this.streamingASR.on("partial-result", (text: string) => {
        if (this.currentFlowName === "listening") {
          display({
            status: "listening",
            text: text,
            RGB: "#00ff00",
          });
        }
      });

      this.streamingASR.on("final-result", (text: string) => {
        if (this.currentFlowName === "listening") {
          console.log(`[${getCurrentTimeTag()}] Final ASR result:`, text);
          display({
            status: "recognizing",
            text: text,
          });
        }
      });

      this.streamingASR.on("error", (error: Error) => {
        console.error(`[${getCurrentTimeTag()}] Streaming ASR error:`, error);
        if (this.currentFlowName === "listening" || this.currentFlowName === "asr") {
          this.setCurrentFlow("sleep");
        }
      });
    }

    // Handle VAD errors
    this.audioStream.on("error", (error: Error) => {
      console.error(`[${getCurrentTimeTag()}] VAD error:`, error);
      this.isVADActive = false;
      // Fallback to button mode on error
      if (this.currentFlowName === "sleep" || this.currentFlowName === "listening") {
        this.setCurrentFlow("sleep");
      }
    });
  }

  startVAD(): void {
    if (!this.useVAD || !this.audioStream || this.isVADActive) return;
    
    try {
      this.audioStream.start();
      this.isVADActive = true;
      if (this.isUsingStreamingASR && this.streamingASR) {
        // Reset streaming ASR for next use
        this.streamingASR.stop();
      }
      console.log(`[${getCurrentTimeTag()}] VAD started`);
    } catch (error) {
      console.error(`[${getCurrentTimeTag()}] Failed to start VAD:`, error);
      this.isVADActive = false;
    }
  }

  stopVAD(): void {
    if (!this.audioStream || !this.isVADActive) return;
    
    try {
      this.audioStream.stop();
      this.isVADActive = false;
      if (this.isUsingStreamingASR && this.streamingASR) {
        this.streamingASR.stop();
      }
      console.log(`[${getCurrentTimeTag()}] VAD stopped`);
    } catch (error) {
      console.error(`[${getCurrentTimeTag()}] Failed to stop VAD:`, error);
      this.isVADActive = false;
    }
  }

  async recognizeAudio(path: string): Promise<string> {
    if ((await getRecordFileDurationMs(path)) < 500) {
      console.log("Record audio too short, skipping recognition.");
      return Promise.resolve("");
    }
    return recognizeAudio(path);
  }

  partialThinkingCallback = (
    partialThinking: string,
  ): void => {
    this.partialThinking += partialThinking;
    const { sentences, remaining } = splitSentences(this.partialThinking);
    if (sentences.length > 0) {
      this.thinkingSentences.push(...sentences);
      const displayText = this.thinkingSentences.join(" ");
      display({
        status: "Thinking",
        emoji: "🤔",
        text: displayText,
        RGB: "#ff6800", // yellow
        scroll_speed: 6,
      });
    }
    this.partialThinking = remaining;
  };

  setCurrentFlow = (flowName: string): void => {
    console.log(`[${getCurrentTimeTag()}] switch to:`, flowName);
    switch (flowName) {
      case "sleep":
        this.currentFlowName = "sleep";
        
        // Start VAD if enabled
        if (this.useVAD) {
          this.startVAD();
        }
        
        // Keep button press as fallback option
        onButtonPressed(() => {
          // Stop VAD if active (button takes precedence)
          if (this.isVADActive) {
            this.stopVAD();
          }
          this.isVADTriggered = false; // Button mode
          this.setCurrentFlow("listening");
        });
        onButtonReleased(noop);
        
        // camera mode
        if (this.enableCamera) {
          const captureImgPath = `${cameraDir}/capture-${moment().format(
            "YYYYMMDD-HHmmss"
          )}.jpg`;
          onButtonDoubleClick(() => {
            display({
              camera_mode: true,
              capture_image_path: captureImgPath,
            });
          });
          onCameraCapture(() => {
            setLatestCapturedImg(captureImgPath);
          });
        }
        
        const statusText = this.useVAD
          ? `Ready to listen...${this.enableCamera ? ",\ndouble click to launch camera" : ""}`
          : `Long Press the button to say something${this.enableCamera ? ",\ndouble click to launch camera" : ""}.`;
        
        display({
          status: "idle",
          emoji: "😴",
          RGB: "#000055",
          ...(getCurrentStatus().text === "Listening..."
            ? {
                text: statusText,
              }
            : {}),
        });
        break;
      case "listening":
        this.answerId += 1;
        this.currentFlowName = "listening";
        this.asrText = ""; // Clear previous ASR text
        
        // Check if this was triggered by VAD or button
        if (this.isVADTriggered && this.isUsingStreamingASR && this.streamingASR) {
          // VAD-triggered: Use streaming ASR
          this.isVADTriggered = false; // Reset flag
          
          // Start streaming ASR
          try {
            this.streamingASR.start();
            display({
              status: "listening",
              emoji: "😐",
              RGB: "#00ff00",
              text: "Listening...",
            });
          } catch (error) {
            console.error(`[${getCurrentTimeTag()}] Failed to start streaming ASR:`, error);
            this.setCurrentFlow("sleep");
          }
          
          // Button press can still interrupt and switch to manual mode
          onButtonPressed(() => {
            if (this.streamingASR) {
              this.streamingASR.stop();
            }
            this.isVADTriggered = false;
            // Restart with button mode
            this.setCurrentFlow("listening");
          });
          onButtonReleased(noop);
        } else {
          // Button-triggered: Use file-based recording (fallback)
          this.isVADTriggered = false; // Reset flag
          
          // Stop VAD if it was active
          if (this.isVADActive) {
            this.stopVAD();
          }
          
          this.currentRecordFilePath = `${
            this.recordingsDir
          }/user-${Date.now()}.${recordFileFormat}`;
          onButtonPressed(noop);
          const { result, stop } = recordAudioManually(
            this.currentRecordFilePath
          );
          onButtonReleased(() => {
            stop();
            display({
              RGB: "#ff6800", // yellow
            });
          });
          result
            .then(() => {
              this.setCurrentFlow("asr");
            })
            .catch((err) => {
              console.error("Error during recording:", err);
              this.setCurrentFlow("sleep");
            });
          display({
            status: "listening",
            emoji: "😐",
            RGB: "#00ff00",
            text: "Listening...",
          });
        }
        break;
      case "asr":
        this.currentFlowName = "asr";
        display({
          status: "recognizing",
        });
        onButtonDoubleClick(null);
        
        // Check if we already have text from streaming ASR
        if (this.asrText && this.isUsingStreamingASR) {
          // Streaming ASR already provided the result, go directly to answer
          console.log(`[${getCurrentTimeTag()}] Using streaming ASR result:`, this.asrText);
          display({ status: "recognizing", text: this.asrText });
          // Small delay to show the result, then proceed
          setTimeout(() => {
            if (this.currentFlowName === "asr") {
              this.setCurrentFlow("answer");
            }
          }, 500);
        } else {
          // File-based ASR: process the audio file
          Promise.race([
            this.recognizeAudio(this.currentRecordFilePath),
            new Promise<string>((resolve) => {
              onButtonPressed(() => {
                resolve("[UserPress]");
              });
              onButtonReleased(noop);
            }),
          ]).then((result) => {
            if (this.currentFlowName !== "asr") return;
            if (result === "[UserPress]") {
              this.setCurrentFlow("listening");
            } else {
              if (result) {
                console.log("Audio recognized result:", result);
                this.asrText = result;
                display({ status: "recognizing", text: result });
                this.setCurrentFlow("answer");
              } else {
                this.setCurrentFlow("sleep");
              }
            }
          });
        }
        break;
      case "answer":
        // Stop VAD before TTS playback to prevent feedback
        if (this.isVADActive) {
          this.stopVAD();
        }
        
        display({
          status: "answering...",
          RGB: "#00c8a3",
        });
        this.currentFlowName = "answer";
        const currentAnswerId = this.answerId;
        onButtonPressed(() => {
          this.setCurrentFlow("listening");
        });
        onButtonReleased(noop);
        const {
          partial,
          endPartial,
          getPlayEndPromise,
          stop: stopPlaying,
        } = this.streamResponser;
        this.partialThinking = "";
        this.thinkingSentences = [];
        chatWithLLMStream(
          [
            {
              role: "user",
              content: this.asrText,
            },
          ],
          (text) =>
            currentAnswerId === this.answerId && partial(text),
          () =>
            currentAnswerId === this.answerId && endPartial(),
          (partialThinking) =>
            currentAnswerId === this.answerId &&
            this.partialThinkingCallback(partialThinking),
          (functionName: string, result?: string) => {
            if (result) {
              display({
                text: `[${functionName}]${result}`,
              });
            } else {
              display({
                text: `Invoking [${functionName}]...`,
              });
            }
          }
        );
        getPlayEndPromise().then(() => {
          if (this.currentFlowName === "answer") {
            const img = getLatestDisplayImg();
            if (img) {
              display({
                image: img,
              });
              this.setCurrentFlow("image");
            } else {
              // Restart VAD before transitioning to sleep
              this.setCurrentFlow("sleep");
            }
          }
        });
        onButtonPressed(() => {
          stopPlaying();
          this.setCurrentFlow("listening");
        });
        onButtonReleased(noop);
        break;
      case "image":
        onButtonPressed(() => {
          display({ image: "" });
          this.setCurrentFlow("sleep");
        });
        onButtonReleased(noop);
        break;
      default:
        console.error("Unknown flow name:", flowName);
        break;
    }
  };
}

export default ChatFlow;
