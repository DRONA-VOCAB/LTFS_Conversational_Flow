import { useState, useRef } from "react";
import { playAudioFromBase64 } from "../utils/audioProcessing";

export const useAudioPlayer = () => {
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const currentAudioRef = useRef(null);

  const playAudio = (base64String) => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
    }

    currentAudioRef.current = playAudioFromBase64(base64String, {
      onPlay: () => setIsPlayingAudio(true),
      onEnd: () => {
        setIsPlayingAudio(false);
        currentAudioRef.current = null;
      },
      onError: (error) => {
        console.error("Audio error:", error);
        setIsPlayingAudio(false);
        currentAudioRef.current = null;
      },
    });
  };

  const stopAudio = () => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
      setIsPlayingAudio(false);
    }
  };

  return { isPlayingAudio, playAudio, stopAudio };
};

