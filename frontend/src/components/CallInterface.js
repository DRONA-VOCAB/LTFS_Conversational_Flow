import React, { useState, useEffect, useRef } from 'react';
import './CallInterface.css';

const CallInterface = ({ sessionId, customer, onCallEnd, apiBaseUrl }) => {
  const [isCallActive, setIsCallActive] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [conversationComplete, setConversationComplete] = useState(false);
  const [transcribedText, setTranscribedText] = useState('');
  const [callSummary, setCallSummary] = useState(null);
  const [error, setError] = useState(null);
  const [speechDetected, setSpeechDetected] = useState(false);
  const [speechProbability, setSpeechProbability] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [audioBars, setAudioBars] = useState(new Array(20).fill(0));

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const isPlayingRef = useRef(false);
  const currentAudioPromiseRef = useRef(Promise.resolve());
  const analyserRef = useRef(null);
  const animationFrameRef = useRef(null);
  const streamRef = useRef(null);
  const scriptProcessorRef = useRef(null);
  const isStreamingRef = useRef(false);
  const streamingPausedRef = useRef(false);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      // Disconnect script processor if it exists
      const scriptProcessor = scriptProcessorRef.current;
      if (scriptProcessor) {
        scriptProcessor.disconnect();
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      stopAudioPlayback();
    };
  }, []);

  // Audio level monitoring
  useEffect(() => {
    if (!isRecording || !analyserRef.current) return;

    const analyser = analyserRef.current;
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const bufferLength = analyser.frequencyBinCount;

    const updateAudioLevel = () => {
      if (!analyserRef.current) return;
      
      analyser.getByteFrequencyData(dataArray);
      
      // Calculate average audio level
      let sum = 0;
      for (let i = 0; i < bufferLength; i++) {
        sum += dataArray[i];
      }
      const average = sum / bufferLength;
      setAudioLevel(average);

      // Create equalizer bars (20 bars from frequency data)
      const bars = [];
      const barCount = 20;
      const step = Math.floor(bufferLength / barCount);
      for (let i = 0; i < barCount; i++) {
        let barSum = 0;
        for (let j = 0; j < step; j++) {
          barSum += dataArray[i * step + j] || 0;
        }
        bars.push(Math.min(100, (barSum / step) * 2));
      }
      setAudioBars(bars);

      animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
    };

    updateAudioLevel();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isRecording]);

  const stopAudioPlayback = () => {
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    isPlayingRef.current = false;
    // Reset the audio promise chain
    currentAudioPromiseRef.current = Promise.resolve();
  };

  const playAudio = async (audioData) => {
    if (!audioData || (audioData.byteLength !== undefined && audioData.byteLength === 0)) {
      console.warn('Empty or invalid audio data');
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      try {
        // Use HTML Audio element for better format support (WAV, MP3, OGG, WebM, etc.)
        const audio = new Audio();
        const blob = new Blob([audioData], { type: 'audio/wav' }); // Default to WAV, browser will try to decode
        const url = URL.createObjectURL(blob);
        
        audio.src = url;
        
        // Try to detect format from first bytes
        const firstBytes = new Uint8Array(audioData.slice(0, 12));
        let mimeType = 'audio/wav'; // Default
        
        // Check for WAV (RIFF...WAVE)
        if (firstBytes[0] === 0x52 && firstBytes[1] === 0x49 && firstBytes[2] === 0x46 && firstBytes[3] === 0x46) {
          mimeType = 'audio/wav';
        }
        // Check for MP3 (starts with FF FB, FF F3, or FF FA)
        else if (firstBytes[0] === 0xFF && (firstBytes[1] === 0xFB || firstBytes[1] === 0xF3 || firstBytes[1] === 0xFA)) {
          mimeType = 'audio/mpeg';
        }
        // Check for OGG (OggS)
        else if (firstBytes[0] === 0x4F && firstBytes[1] === 0x67 && firstBytes[2] === 0x67 && firstBytes[3] === 0x53) {
          mimeType = 'audio/ogg';
        }
        // Check for WebM (starts with 1A 45 DF A3)
        else if (firstBytes[0] === 0x1A && firstBytes[1] === 0x45 && firstBytes[2] === 0xDF && firstBytes[3] === 0xA3) {
          mimeType = 'audio/webm';
        }
        
        // Create blob with detected or default MIME type
        const typedBlob = new Blob([audioData], { type: mimeType });
        const typedUrl = URL.createObjectURL(typedBlob);
        audio.src = typedUrl;
        
        audio.onloadeddata = () => {
          console.log('Audio loaded successfully, format:', mimeType);
        };
        
        audio.oncanplay = () => {
          console.log('Audio can play');
        };
        
        audio.onerror = (err) => {
          console.error('Audio playback error:', err, audio.error);
          // Try WAV as fallback if current format failed
          if (mimeType !== 'audio/wav') {
            console.log('Trying WAV format as fallback...');
            const wavBlob = new Blob([audioData], { type: 'audio/wav' });
            const wavUrl = URL.createObjectURL(wavBlob);
            audio.src = wavUrl;
            audio.load();
          } else {
            URL.revokeObjectURL(typedUrl);
            isPlayingRef.current = false;
            reject(new Error('Failed to play audio: ' + (audio.error?.message || 'Unknown error')));
          }
        };
        
        audio.onended = () => {
          URL.revokeObjectURL(typedUrl);
          isPlayingRef.current = false;
          // Resume audio streaming when TTS finishes
          streamingPausedRef.current = false;
          console.log('🎤 Audio streaming resumed (TTS finished)');
          resolve();
        };
        
        audio.onplay = () => {
          isPlayingRef.current = true;
          // Pause audio streaming when TTS starts playing
          streamingPausedRef.current = true;
          console.log('🔇 Audio streaming paused (TTS playing)');
        };
        
        // Start playing
        audio.play().catch((playError) => {
          console.error('Error starting audio playback:', playError);
          URL.revokeObjectURL(typedUrl);
          isPlayingRef.current = false;
          streamingPausedRef.current = false;
          reject(playError);
        });
      } catch (err) {
        console.error('Error setting up audio playback:', err);
        isPlayingRef.current = false;
        reject(err);
      }
    });
  };

  const startCall = async () => {
    try {
      setError(null);
      
      // Get user media
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 16000,  // Match VAD sample rate
          channelCount: 1,    // Mono
          echoCancellation: true,
          noiseSuppression: true
        }
      });
      streamRef.current = stream;
      
      // Initialize WebSocket
      const wsUrl = apiBaseUrl.replace('http', 'ws') + `/ws/call/${sessionId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsCallActive(true);
        
        // Setup continuous audio streaming using ScriptProcessorNode
        // This captures PCM audio frames continuously
        // Note: ScriptProcessorNode is deprecated but still works and is simplest for this use case
        const audioContext = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: 16000  // Match VAD sample rate
        });
        audioContextRef.current = audioContext;
        
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        source.connect(analyser);
        analyserRef.current = analyser;
        
        // Create ScriptProcessorNode for continuous PCM capture
        // Buffer size: 512 samples = 32ms at 16kHz (matches VAD frame size)
        const bufferSize = 512;
        const scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);
        scriptProcessorRef.current = scriptProcessor;
        
        let frameCount = 0;
        scriptProcessor.onaudioprocess = (event) => {
          // Only stream if not paused (TTS not playing)
          if (!streamingPausedRef.current && isStreamingRef.current && ws.readyState === WebSocket.OPEN) {
            const inputData = event.inputBuffer.getChannelData(0);
            
            // Convert float32 to int16 PCM
            const pcm16 = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
              // Clamp and convert to int16
              const s = Math.max(-1, Math.min(1, inputData[i]));
              pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            
            // Send PCM frame to server
            frameCount++;
            if (frameCount % 50 === 0) {
              console.log(`📤 Sent frame ${frameCount} to server`);
            }
            ws.send(pcm16.buffer);
          }
        };
        
        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);
        
        // Start streaming after a short delay (wait for TTS to finish if playing)
        setTimeout(() => {
          isStreamingRef.current = true;
          streamingPausedRef.current = false;
          console.log('🎤 Continuous audio streaming started');
        }, 500);
      };

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob || event.data instanceof ArrayBuffer) {
          // Audio data - start playing it (don't wait, let it play in background)
          const audioData = event.data instanceof ArrayBuffer 
            ? event.data 
            : await event.data.arrayBuffer();
          // Chain the promise so we can wait for it later
          // Pass ArrayBuffer directly (decodeAudioData requires ArrayBuffer)
          currentAudioPromiseRef.current = currentAudioPromiseRef.current.then(() => 
            playAudio(audioData)
          );
        } else {
          // JSON data - wait for any pending audio to finish first
          try {
            const data = JSON.parse(event.data);
            await handleWebSocketMessage(data);
          } catch (err) {
            console.error('Error parsing JSON:', err);
          }
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setError('Connection error. Please try again.');
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
        setIsCallActive(false);
        isStreamingRef.current = false;
        streamingPausedRef.current = false;
        
        // Disconnect script processor
        const scriptProcessor = scriptProcessorRef.current;
        if (scriptProcessor) {
          scriptProcessor.disconnect();
          scriptProcessorRef.current = null;
        }
        
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
        analyserRef.current = null;
      };

    } catch (err) {
      console.error('Error starting call:', err);
      setError('Failed to start call. Please check microphone permissions.');
    }
  };

  const handleWebSocketMessage = async (data) => {
    switch (data.type) {
      case 'question':
        setCurrentQuestion({
          number: data.question_number,
          text: data.text
        });
        // Wait for any pending audio to finish, then resume streaming
        await currentAudioPromiseRef.current;
        // Small delay to ensure audio fully finished
        await new Promise(resolve => setTimeout(resolve, 300));
        setIsRecording(true);
        streamingPausedRef.current = false;
        isStreamingRef.current = true;
        console.log('🎤 Audio streaming resumed after question');
        break;
      
      case 'response':
        setTranscribedText(data.transcribed_text || '');
        setCurrentQuestion(prev => prev ? {
          ...prev,
          text: data.bot_text
        } : null);
        
        if (data.conversation_complete) {
          setIsRecording(false);
          isStreamingRef.current = false;
          streamingPausedRef.current = true;
          setConversationComplete(true);
        } else {
          // Wait for bot response audio to finish playing before resuming streaming
          await currentAudioPromiseRef.current;
          // Small delay to ensure audio fully finished
          await new Promise(resolve => setTimeout(resolve, 300));
          
          if (!conversationComplete) {
            setIsRecording(true);
            streamingPausedRef.current = false;
            isStreamingRef.current = true;
            console.log('🎤 Audio streaming resumed after response');
          }
        }
        break;
      
      case 'summary':
        setCallSummary(data.data);
        break;
      
      case 'error':
        setError(data.message);
        break;
      
      case 'vad_status':
        console.log('VAD Status:', data.message, 'Loaded:', data.vad_loaded);
        break;
      
      case 'vad_update':
        // Update speech detection status
        setSpeechDetected(data.is_speech || false);
        setSpeechProbability(data.probability || 0);
        break;
      
      default:
        // Unknown message type, log for debugging
        console.log('Unknown WebSocket message type:', data.type);
        break;
    }
  };

  // Note: startRecording and stopRecording are kept for compatibility
  // but are not actively used since we use continuous streaming via ScriptProcessorNode
  // eslint-disable-next-line no-unused-vars
  const startRecording = () => {
    // Continuous streaming is handled by ScriptProcessorNode
    isStreamingRef.current = true;
    streamingPausedRef.current = false;
  };

  // eslint-disable-next-line no-unused-vars
  const stopRecording = () => {
    // Pause streaming instead of stopping
    streamingPausedRef.current = true;
  };

  const endCall = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_call' }));
      wsRef.current.close();
    }
    // Disconnect script processor if it exists
    const scriptProcessor = scriptProcessorRef.current;
    if (scriptProcessor) {
      scriptProcessor.disconnect();
      scriptProcessorRef.current = null;
    }
    stopAudioPlayback();
    setIsCallActive(false);
    setIsRecording(false);
    onCallEnd();
  };

  return (
    <div className="call-interface">
      <div className="call-container">
        <div className="call-header">
          <h2>Call with {customer.customer_name}</h2>
          <div className="call-info">
            <p>Phone: {customer.contact_number}</p>
            <p>Agreement: {customer.agreement_no}</p>
          </div>
        </div>

        {error && (
          <div className="call-error">
            {error}
            <button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {!isCallActive ? (
          <div className="call-controls-start">
            <button onClick={startCall} className="start-call-button">
              Start Call
            </button>
          </div>
        ) : (
          <>
            <div className="call-status">
              <div className={`status-indicator ${isRecording ? 'recording' : 'listening'}`}>
                <span className="status-dot"></span>
                {isRecording ? 'Recording...' : conversationComplete ? 'Call Complete' : 'Listening...'}
              </div>
              
              {/* Speech Detection Status */}
              {isRecording && (
                <div className={`speech-detection ${speechDetected ? 'speech-detected' : 'no-speech'}`}>
                  <div className="speech-indicator">
                    <span className={`speech-dot ${speechDetected ? 'active' : ''}`}></span>
                    {speechDetected ? (
                      <span>🎤 Speech Detected ({Math.round(speechProbability * 100)}%)</span>
                    ) : (
                      <span>🔇 Listening... ({Math.round(speechProbability * 100)}%)</span>
                    )}
                  </div>
                </div>
              )}
              
              {/* Audio Visualizer/Equalizer */}
              {isRecording && (
                <div className="audio-visualizer">
                  <div className="visualizer-label">Audio Level</div>
                  <div className="equalizer-bars">
                    {audioBars.map((height, index) => (
                      <div
                        key={index}
                        className="equalizer-bar"
                        style={{
                          height: `${height}%`,
                          backgroundColor: speechDetected ? '#4caf50' : '#2196f3'
                        }}
                      />
                    ))}
                  </div>
                  <div className="audio-level">
                    Level: {Math.round(audioLevel)}%
                  </div>
                </div>
              )}
            </div>

            {currentQuestion && (
              <div className="question-display">
                <div className="question-number">
                  Question {currentQuestion.number} of 9
                </div>
                <div className="question-text">{currentQuestion.text}</div>
              </div>
            )}

            {transcribedText && (
              <div className="transcription">
                <strong>You said:</strong> {transcribedText}
              </div>
            )}

            {conversationComplete && (
              <div className="call-complete">
                <h3>Call Completed Successfully!</h3>
                {callSummary && (
                  <div className="summary">
                    <p><strong>Questions Answered:</strong> {callSummary.questions_answered} / {callSummary.total_questions}</p>
                    <p><strong>Status:</strong> {callSummary.status}</p>
                  </div>
                )}
              </div>
            )}

            <div className="call-controls">
              <button onClick={endCall} className="end-call-button">
                End Call
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default CallInterface;

