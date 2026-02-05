"""
Filler Manager - Manages Hindi filler words for reducing perceived latency
Uses similarity search to select appropriate fillers based on transcript and question context
"""
import random
import logging
from typing import Optional, Dict, List
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Hindi filler words/phrases (neutral, 2-3 words and 3+ words)
HINDI_FILLERS = [
    # 2-3 word fillers
    "नोट कर लिया...",
    "आगे बढ़ते हैं...",
    "एक सेकंड...",
    "एक मिनट...",
    "आगे बताइए...",
    "हाँ, नोट कर लिया...",
    "समझ रहा है...",
    "सुन रहा है...",
    "ध्यान दे रहा है...",
    "जारी रखें...",
    "ठीक है...",
    "समझ गया...",
    "जी हाँ...",
    "बिल्कुल सही...",
    # 3+ word fillers
    "एक पल इंतज़ार करें...",
    "नोट कर लिया है...",
    "बस कुछ ही सवाल और...",
    "अगला विषय है...",
    "जानकारी के लिए शुक्रिया।",
    "जी, ध्यान से सुन रहा है...",
    "बिल्कुल, समझ रहा है...",
    "ठीक है, आगे बढ़ते हैं...",
    "समझ गया, जारी रखें...",
    "जी हाँ, समझ रहा है...",
    "बिल्कुल सही, नोट कर लिया...",
    "एक सेकंड, समझ रहा है...",
    "ठीक है, ध्यान से सुन रहा है...",
    "हाँ, जानकारी मिल गई...",
    "समझ गया, आगे बताइए...",
    "जी, सब कुछ समझ रहा है...",
    "ठीक है, अगला सवाल है...",
    "हाँ, यह जानकारी मिल गई...",
    "समझ रहा है, जारी रखें...",
    "बिल्कुल, नोट कर लिया है...",
    "ठीक है, आप बताते रहिए...",
    "हाँ, यह सही जानकारी है...",
    "एक मिनट, समझ रहा है...",
    "ठीक है, नोट कर लिया...",
    "समझ रहा है, आगे बताइए...",
    "जी, जानकारी मिल गई...",
    "बिल्कुल, ध्यान से सुन रहा है...",
    "हाँ, समझ रहा है...",
    "ठीक है, जारी रखें...",
    "समझ गया, नोट कर लिया...",
    "जी हाँ, नोट कर लिया...",
    "बिल्कुल, जानकारी मिल गई...",
    "हाँ, ध्यान से सुन रहा है...",
    "ठीक है, समझ रहा है...",
    "समझ रहा है, नोट कर लिया...",
    "जी, आगे बताइए...",
    "बिल्कुल, जारी रखें...",
    "हाँ, आगे बढ़ते हैं...",
    "ठीक है, जानकारी मिल गई...",
]

