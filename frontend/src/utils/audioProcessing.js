import { SAMPLE_RATE } from './constants';

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
        onStart = () => {
        },
        onChunk = () => {
        },
        onEnd = () => {
        },
        onError = (err) => console.error(err),
    } = callbacks;

    let audioContext = null;
    let isPlaying = true;
    let scheduledTime = 0;
    const activeNodes = [];

    try {
        console.log("🎵 Initializing PCM audio context...");

        audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 24000,
        });

        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }

        console.log(`✅ Audio context ready: ${audioContext.state}`);
        onStart();

        const response = await fetch(apiUrl, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text}),
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        console.log("✅ Stream connected");
        const reader = response.body.getReader();
        scheduledTime = audioContext.currentTime;
        let chunkCount = 0;

        while (isPlaying) {
            const {done, value} = await reader.read();

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
            await new Promise((resolve) => setTimeout(resolve, remainingTime * 1000 + 100));
        }

        console.log("✅ Playback completed");
        onEnd();
    } catch (error) {
        console.error("❌ PCM streaming error:", error);
        onError(error);
    } finally {
        activeNodes.forEach(node => {
            try {
                node.disconnect();
            } catch (e) {
            }
        });

        if (audioContext && audioContext.state !== 'closed') {
            await audioContext.close();
        }
    }

    return {
        stop: () => {
            isPlaying = false;
            activeNodes.forEach(node => {
                try {
                    node.stop();
                } catch (e) {
                }
            });
            if (audioContext && audioContext.state !== 'closed') {
                audioContext.close();
            }
        },
    };
};

// =====================================================================
//           ⭐ NEW: PCM PLAYER CLASS FOR WEBSOCKET STREAMING
// =====================================================================

export class PCMPlayer {
    constructor(sampleRate = 16000) {
        this.sampleRate = sampleRate;
        this.audioContext = null;
        this.scheduledTime = 0;
        this.isPlaying = false;
        this.activeNodes = [];
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

        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }

        this.gainNode = this.audioContext.createGain();
        this.gainNode.gain.setValueAtTime(1.0, this.audioContext.currentTime);
        this.gainNode.connect(this.audioContext.destination);

        this.scheduledTime = this.audioContext.currentTime;
        this.isPlaying = true;

        console.log(`✅ PCM Player ready: ${this.audioContext.state}`);
    }

    playChunk(pcmData) {
        if (!this.audioContext || !this.isPlaying) {
            console.warn("PCMPlayer not initialized or stopped");
            return;
        }

        try {
            // Convert ArrayBuffer to Int16Array
            const int16Array = new Int16Array(pcmData);
            const float32Array = new Float32Array(int16Array.length);

            // Convert Int16 PCM to Float32
            for (let i = 0; i < int16Array.length; i++) {
                float32Array[i] = int16Array[i] / 32768.0;
            }

            // Check for silence
            const maxAmplitude = Math.max(...float32Array.map(Math.abs));
            if (maxAmplitude === 0) {
                console.warn("⚠️ Received silent chunk");
            }

            // Create audio buffer
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

            const startTime = Math.max(this.scheduledTime, this.audioContext.currentTime);
            source.start(startTime);

            this.scheduledTime = startTime + audioBuffer.duration;
            this.activeNodes.push(source);

            console.log(`▶️ PCM chunk played (${float32Array.length} samples, ${maxAmplitude.toFixed(4)} max amplitude)`);
        } catch (error) {
            console.error("❌ Error playing PCM chunk:", error);
        }
    }

    stop() {
        console.log("🛑 Flushing PCM Player (not destroying)");

        this.isPlaying = false;

        if (this.gainNode) {
            const now = this.audioContext.currentTime;
            this.gainNode.gain.cancelScheduledValues(now);
            this.gainNode.gain.setValueAtTime(0.0, now);
        }

        this.activeNodes.forEach(node => {
            try {
                node.stop();
                node.disconnect();
            } catch {
            }
        });

        this.activeNodes = [];
        this.scheduledTime = this.audioContext.currentTime;
    }

    destroy() {
        if (this.audioContext && this.audioContext.state !== 'closed') {
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
        if (this.audioContext && this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
            console.log("✅ PCM Player resumed");
        }
    }
}

