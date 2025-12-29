"""Conversation recorder service for recording 2-way conversations."""
import os
import struct
from typing import Optional, List
from datetime import datetime
from pathlib import Path
import asyncio


class ConversationRecorder:
    """Service for recording 2-way conversations (user + bot audio)."""
    
    def __init__(self, recordings_dir: str = "recordings"):
        """
        Initialize conversation recorder.
        
        Args:
            recordings_dir: Directory to store recordings
        """
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage for active conversations
        self.active_recordings: dict[str, dict] = {}
    
    def start_recording(self, call_id: str) -> None:
        """
        Start recording a new conversation.
        
        Args:
            call_id: Unique call identifier
        """
        self.active_recordings[call_id] = {
            "user_audio_chunks": [],
            "bot_audio_chunks": [],
            "start_time": datetime.now(),
            "user_chunk_count": 0,
            "bot_chunk_count": 0
        }
        print(f"[Recorder] Started recording for call: {call_id}")
    
    def record_user_audio(self, call_id: str, audio_data: bytes) -> None:
        """
        Record user audio chunk.
        
        Args:
            call_id: Call identifier
            audio_data: Audio bytes from user
        """
        if call_id not in self.active_recordings:
            self.start_recording(call_id)
        
        self.active_recordings[call_id]["user_audio_chunks"].append(audio_data)
        self.active_recordings[call_id]["user_chunk_count"] += 1
        print(f"[Recorder] Recorded user audio chunk {self.active_recordings[call_id]['user_chunk_count']} for call: {call_id} ({len(audio_data)} bytes)")
    
    def record_bot_audio(self, call_id: str, audio_data: bytes) -> None:
        """
        Record bot audio chunk.
        
        Args:
            call_id: Call identifier
            audio_data: Audio bytes from bot
        """
        if call_id not in self.active_recordings:
            self.start_recording(call_id)
        
        self.active_recordings[call_id]["bot_audio_chunks"].append(audio_data)
        self.active_recordings[call_id]["bot_chunk_count"] += 1
        print(f"[Recorder] Recorded bot audio chunk {self.active_recordings[call_id]['bot_chunk_count']} for call: {call_id} ({len(audio_data)} bytes)")
    
    def _extract_pcm_from_wav(self, wav_data: bytes) -> Optional[bytes]:
        """
        Extract PCM audio data from WAV file.
        
        Args:
            wav_data: WAV file bytes
            
        Returns:
            PCM audio data or None if invalid
        """
        if len(wav_data) < 44:  # WAV header is at least 44 bytes
            return None
        
        # Check if it's a WAV file
        if wav_data[:4] != b'RIFF' or wav_data[8:12] != b'WAVE':
            # Assume raw PCM
            return wav_data
        
        # Find 'data' chunk
        i = 12
        while i < len(wav_data) - 8:
            if wav_data[i:i+4] == b'data':
                data_size = struct.unpack('<I', wav_data[i+4:i+8])[0]
                data_start = i + 8
                pcm_data = wav_data[data_start:data_start + data_size]
                return pcm_data
            # Move to next chunk
            chunk_size = struct.unpack('<I', wav_data[i+4:i+8])[0]
            i += 8 + chunk_size
        
        return None
    
    def _create_wav_header(self, data_size: int, sample_rate: int = 24000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
        """Create a WAV file header."""
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
    
    def _combine_audio_chunks(self, chunks: List[bytes], sample_rate: int = 24000) -> bytes:
        """
        Combine multiple audio chunks into a single WAV file.
        
        Args:
            chunks: List of audio chunks (WAV format)
            sample_rate: Sample rate for output (default: 24000)
            
        Returns:
            Combined WAV file bytes
        """
        if not chunks:
            return b''
        
        combined_pcm = b''
        
        for chunk in chunks:
            pcm_data = self._extract_pcm_from_wav(chunk)
            if pcm_data:
                combined_pcm += pcm_data
            else:
                # If extraction failed, try to use chunk as-is (might be raw PCM)
                combined_pcm += chunk
        
        if not combined_pcm:
            return b''
        
        # Create WAV header and combine
        wav_header = self._create_wav_header(len(combined_pcm), sample_rate)
        return wav_header + combined_pcm
    
    async def finalize_recording(self, call_id: str) -> Optional[str]:
        """
        Finalize recording and save to disk.
        
        Args:
            call_id: Call identifier
            
        Returns:
            Path to saved recording file or None if failed
        """
        if call_id not in self.active_recordings:
            print(f"[Recorder] No active recording found for call: {call_id}")
            return None
        
        recording_data = self.active_recordings[call_id]
        
        try:
            # Combine user and bot audio chunks
            user_audio = self._combine_audio_chunks(recording_data["user_audio_chunks"])
            bot_audio = self._combine_audio_chunks(recording_data["bot_audio_chunks"])
            
            # Create interleaved conversation (user -> bot -> user -> bot...)
            # For simplicity, we'll create separate files for user and bot,
            # and a combined file
            timestamp = recording_data["start_time"].strftime("%Y%m%d_%H%M%S")
            
            # Save user audio
            user_file = self.recordings_dir / f"{call_id}_user_{timestamp}.wav"
            if user_audio:
                with open(user_file, 'wb') as f:
                    f.write(user_audio)
                print(f"[Recorder] Saved user audio: {user_file}")
            
            # Save bot audio
            bot_file = self.recordings_dir / f"{call_id}_bot_{timestamp}.wav"
            if bot_audio:
                with open(bot_file, 'wb') as f:
                    f.write(bot_audio)
                print(f"[Recorder] Saved bot audio: {bot_file}")
            
            # Create combined recording (user + bot interleaved)
            combined_pcm = b''
            user_chunks = recording_data["user_audio_chunks"]
            bot_chunks = recording_data["bot_audio_chunks"]
            
            # Interleave: user chunk 1, bot chunk 1, user chunk 2, bot chunk 2, etc.
            max_chunks = max(len(user_chunks), len(bot_chunks))
            for i in range(max_chunks):
                if i < len(user_chunks):
                    user_pcm = self._extract_pcm_from_wav(user_chunks[i])
                    if user_pcm:
                        combined_pcm += user_pcm
                if i < len(bot_chunks):
                    bot_pcm = self._extract_pcm_from_wav(bot_chunks[i])
                    if bot_pcm:
                        combined_pcm += bot_pcm
            
            # Save combined recording
            combined_file = self.recordings_dir / f"{call_id}_combined_{timestamp}.wav"
            if combined_pcm:
                wav_header = self._create_wav_header(len(combined_pcm))
                with open(combined_file, 'wb') as f:
                    f.write(wav_header + combined_pcm)
                print(f"[Recorder] Saved combined recording: {combined_file}")
            
            # Clean up from memory
            del self.active_recordings[call_id]
            
            return str(combined_file)
            
        except Exception as e:
            print(f"[Recorder] Error finalizing recording for {call_id}: {str(e)}")
            import traceback
            print(f"[Recorder] Traceback: {traceback.format_exc()}")
            return None
    
    def get_recording_path(self, call_id: str) -> Optional[str]:
        """
        Get the path to a recording file for a call.
        
        Args:
            call_id: Call identifier
            
        Returns:
            Path to recording file or None if not found
        """
        # Search for combined recording file
        pattern = f"{call_id}_combined_*.wav"
        matching_files = list(self.recordings_dir.glob(pattern))
        
        if matching_files:
            # Return the most recent one
            return str(max(matching_files, key=lambda p: p.stat().st_mtime))
        
        return None
    
    def cleanup_old_recordings(self, days: int = 30) -> int:
        """
        Clean up recordings older than specified days.
        
        Args:
            days: Number of days to keep recordings
            
        Returns:
            Number of files deleted
        """
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for file_path in self.recordings_dir.glob("*.wav"):
            try:
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"[Recorder] Error deleting {file_path}: {str(e)}")
        
        print(f"[Recorder] Cleaned up {deleted_count} old recordings")
        return deleted_count

