import { SAMPLE_RATE, TTS_SAMPLE_RATE } from "./constants";

// =====================================================================
//                    TTS FRONTEND FOR PCM STREAMING (FIXED)
// =====================================================================

export const convertFloat32ToInt16 = (float32Array) => {
  const int16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    let s = Math.max(-1, Math.min(1, float32Array[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16;
};

export const playAudioFromBase64 = (base64String, callbacks) => {
  try {
    const audio = new Audio(`data:audio/mp3;base64,${base64String}`);
    audio.onplay = callbacks.onPlay;
    audio.onended = callbacks.onEnd;
    audio.onerror = callbacks.onError;
    audio.play().catch(callbacks.onError);
    return audio;
  } catch (error) {
    callbacks.onError(error);
    return null;
  }
};

// =====================================================================
//           ⭐ PCM STREAMING FOR HTTP API
// =====================================================================

export const streamTTSAudio = async (
  text,
  apiUrl = "http://localhost:5057/synthesize",
  callbacks = {}
) => {
  const {
    onStart = () => {},
    onChunk = () => {},
    onEnd = () => {},
    onError = (err) => console.error(err),
  } = callbacks;

  let audioContext = null;
  let isPlaying = true;
  let scheduledTime = 0;
  const activeNodes = [];

  try {
    console.log("🎵 Initializing PCM audio context...");

    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: TTS_SAMPLE_RATE,
    });

    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }

    console.log(`✅ Audio context ready: ${audioContext.state}`);
    onStart();

    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    console.log("✅ Stream connected");
    const reader = response.body.getReader();
    scheduledTime = audioContext.currentTime;
    let chunkCount = 0;

    while (isPlaying) {
      const { done, value } = await reader.read();

      if (done) {
        console.log("✅ Stream finished");
        break;
      }

      chunkCount++;
      console.log(`📦 Chunk ${chunkCount}: ${value.length} bytes`);

      const int16Array = new Int16Array(value.buffer);
      const float32Array = new Float32Array(int16Array.length);

      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }

      const audioBuffer = audioContext.createBuffer(
        1,
        float32Array.length,
        audioContext.sampleRate
      );

      audioBuffer.getChannelData(0).set(float32Array);

      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);

      const startTime = Math.max(scheduledTime, audioContext.currentTime);
      source.start(startTime);

      scheduledTime = startTime + audioBuffer.duration;
      activeNodes.push(source);

      console.log(`▶️ Scheduled at ${startTime.toFixed(3)}s`);
      onChunk(value.length);
    }

    const remainingTime = scheduledTime - audioContext.currentTime;
    if (remainingTime > 0) {
      await new Promise((resolve) =>
        setTimeout(resolve, remainingTime * 1000 + 100)
      );
    }

    console.log("✅ Playback completed");
    onEnd();
  } catch (error) {
    console.error("❌ PCM streaming error:", error);
    onError(error);
  } finally {
    activeNodes.forEach((node) => {
      try {
        node.disconnect();
      } catch (e) {}
    });

    if (audioContext && audioContext.state !== "closed") {
      await audioContext.close();
    }
  }

  return {
    stop: () => {
      isPlaying = false;
      activeNodes.forEach((node) => {
        try {
          node.stop();
        } catch (e) {}
      });
      if (audioContext && audioContext.state !== "closed") {
        audioContext.close();
      }
    },
  };
};

// =====================================================================
//           ⭐ NEW: PCM PLAYER CLASS FOR WEBSOCKET STREAMING
// =====================================================================

export class PCMPlayer {
  constructor(sampleRate = 24000) {
    this.sampleRate = sampleRate;
    this.audioContext = null;
    this.scheduledTime = 0;
    this.isPlaying = false;
    this.activeNodes = [];
    this.chunkQueue = [];
    this.isProcessingQueue = false;
    this.minBufferTime = 0.1; // 100ms buffer to smooth playback
  }

