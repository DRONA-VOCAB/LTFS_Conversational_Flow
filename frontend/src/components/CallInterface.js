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

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const isPlayingRef = useRef(false);
  const currentAudioPromiseRef = useRef(Promise.resolve());

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
      stopAudioPlayback();
    };
  }, []);

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
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      try {
        if (!audioContextRef.current) {
          audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }

        // decodeAudioData requires ArrayBuffer - audioData should already be ArrayBuffer
        const audioBufferPromise = audioContextRef.current.decodeAudioData(audioData);
        
        audioBufferPromise.then((audioBuffer) => {
          const source = audioContextRef.current.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(audioContextRef.current.destination);
          
          source.onended = () => {
            isPlayingRef.current = false;
            resolve();
          };
          
          isPlayingRef.current = true;
          source.start(0);
        }).catch(reject);
      } catch (err) {
        console.error('Error playing audio:', err);
        isPlayingRef.current = false;
        reject(err);
      }
    });
  };

  const startCall = async () => {
    try {
      setError(null);
      
      // Get user media
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Initialize WebSocket
      const wsUrl = apiBaseUrl.replace('http', 'ws') + `/ws/call/${sessionId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsCallActive(true);
        
        // Setup MediaRecorder
        const options = { mimeType: 'audio/webm' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          options.mimeType = 'audio/webm;codecs=opus';
          if (!MediaRecorder.isTypeSupported(options.mimeType)) {
            options.mimeType = '';
          }
        }

        const mediaRecorder = new MediaRecorder(stream, options);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          const arrayBuffer = await audioBlob.arrayBuffer();
          
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(arrayBuffer);
          }
          
          audioChunksRef.current = [];
        };
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
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
          mediaRecorderRef.current.stop();
        }
        stream.getTracks().forEach(track => track.stop());
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
        // Wait for any pending audio to finish, then start recording
        await currentAudioPromiseRef.current;
        // Small delay to ensure audio fully finished
        await new Promise(resolve => setTimeout(resolve, 300));
        setIsRecording(true);
        startRecording();
        break;
      
      case 'response':
        setTranscribedText(data.transcribed_text || '');
        setCurrentQuestion(prev => prev ? {
          ...prev,
          text: data.bot_text
        } : null);
        
        if (data.conversation_complete) {
          setIsRecording(false);
          stopRecording();
          setConversationComplete(true);
        } else {
          // Stop recording (we already sent the audio)
          setIsRecording(false);
          stopRecording();
          
          // Wait for bot response audio to finish playing before starting recording again
          await currentAudioPromiseRef.current;
          // Small delay to ensure audio fully finished
          await new Promise(resolve => setTimeout(resolve, 300));
          
          if (!conversationComplete) {
            setIsRecording(true);
            startRecording();
          }
        }
        break;
      
      case 'summary':
        setCallSummary(data.data);
        break;
      
      case 'error':
        setError(data.message);
        break;
      
      default:
        // Unknown message type, log for debugging
        console.log('Unknown WebSocket message type:', data.type);
        break;
    }
  };

  const startRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'inactive') {
      audioChunksRef.current = [];
      mediaRecorderRef.current.start(1000); // Collect data every second
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const endCall = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'end_call' }));
      wsRef.current.close();
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
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

