import { useRef, useState, useCallback } from "react";
import { PCMPlayer } from "../utils/audioProcessing";
import { WS_URL } from "../config/settings";
import { SAMPLE_RATE, FRAME_SAMPLES, TTS_SAMPLE_RATE } from "../utils/constants";

export const useVoiceWebSocket = () => {
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const sourceRef = useRef(null);
  const workletNodeRef = useRef(null);

  const pcmPlayerRef = useRef(null);
  const bargeInActiveRef = useRef(false);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPlayingTTS, setIsPlayingTTS] = useState(false);

  const [currentTranscript, setCurrentTranscript] = useState("");
  const [transcripts, setTranscripts] = useState([]);
  const [latestLatency, setLatestLatency] = useState(null);

  /* -------------------- AUDIO OUTPUT (TTS) -------------------- */

  const setupPCMPlayer = useCallback(async () => {
    pcmPlayerRef.current?.stop();
    pcmPlayerRef.current = new PCMPlayer(TTS_SAMPLE_RATE); // Use configurable TTS sample rate
    await pcmPlayerRef.current.init();
    return true;
  }, []);

  const enableAudioPlayback = useCallback(async () => {
    try {
      await pcmPlayerRef.current?.resume();
      return true;
    } catch {
      return false;
    }
  }, []);

  const stopTTS = useCallback(() => {
    setIsPlayingTTS(false);
    pcmPlayerRef.current?.stop();
  }, []);

  /* -------------------- AUDIO INPUT (WORKLET) -------------------- */

  const startMicStream = useCallback(async () => {
    if (isStreaming) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    audioContextRef.current = new AudioContext({ sampleRate: SAMPLE_RATE });
    await audioContextRef.current.resume();

    await audioContextRef.current.audioWorklet.addModule("/pcm-worklet.js");

    sourceRef.current = audioContextRef.current.createMediaStreamSource(stream);

    workletNodeRef.current = new AudioWorkletNode(
      audioContextRef.current,
      "pcm-worklet",
      {
        processorOptions: {
          frameSamples: FRAME_SAMPLES,
        },
      }
    );

    workletNodeRef.current.port.onmessage = (e) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(e.data);
      }
    };

    sourceRef.current.connect(workletNodeRef.current);
    workletNodeRef.current.connect(audioContextRef.current.destination);

    setIsStreaming(true);
    setConnectionStatus("Streaming mic audio...");
  }, [isStreaming]);

  const stopMicStream = useCallback(() => {
    if (!isStreaming) return;

    workletNodeRef.current?.disconnect();
    sourceRef.current?.disconnect();
    audioContextRef.current?.close();

    setIsStreaming(false);
  }, [isStreaming]);

  /* -------------------- WEBSOCKET -------------------- */

  const handleWebSocketMessage = useCallback((event) => {
    // 🔊 Binary audio (TTS)
    if (event.data instanceof ArrayBuffer) {
      console.log(
        `🎵 Received binary audio chunk: ${event.data.byteLength} bytes`
      );
      if (bargeInActiveRef.current) {
        console.log("⏸️ Barge-in active, ignoring audio chunk");
        return;
      }
      pcmPlayerRef.current?.playChunk(event.data);
      return;
    }

    if (typeof event.data !== "string") {
      console.warn(
        "⚠️ Received non-string, non-ArrayBuffer message:",
        typeof event.data
      );
      return;
    }

    console.log("📨 Received text message:", event.data);
    let message;
    try {
      message = JSON.parse(event.data);
      console.log("✅ Parsed message:", message);
    } catch (error) {
      console.warn("❌ Non-JSON message:", event.data, error);
      return;
    }

    // Handle both 'type' (backend) and 'event' (legacy) message formats
    const msgType = message.type || message.event;
    
    // Log message type for debugging
    if (msgType === "transcription" || msgType === "asr_final" || msgType === "asr_partial") {
      console.log("🔍 ASR message detected:", msgType, message);
    }

    // 📝 Backend transcription (from ASR)
    if (msgType === "transcription") {
      const transcription = message.text || "";
      
      if (!transcription || transcription.trim() === "") {
        console.warn("⚠️ Received empty transcription, skipping");
        return;
      }

      console.log("📝 Processing transcription:", transcription);
      
      // Update current transcript immediately
      setCurrentTranscript(transcription);

      // Add to transcripts list, avoiding duplicates
      setTranscripts((prev) => {
        // Check if this transcription already exists (avoid duplicates)
        const existingIndex = prev.findIndex(
          (t) => t.asrText === transcription && !t.chatbotResponse
        );
        
        if (existingIndex >= 0) {
          // Update existing transcript with latencies if provided
          const updated = [...prev];
          updated[existingIndex] = {
            ...updated[existingIndex],
            latencies: message.latencies || updated[existingIndex].latencies,
          };
          console.log("📝 Updated existing transcript");
          return updated;
        }

        // Add new transcript
        const newTranscript = {
          id: Date.now(),
          asrText: transcription,
          chatbotResponse: "",
          latencies: message.latencies || {},
          timestamp: new Date().toLocaleTimeString(),
        };
        console.log("📝 Added new transcript:", newTranscript);
        return [...prev, newTranscript];
      });
      
      if (message.latencies) {
        setLatestLatency(message.latencies);
      }
    }

    // 📝 ASR events (legacy format)
    if (msgType === "asr_partial" || msgType === "asr_final") {
      const text = message.text || "";
      setCurrentTranscript(text);

      if (msgType === "asr_final" && text && text.trim() !== "") {
        console.log("📝 Processing ASR final:", text);
        
        setTranscripts((prev) => {
          // Check if this transcription already exists
          const existingIndex = prev.findIndex(
            (t) => t.asrText === text && !t.chatbotResponse
          );
          
          if (existingIndex >= 0) {
            // Update existing transcript
            const updated = [...prev];
            updated[existingIndex] = {
              ...updated[existingIndex],
              latencies: message.latencies || updated[existingIndex].latencies,
            };
            return updated;
          }

          // Add new transcript
          return [
            ...prev,
            {
              id: Date.now(),
              asrText: text,
              chatbotResponse: "",
              latencies: message.latencies || {},
              timestamp: new Date().toLocaleTimeString(),
            },
          ];
        });
        
        if (message.latencies) {
          setLatestLatency(message.latencies);
        }
      }
    }

    // 👤 User transcript (agent pipelines)
    if (msgType === "user_transcript") {
      setCurrentTranscript(message.text || "");

      setTranscripts((prev) => [
        ...prev,
        {
          id: Date.now(),
          asrText: message.text,
          chatbotResponse: "",
          latencies: {},
          timestamp: new Date().toLocaleTimeString(),
          agentType: message.agent_type,
        },
      ]);
    }

    // 🤖 LLM response
    if (msgType === "llm_response") {
      setTranscripts((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last) {
          last.chatbotResponse = message.response || "";
          last.latencies = message.latencies || last.latencies;
        }
        return updated;
      });
      setLatestLatency(message.latencies);
    }

    // 🤖 Agent response (ElevenLabs / others)
    if (msgType === "agent_response") {
      setTranscripts((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last) {
          last.chatbotResponse = message.text || "";
        }
        return updated;
      });
      setIsPlayingTTS(true);
    }

    // 🔄 Agent correction
    if (msgType === "agent_correction") {
      setTranscripts((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last && last.chatbotResponse === message.original) {
          last.chatbotResponse = message.corrected;
        }
        return updated;
      });
    }

    // 🧾 Legacy combined transcript
    if (msgType === "transcript") {
      setTranscripts((prev) => [
        ...prev,
        {
          id: Date.now(),
          asrText: message.asr_response || "",
          chatbotResponse: message.chatbot_response || "",
          latencies: message.latencies || {},
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
      setLatestLatency(message.latencies);
    }

    // 🤖 Bot message (questions from TTS)
    if (msgType === "bot_message") {
      console.log("🤖 Bot message received:", message.text);
      setTranscripts((prev) => [
        ...prev,
        {
          id: Date.now(),
          asrText: "",
          chatbotResponse: message.text || "",
          latencies: {},
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    }

    // 🎵 TTS lifecycle - Backend uses 'type: "tts_start"'
    if (msgType === "tts_start") {
      bargeInActiveRef.current = false;
      if (pcmPlayerRef.current) {
        pcmPlayerRef.current.isPlaying = true;
        pcmPlayerRef.current.fadeInFull();
      }
      setIsPlayingTTS(true);

      // Notify backend that TTS started
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "tts_started" }));
      }
    }

    if (msgType === "tts_end" || msgType === "end") {
      setIsPlayingTTS(false);

      // Notify backend that TTS finished - this enables mic for VAD
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "tts_finished" }));
      }
    }

    // 🎤 Mic enabled notification from backend
    if (msgType === "mic_enabled") {
      setConnectionStatus(message.message || "Microphone is now active");
    }

    // 🔌 WebSocket ready notification
    if (msgType === "websocket_ready") {
      console.log("✅ WebSocket ready on backend");
      setConnectionStatus("Connected. Waiting for call to start...");
    }

    // 📞 Call starting notification
    if (msgType === "call_starting") {
      console.log("📞 Call is starting:", message.message);
      setConnectionStatus(message.message || "Call starting...");
    }

    // 📋 Session created
    if (msgType === "session_created") {
      console.log("Session created:", message.session_id);
      setConnectionStatus(`Session: ${message.session_id}`);
    }

    // ✅ Survey completed
    if (msgType === "survey_completed" || msgType === "survey_ended") {
      setConnectionStatus(message.message || "Survey completed");
      setIsStreaming(false);
    }

    // 🛑 Barge-in detection
    if (msgType === "barge_in" || message.event === "barge_in") {
      console.log("Barge-in detected. confidence: ", message.confidence);
      if (bargeInActiveRef.current) return;

      bargeInActiveRef.current = true;

      pcmPlayerRef.current?.fadeOutFast();
      setTimeout(() => {
        pcmPlayerRef.current?.stop();
        setIsPlayingTTS(false);
      }, 25);
      return;
    }

    // 📊 Latency
    if (msgType === "latency_report") {
      setLatestLatency(message.latencies);
    }

    // ❌ Errors
    if (msgType === "error") {
      console.error("❌ Server error:", message.message);
      setConnectionStatus(`Error: ${message.message}`);
      // Add error to transcripts so it shows in UI
      setTranscripts((prev) => [
        ...prev,
        {
          id: Date.now(),
          asrText: "",
          chatbotResponse: `Error: ${message.message}`,
          latencies: {},
          timestamp: new Date().toLocaleTimeString(),
        },
      ]);
    }
  }, []);

  const connect = useCallback(
    async (
      agentType = "traditional",
      sessionId = null,
      customerName = null
    ) => {
      console.log("🔗 Connecting to WebSocket:", WS_URL);

      console.log("🚀 Creating WebSocket connection...");
      try {
        wsRef.current = new WebSocket(WS_URL);
        wsRef.current.binaryType = "arraybuffer";
      } catch (err) {
        console.error("❌ Failed to create WebSocket:", err);
        setConnectionStatus(`WebSocket error: ${err.message}`);
        return;
      }

      wsRef.current.onopen = async () => {
        console.log(
          "🔌 WebSocket opened, readyState:",
          wsRef.current?.readyState
        );
        setIsConnected(true);
        setConnectionStatus("WebSocket connected, initializing...");

        // Small delay to ensure WebSocket is fully ready
        await new Promise((resolve) => setTimeout(resolve, 100));

        // For outbound calls, sessionId and customerName are REQUIRED
        if (sessionId && customerName) {
          console.log(
            `📞 Preparing init_session: sessionId=${sessionId}, customerName=${customerName}`
          );
          const message = {
            type: "init_session",
            session_id: sessionId,
            customer_name: customerName,
          };
          console.log(
            "📤 Sending init_session message:",
            JSON.stringify(message)
          );

          if (wsRef.current?.readyState === WebSocket.OPEN) {
            try {
              wsRef.current.send(JSON.stringify(message));
              console.log("✅ init_session message sent successfully");
              setConnectionStatus("Call starting...");
            } catch (err) {
              console.error("❌ Error sending init_session:", err);
              setConnectionStatus(
                `Error: Failed to send message - ${err.message}`
              );
            }
          } else {
            console.error(
              "❌ WebSocket not open! readyState:",
              wsRef.current?.readyState
            );
            setConnectionStatus("Error: WebSocket not ready");
          }
        } else {
          console.error(
            "❌ ERROR: sessionId and customerName are required for outbound calls"
          );
          setConnectionStatus("Error: Missing session information");
          wsRef.current.close();
          return;
        }

        // Setup audio in parallel (non-blocking)
        console.log("🎵 Setting up PCM player...");
        setupPCMPlayer()
          .then(() => {
            console.log("✅ PCM player setup complete");
            console.log("🎤 Starting mic stream...");
            return startMicStream();
          })
          .then(() => {
            console.log("✅ Mic stream started");
            // Don't override status if call is already starting
            if (
              !connectionStatus.includes("starting") &&
              !connectionStatus.includes("active")
            ) {
              setConnectionStatus("Call active - listening...");
            }
          })
          .catch((err) => {
            console.error("❌ Audio setup error:", err);
            setConnectionStatus(`Audio setup error: ${err.message}`);
          });
      };

      wsRef.current.onmessage = handleWebSocketMessage;

      wsRef.current.onclose = (event) => {
        console.log("🔌 WebSocket closed:", event.code, event.reason);
        setConnectionStatus(`Disconnected (${event.code})`);
        setIsConnected(false);
        stopMicStream();
        pcmPlayerRef.current?.destroy();
      };

      wsRef.current.onerror = (error) => {
        console.error("❌ WebSocket error:", error);
        setConnectionStatus("WebSocket connection failed");
        setIsConnected(false);
        stopMicStream();
      };
    },
    [handleWebSocketMessage, setupPCMPlayer, startMicStream, stopMicStream]
  );

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    stopMicStream();
    pcmPlayerRef.current?.destroy();
    setIsConnected(false);
    setConnectionStatus("Disconnected");
  }, [stopMicStream]);

  /* -------------------- PUBLIC HELPERS -------------------- */

  const sendData = useCallback((payload) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    const metadata = {
      vani_email: localStorage.getItem("vani_email"),
      vani_username: localStorage.getItem("vani_username"),
      google_user_id: localStorage.getItem("google_user_id"),
    };

    wsRef.current.send(JSON.stringify({ ...metadata, ...payload }));
  }, []);

  const sendTTSRequest = useCallback(
    (text, provider = "elevenlabs") => {
      sendData({
        event: "tts_request",
        id: `utt-${Date.now()}`,
        text,
        provider,
      });
    },
    [sendData]
  );

  const clearTranscripts = useCallback(() => {
    setTranscripts([]);
    setCurrentTranscript("");
    setLatestLatency(null);
  }, []);

  const addWelcomeMessage = useCallback((text) => {
    setTranscripts((prev) => [
      {
        id: Date.now(),
        asrText: "",
        chatbotResponse: text,
        latencies: {},
        timestamp: new Date().toLocaleTimeString(),
      },
      ...prev,
    ]);
  }, []);

  const setAgentType = useCallback((agentType) => {
    localStorage.setItem("vani_agent_type", agentType);
  }, []);

  /* -------------------- CANONICAL PUBLIC API -------------------- */

  return {
    isConnected,
    connectionStatus,
    isStreaming,
    isPlayingTTS,
    currentTranscript,
    transcripts,
    latestLatency,

    connect,
    disconnect,
    sendData,
    sendTTSRequest,
    clearTranscripts,
    stopTTS,
    enableAudioPlayback,
    addWelcomeMessage,
    setAgentType,
  };
};