  async init() {
    if (this.audioContext) {
      console.warn("PCMPlayer already initialized");
      return;
    }

    console.log("🎵 Initializing PCM Player...");
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: this.sampleRate,
    });

    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
    }

    this.gainNode = this.audioContext.createGain();
    this.gainNode.gain.setValueAtTime(1.0, this.audioContext.currentTime);
    this.gainNode.connect(this.audioContext.destination);

    // Initialize scheduledTime with a small buffer to prevent gaps
    this.scheduledTime = this.audioContext.currentTime + this.minBufferTime;
    this.isPlaying = true;
    this.chunkQueue = [];
    this.isProcessingQueue = false;

    console.log(`✅ PCM Player ready: ${this.audioContext.state}`);
  }

  async processQueue() {
    if (this.isProcessingQueue || !this.isPlaying) {
      return;
    }

    this.isProcessingQueue = true;

    try {
      while (this.chunkQueue.length > 0 && this.isPlaying) {
        const chunkData = this.chunkQueue.shift();
        this.playChunkInternal(chunkData);
        
        // Small delay to prevent blocking and allow other chunks to queue
        if (this.chunkQueue.length > 0) {
          await new Promise(resolve => setTimeout(resolve, 0));
        }
      }
    } finally {
      this.isProcessingQueue = false;
    }
  }

  playChunk(pcmData) {
    if (!this.audioContext || !this.isPlaying) {
      console.warn("PCMPlayer not initialized or stopped");
      return;
    }

    // Add to queue for smoother playback
    this.chunkQueue.push(pcmData);
    
    // Process queue asynchronously (don't await to avoid blocking)
    if (!this.isProcessingQueue) {
      this.processQueue().catch(err => {
        console.error("Error processing audio queue:", err);
      });
    }
  }

  playChunkInternal(pcmData) {
    if (!this.audioContext || !this.isPlaying) {
      return;
    }

    try {
      // Convert ArrayBuffer to Int16Array
      const int16Array = new Int16Array(pcmData);
      if (int16Array.length === 0) {
        return;
      }

      const float32Array = new Float32Array(int16Array.length);

      // Convert Int16 PCM to Float32 with proper normalization
      for (let i = 0; i < int16Array.length; i++) {
        // Normalize to [-1, 1] range
        float32Array[i] = Math.max(-1, Math.min(1, int16Array[i] / 32768.0));
      }

      // Create audio buffer with correct sample rate
      const audioBuffer = this.audioContext.createBuffer(
        1,
        float32Array.length,
        this.sampleRate
      );

      audioBuffer.getChannelData(0).set(float32Array);

      // Create and schedule source
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.gainNode);

      // Ensure we schedule ahead of current time to prevent gaps
      const now = this.audioContext.currentTime;
      let startTime = Math.max(this.scheduledTime, now + 0.01); // Small lookahead
      
      // If scheduledTime is too far in the past, reset it
      if (this.scheduledTime < now - 0.1) {
        startTime = now + this.minBufferTime;
        this.scheduledTime = startTime;
      }

      source.start(startTime);
      this.scheduledTime = startTime + audioBuffer.duration;
      this.activeNodes.push(source);

      // Clean up finished nodes periodically
      this.cleanupFinishedNodes();
    } catch (error) {
      console.error("❌ Error playing PCM chunk:", error);
    }
  }

  cleanupFinishedNodes() {
    // Keep only recent nodes, remove old ones
    if (this.activeNodes.length > 50) {
      const toRemove = this.activeNodes.splice(0, 25);
      toRemove.forEach((node) => {
        try {
          if (node.buffer) {
            node.disconnect();
          }
        } catch (e) {
          // Node may already be disconnected
        }
      });
    }
  }

  stop() {
    console.log("🛑 Flushing PCM Player (not destroying)");

    this.isPlaying = false;
    this.chunkQueue = [];
    this.isProcessingQueue = false;

    if (this.gainNode && this.audioContext) {
      const now = this.audioContext.currentTime;
      this.gainNode.gain.cancelScheduledValues(now);
      this.gainNode.gain.setValueAtTime(0.0, now);
    }

    this.activeNodes.forEach((node) => {
      try {
        node.stop();
        node.disconnect();
      } catch {}
    });

    this.activeNodes = [];
    if (this.audioContext) {
      this.scheduledTime = this.audioContext.currentTime;
    }
  }

  destroy() {
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
    }
    this.audioContext = null;
    this.gainNode = null;
  }

  fadeOutFast() {
    if (!this.gainNode) return;
    const now = this.audioContext.currentTime;
    this.gainNode.gain.cancelScheduledValues(now);
    this.gainNode.gain.setValueAtTime(this.gainNode.gain.value, now);
    this.gainNode.gain.linearRampToValueAtTime(0.0, now + 0.02);
  }

  fadeInFull() {
    if (!this.gainNode) return;
    const now = this.audioContext.currentTime;
    this.gainNode.gain.cancelScheduledValues(now);
    this.gainNode.gain.setValueAtTime(0.0, now);
    this.gainNode.gain.linearRampToValueAtTime(1.0, now + 0.05);
  }

  async resume() {
    if (this.audioContext && this.audioContext.state === "suspended") {
      await this.audioContext.resume();
      console.log("✅ PCM Player resumed");
    }
  }
}
