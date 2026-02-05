# Hindi Filler Implementation

## Overview
Added Hindi filler words/phrases to reduce perceived latency during LLM processing. Fillers play immediately after ASR completes while LLM processes in parallel.

## Implementation Details

### Files Modified/Created

1. **`backend/app/utils/filler_manager.py`** (NEW)
   - Manages Hindi filler words/phrases
   - 85% probability of using fillers (approximately 2 out of 3 times)
   - Random selection from 14 filler phrases

2. **`backend/app/core/websocket_handler.py`** (MODIFIED)
   - Added `send_tts_and_wait()` function to wait for TTS completion
   - Added `process_with_filler()` function to handle filler + LLM parallel processing
   - Modified `process_asr_queue()` to use new filler-enabled processing
   - Added TTS finished callback mechanism

### How It Works

1. **After ASR completes:**
   - System checks if filler should be used (85% probability)
   - If yes, selects a random filler from the list

2. **Parallel Processing:**
   - LLM processing starts in parallel (via executor)
   - Filler TTS starts playing immediately (if selected)

3. **Sequencing:**
   - System waits for LLM to complete
   - System waits for filler to finish playing (if it's still playing)
   - LLM response plays AFTER filler completes

4. **Edge Cases:**
   - If LLM finishes before filler: waits for filler to finish, then plays response
   - If filler finishes before LLM: waits for LLM, then plays response immediately
   - If no filler selected: normal flow (LLM processes, then response plays)

### Filler Phrases

The following 14 Hindi filler phrases are used (random selection):

1. हम्म... (Hmm...)
2. अच्छा... (Accha...)
3. एक सेकंड... (Ek second...)
4. समझ गया। (Samajh gaya.)
5. नोट कर लिया (Note kar liya)
6. शुक्रिया (Shukriya)
7. आगे बढ़ते हैं... (Aage badhte hain...)
8. वैसे ही... (Waise hi...)
9. बढ़िया। (Badiya.)
10. धन्यवाद। (Dhanyawaad.)
11. बस कुछ ही सवाल और... (Bas kuch hi sawaal aur...)
12. एक पल इंतज़ार करें... (Wait for a moment...)
13. अगला विषय है... (The next topic is...)
14. जानकारी के लिए शुक्रिया। (Thanks for the information.)

### Usage Probability

- **85% chance** (approximately 2 out of 3 times) a filler will be used
- **15% chance** no filler will be used (normal flow)

### When Fillers Are Used

- ✅ **Used for:** User responses after ASR transcription
- ❌ **NOT used for:** 
  - Initial greetings/questions
  - System-generated messages
  - Error messages

### Technical Flow

```
User speaks → ASR completes → Check filler (85% chance)
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
            Play filler TTS              Start LLM processing
                    ↓                               ↓
                    └───────────────┬───────────────┘
                                    ↓
                            Wait for both to complete
                                    ↓
                            Play LLM response (after filler)
```

### Code Changes Summary

1. **Filler Manager (`filler_manager.py`):**
   - `get_filler()`: Returns filler text or None (85% probability)
   - `should_use_filler()`: Probability check
   - `get_random_filler()`: Random selection

2. **WebSocket Handler (`websocket_handler.py`):**
   - `send_tts_and_wait()`: Sends TTS and waits for completion using callback
   - `process_with_filler()`: Main function handling filler + LLM parallel processing
   - Modified `process_asr_queue()`: Uses `process_with_filler()` instead of direct processing
   - Added callback mechanism in `process_tts_queue()`: Triggers callback when TTS finishes

### Testing

To test the implementation:

1. Start a conversation
2. Speak a response
3. Observe:
   - Filler should play immediately after your speech is transcribed (85% chance)
   - LLM response should play after filler completes
   - If no filler, normal flow continues

### Configuration

To adjust filler probability, modify `FILLER_PROBABILITY` in `backend/app/utils/filler_manager.py`:

```python
FILLER_PROBABILITY = 0.85  # Change to 0.0-1.0 (0.85 = 85%)
```

To add/remove filler phrases, modify `HINDI_FILLERS` list in the same file.

### Notes

- Fillers are generated on-demand via TTS API (not pre-generated)
- Fillers use the same TTS service as regular responses
- Fillers are logged in the same way as regular TTS audio
- The implementation maintains backward compatibility - if fillers fail, normal flow continues