# Lookup table: Maps question types/contexts to appropriate fillers
# Key: keywords or question patterns, Value: list of preferred fillers
FILLER_LOOKUP_TABLE: Dict[str, List[str]] = {
    # Amount/Number related
    "amount": ["नोट कर लिया...", "हाँ, नोट कर लिया...", "बिल्कुल सही, नोट कर लिया...", "हाँ, यह जानकारी मिल गई..."],
    "राशि": ["नोट कर लिया...", "हाँ, नोट कर लिया...", "बिल्कुल सही, नोट कर लिया..."],
    "रुपये": ["नोट कर लिया...", "हाँ, नोट कर लिया...", "बिल्कुल सही, नोट कर लिया..."],
    
    # Date related
    "date": ["समझ गया...", "हाँ, जानकारी मिल गई...", "ठीक है, समझ गया...", "समझ गया, जारी रखें..."],
    "तारीख": ["समझ गया...", "हाँ, जानकारी मिल गई...", "ठीक है, समझ गया..."],
    "दिनांक": ["समझ गया...", "हाँ, जानकारी मिल गई..."],
    "कब": ["समझ गया...", "हाँ, जानकारी मिल गई...", "ठीक है, समझ गया..."],
    "दिसंबर": ["समझ गया...", "हाँ, जानकारी मिल गई...", "ठीक है, समझ गया..."],
    "महीने": ["समझ गया...", "हाँ, जानकारी मिल गई...", "ठीक है, समझ गया..."],
    
    # Payment mode related
    "mode": ["समझ रहा है...", "जी, ध्यान से सुन रहा है...", "बिल्कुल, समझ रहा है...", "समझ रहा है, जारी रखें..."],
    "माध्यम": ["समझ रहा है...", "जी, ध्यान से सुन रहा है...", "बिल्कुल, समझ रहा है..."],
    "ऑनलाइन": ["समझ रहा है...", "जी, ध्यान से सुन रहा है...", "बिल्कुल, समझ रहा है..."],
    "नकद": ["समझ रहा है...", "जी, ध्यान से सुन रहा है...", "बिल्कुल, समझ रहा है..."],
    "ब्रांच": ["समझ रहा है...", "जी, ध्यान से सुन रहा है...", "बिल्कुल, समझ रहा है..."],
    "कैसे": ["समझ रहा है...", "जी, ध्यान से सुन रहा है...", "बिल्कुल, समझ रहा है..."],
    # Note: "भुगतान" removed as it's too generic and appears in many contexts
    
    # Payee/Who paid related
    "payee": ["समझ गया...", "हाँ, समझ गया...", "ठीक है, समझ गया...", "समझ गया, आगे बताइए..."],
    "किसने": ["समझ गया...", "हाँ, समझ गया...", "ठीक है, समझ गया..."],
    "कौन": ["समझ गया...", "हाँ, समझ गया...", "ठीक है, समझ गया..."],
    
    # Reason/Purpose related
    "reason": ["समझ रहा है...", "जी हाँ, समझ रहा है...", "बिल्कुल, समझ रहा है...", "समझ रहा है, जारी रखें..."],
    "कारण": ["समझ रहा है...", "जी हाँ, समझ रहा है...", "बिल्कुल, समझ रहा है..."],
    "ईएमआई": ["समझ रहा है...", "जी हाँ, समझ रहा है...", "बिल्कुल, समझ रहा है..."],
    
    # General acknowledgment
    "general": ["एक सेकंड...", "एक मिनट...", "एक पल इंतज़ार करें...", "आगे बताइए...", "आगे बढ़ते हैं..."],
    "acknowledgment": ["समझ रहा है...", "जी, ध्यान से सुन रहा है...", "बिल्कुल, समझ रहा है..."],
    
    # Confirmation/Verification
    "confirmation": ["बिल्कुल सही...", "हाँ, यह सही जानकारी है...", "बिल्कुल, नोट कर लिया है...", "हाँ, यह जानकारी मिल गई..."],
    "सही": ["बिल्कुल सही...", "हाँ, यह सही जानकारी है...", "बिल्कुल, नोट कर लिया है..."],
    
    # Transition/Next question
    "transition": ["आगे बढ़ते हैं...", "ठीक है, आगे बढ़ते हैं...", "अगला विषय है...", "ठीक है, अगला सवाल है...", "बस कुछ ही सवाल और..."],
    "next": ["आगे बढ़ते हैं...", "ठीक है, आगे बढ़ते हैं...", "अगला विषय है...", "ठीक है, अगला सवाल है..."],
}

# Probability of using filler (85% = 0.85)
FILLER_PROBABILITY = 0.85


