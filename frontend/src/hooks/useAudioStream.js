import { useRef } from 'react';
import { SAMPLE_RATE, FRAME_SAMPLES } from '../utils/constants';
import { convertFloat32ToInt16 } from '../utils/audioProcessing';

export const useAudioStream = (wsRef) => {
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const sourceRef = useRef(null);
  const bufferRef = useRef([]);

  const startAudioStream = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: SAMPLE_RATE,
    });
    audioContextRef.current = audioContext;

    const source = audioContext.createMediaStreamSource(stream);
    sourceRef.current = source;

    const processor = audioContext.createScriptProcessor(1024, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      bufferRef.current.push(...input);

      while (bufferRef.current.length >= FRAME_SAMPLES) {
        const frame = bufferRef.current.slice(0, FRAME_SAMPLES);
        bufferRef.current = bufferRef.current.slice(FRAME_SAMPLES);

        const int16 = convertFloat32ToInt16(frame);

        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(int16.buffer);
        }
      }
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
  };

  const stopAudioStream = () => {
    if (processorRef.current) processorRef.current.disconnect();
    if (sourceRef.current) sourceRef.current.disconnect();
    if (audioContextRef.current) audioContextRef.current.close();
    bufferRef.current = [];
  };

  return { startAudioStream, stopAudioStream };
};

