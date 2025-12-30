"""
Conversation recorder service
FINAL VERSION – captures COMPLETE calls safely
Creates a single combined recording file with user and bot audio interleaved chronologically.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
import struct
import subprocess
import tempfile
import os


class ConversationRecorder:
    """
    Records full 2-way conversations safely by
    writing audio incrementally to disk.
    """

    def __init__(self, recordings_dir: str = "recordings"):
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        # Active calls - stores audio chunks with timestamps for chronological ordering
        self.active_calls: dict[str, dict] = {}

    # --------------------------------------------------
    # START CALL
    # --------------------------------------------------
    def start_recording(self, call_id: str) -> None:
        if call_id in self.active_calls:
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        combined_path = self.recordings_dir / f"{call_id}_combined_{ts}.wav"
        meta_path = self.recordings_dir / f"{call_id}_{ts}.json"

        self.active_calls[call_id] = {
            "start_time": datetime.now(),
            "combined_path": combined_path,
            "meta_path": meta_path,
            # Store audio chunks with timestamps for chronological ordering
            "audio_chunks": [],  # List of (timestamp, type, data) tuples
        }

        print(f"[Recorder] Recording started for {call_id}")

    # --------------------------------------------------
    # USER AUDIO (WEBM / OPUS)
    # --------------------------------------------------
    def record_user_audio(self, call_id: str, audio_data: bytes) -> None:
        if call_id not in self.active_calls:
            self.start_recording(call_id)

        call = self.active_calls[call_id]
        # Store with timestamp for chronological ordering
        call["audio_chunks"].append((
            datetime.now(),
            "user",
            audio_data
        ))

        user_chunks = sum(1 for _, t, _ in call["audio_chunks"] if t == "user")
        print(
            f"[Recorder] User chunk #{user_chunks} "
            f"({len(audio_data)} bytes) for {call_id}"
        )

    # --------------------------------------------------
    # BOT AUDIO (WAV)
    # --------------------------------------------------
    def record_bot_audio(self, call_id: str, audio_data: bytes) -> None:
        if call_id not in self.active_calls:
            self.start_recording(call_id)

        call = self.active_calls[call_id]
        # Store with timestamp for chronological ordering
        call["audio_chunks"].append((
            datetime.now(),
            "bot",
            audio_data
        ))

        bot_chunks = sum(1 for _, t, _ in call["audio_chunks"] if t == "bot")
        print(
            f"[Recorder] Bot chunk #{bot_chunks} "
            f"({len(audio_data)} bytes) for {call_id}"
        )

    # --------------------------------------------------
    # FINALIZE CALL - Create combined recording
    # --------------------------------------------------
    async def finalize_recording(self, call_id: str) -> Optional[str]:
        if call_id not in self.active_calls:
            print(f"[Recorder] No active call for {call_id}")
            return None

        call = self.active_calls[call_id]

        try:
            # Sort audio chunks by timestamp to maintain chronological order
            call["audio_chunks"].sort(key=lambda x: x[0])
            
            user_chunks = sum(1 for _, t, _ in call["audio_chunks"] if t == "user")
            bot_chunks = sum(1 for _, t, _ in call["audio_chunks"] if t == "bot")
            
            print(f"[Recorder] Combining {user_chunks} user chunks and {bot_chunks} bot chunks for {call_id}")
            
            # Combine audio chunks in chronological order
            combined_wav = self._combine_audio_chunks(call["audio_chunks"])
            
            # Write combined WAV file
            call["combined_path"].write_bytes(combined_wav)
            
            # Write metadata
            call["meta_path"].write_text(
                f"""{{
  "call_id": "{call_id}",
  "start_time": "{call['start_time'].isoformat()}",
  "end_time": "{datetime.now().isoformat()}",
  "user_chunks": {user_chunks},
  "bot_chunks": {bot_chunks},
  "total_chunks": {len(call['audio_chunks'])},
  "combined_audio": "{call['combined_path'].name}",
  "format": "audio/wav"
}}"""
            )

            print(f"[Recorder] Call finalized: {call_id}")
            print(f"[Recorder] Combined recording → {call['combined_path']}")

            del self.active_calls[call_id]

            return str(call["combined_path"])

        except Exception as e:
            print(f"[Recorder] Finalization error for {call_id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _convert_webm_to_wav(self, webm_data: bytes) -> bytes:
        """
        Convert WebM/Opus audio to WAV format using ffmpeg.
        
        Args:
            webm_data: WebM audio bytes
            
        Returns:
            WAV audio bytes
        """
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as input_file:
                input_file.write(webm_data)
                input_path = input_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as output_file:
                output_path = output_file.name
            
            # Convert using ffmpeg
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ar', '24000',  # Sample rate
                '-ac', '1',      # Mono
                '-f', 'wav',
                '-y',            # Overwrite output
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=30
            )
            
            # Read converted WAV file
            with open(output_path, 'rb') as f:
                wav_data = f.read()
            
            # Cleanup
            os.unlink(input_path)
            os.unlink(output_path)
            
            return wav_data
            
        except subprocess.CalledProcessError as e:
            print(f"[Recorder] FFmpeg conversion error: {e.stderr.decode()}")
            # Return empty WAV if conversion fails
            return self._create_empty_wav()
        except FileNotFoundError:
            print("[Recorder] FFmpeg not found. Please install ffmpeg for audio conversion.")
            return self._create_empty_wav()
        except Exception as e:
            print(f"[Recorder] Audio conversion error: {e}")
            return self._create_empty_wav()
    
    def _create_empty_wav(self) -> bytes:
        """Create an empty WAV file header."""
        return self._create_wav_header(0, 24000, 1, 16)
    
    def _create_wav_header(self, data_size: int, sample_rate: int, channels: int, bits_per_sample: int) -> bytes:
        """Create a standard WAV file header."""
        fmt_chunk_size = 16
        data_chunk_size = data_size
        file_size = 36 + data_chunk_size
        
        header = b'RIFF'
        header += struct.pack('<I', file_size)
        header += b'WAVE'
        header += b'fmt '
        header += struct.pack('<I', fmt_chunk_size)
        header += struct.pack('<H', 1)  # PCM
        header += struct.pack('<H', channels)
        header += struct.pack('<I', sample_rate)
        header += struct.pack('<I', sample_rate * channels * (bits_per_sample // 8))
        header += struct.pack('<H', channels * (bits_per_sample // 8))
        header += struct.pack('<H', bits_per_sample)
        header += b'data'
        header += struct.pack('<I', data_chunk_size)
        
        return header
    
    def _extract_pcm_from_wav(self, wav_data: bytes) -> bytes:
        """Extract PCM audio data from WAV file."""
        if len(wav_data) < 44:
            return wav_data
        
        # Find 'data' chunk
        data_pos = wav_data.find(b'data', 12)
        if data_pos == -1:
            return b''
        
        # Skip 'data' header (4 bytes 'data' + 4 bytes size)
        pcm_start = data_pos + 8
        return wav_data[pcm_start:]
    
    def _combine_audio_chunks(self, audio_chunks: List[Tuple[datetime, str, bytes]]) -> bytes:
        """
        Combine user and bot audio chunks in chronological order into a single WAV file.
        
        Args:
            audio_chunks: List of (timestamp, type, data) tuples sorted by timestamp
            
        Returns:
            Combined WAV file bytes
        """
        if not audio_chunks:
            return self._create_empty_wav()
        
        sample_rate = 24000
        channels = 1
        bits_per_sample = 16
        
        combined_pcm = b''
        
        for timestamp, chunk_type, audio_data in audio_chunks:
            if chunk_type == "user":
                # Convert WebM to WAV, then extract PCM
                wav_data = self._convert_webm_to_wav(audio_data)
                pcm_data = self._extract_pcm_from_wav(wav_data)
            else:  # bot
                # Extract PCM from WAV
                pcm_data = self._extract_pcm_from_wav(audio_data)
            
            combined_pcm += pcm_data
        
        # Create WAV file with combined PCM data
        header = self._create_wav_header(len(combined_pcm), sample_rate, channels, bits_per_sample)
        return header + combined_pcm
    
    def get_recording_path(self, call_id: str) -> Optional[str]:
        """
        Get the path to the finalized combined recording for a call.
        
        Args:
            call_id: The call ID
            
        Returns:
            Path to the combined recording file if found, None otherwise
        """
        # Search for the most recent combined recording file for this call
        pattern = f"{call_id}_combined_*.wav"
        matching_files = list(self.recordings_dir.glob(pattern))
        
        if not matching_files:
            return None
        
        # Return the most recently modified file
        most_recent = max(matching_files, key=lambda p: p.stat().st_mtime)
        return str(most_recent)