def similarity_score(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two texts using SequenceMatcher
    Returns a value between 0.0 and 1.0
    """
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def find_matching_context(transcript: str, question: Optional[str] = None) -> List[str]:
    """
    Find matching context keywords from transcript and question
    Returns list of matching context keys, prioritized by specificity
    """
    combined_text = (transcript + " " + (question or "")).lower()
    matching_contexts = []
    
    # Priority order: more specific keywords first
    # This ensures specific matches take precedence over generic ones
    priority_keywords = [
        # Most specific - Amount/Number
        "रुपये", "राशि", "amount",
        # Date specific
        "तारीख", "दिनांक", "date", "कब", "दिसंबर", "महीने",
        # Payee specific
        "किसने", "कौन", "payee",
        # Reason specific
        "कारण", "ईएमआई", "reason",
        # Mode specific
        "माध्यम", "mode", "ऑनलाइन", "नकद", "ब्रांच", "कैसे",
        # Confirmation specific
        "सही", "confirmation",
        # Transition specific
        "transition", "next",
        # General (lowest priority)
        "भुगतान", "general", "acknowledgment"
    ]
    
    # Check in priority order
    for keyword in priority_keywords:
        if keyword in combined_text and keyword in FILLER_LOOKUP_TABLE:
            matching_contexts.append(keyword)
    
    return matching_contexts


def get_similarity_based_filler(transcript: str, question: Optional[str] = None) -> str:
    """
    Get filler based on similarity search with transcript and question
    
    Args:
        transcript: User's transcript from ASR
        question: Current question being asked (optional)
    
    Returns:
        Selected filler phrase
    """
    # Find matching contexts
    matching_contexts = find_matching_context(transcript, question)
    
    # If we have matching contexts, use fillers from those contexts
    candidate_fillers = []
    if matching_contexts:
        for context in matching_contexts:
            candidate_fillers.extend(FILLER_LOOKUP_TABLE[context])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for filler in candidate_fillers:
            if filler not in seen:
                seen.add(filler)
                unique_candidates.append(filler)
        
        if unique_candidates:
            # Calculate similarity scores for each candidate
            combined_text = (transcript + " " + (question or "")).lower()
            filler_scores = [
                (filler, similarity_score(combined_text, filler))
                for filler in unique_candidates
            ]
            
            # Sort by similarity score (descending)
            filler_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Return top 3 candidates and randomly select from them for variety
            top_candidates = [filler for filler, score in filler_scores[:3]]
            selected = random.choice(top_candidates)
            logger.info(f"🎭 Similarity-based filler selected: '{selected}' (contexts: {matching_contexts})")
            return selected
    
    # Fallback: Use general fillers or random selection
    general_fillers = FILLER_LOOKUP_TABLE.get("general", HINDI_FILLERS)
    selected = random.choice(general_fillers)
    logger.info(f"🎭 Fallback filler selected: '{selected}' (no matching context)")
    return selected


def should_use_filler() -> bool:
    """
    Determine if filler should be used based on probability (85% chance)
    Returns True 85% of the time
    """
    return random.random() < FILLER_PROBABILITY


def get_random_filler() -> str:
    """
    Get a random filler word/phrase from the list
    """
    return random.choice(HINDI_FILLERS)


def get_filler(
    transcript: Optional[str] = None,
    question: Optional[str] = None,
    skip_for_opening: bool = False,
    skip_for_closing: bool = False,
    use_similarity: bool = True,
) -> Optional[str]:
    """
    Get a filler word if it should be used (85% probability)
    Uses similarity search if transcript is provided, otherwise uses random selection
    
    Args:
        transcript: User's transcript from ASR (for similarity search)
        question: Current question being asked (for similarity search)
        skip_for_opening: Skip filler if this is an opening/greeting
        skip_for_closing: Skip filler if this is a closing statement
        use_similarity: Whether to use similarity-based selection (default: True)
    
    Returns filler text or None
    """
    # Skip fillers for opening and closing
    if skip_for_opening or skip_for_closing:
        logger.info(f"🎭 Skipping filler (opening={skip_for_opening}, closing={skip_for_closing})")
        return None
    
    if should_use_filler():
        # Use similarity-based selection if transcript is provided and enabled
        if use_similarity and transcript:
            filler = get_similarity_based_filler(transcript, question)
        else:
            filler = get_random_filler()
        
        logger.info(f"🎭 Selected filler: '{filler}'")
        return filler
    
    return None
