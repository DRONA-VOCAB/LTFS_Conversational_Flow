#!/usr/bin/env python3
"""
Test script for filler lookup system
Tests similarity-based filler selection with various questions and transcripts
"""
import sys
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).resolve().parent.parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from utils.filler_manager import (
    get_filler,
    get_similarity_based_filler,
    find_matching_context,
    FILLER_LOOKUP_TABLE,
    HINDI_FILLERS
)

def print_separator():
    print("=" * 80)

def test_filler_selection(transcript: str, question: str = None, description: str = ""):
    """Test filler selection for a given transcript and question"""
    print_separator()
    print(f"Test: {description}")
    print(f"Transcript: '{transcript}'")
    print(f"Question: '{question}'" if question else "Question: None")
    
    # Find matching contexts
    contexts = find_matching_context(transcript, question)
    print(f"Matching Contexts: {contexts}")
    
    # Get similarity-based filler
    filler = get_similarity_based_filler(transcript, question)
    print(f"Selected Filler: '{filler}'")
    print()

def run_tests():
    """Run comprehensive tests"""
    print("=" * 80)
    print("FILLER LOOKUP SYSTEM TEST")
    print("=" * 80)
    print()
    
    # Test cases: (transcript, question, description)
    test_cases = [
        # Amount/Number related
        ("5000 रुपये", "कितने रुपये का भुगतान किया था?", "Amount - User mentions rupees"),
        ("दस हज़ार", "भुगतान की राशि क्या थी?", "Amount - User mentions amount"),
        ("पांच हज़ार रुपये", None, "Amount - User mentions amount without question"),
        
        # Date related
        ("15 दिसंबर", "किस तारीख को भुगतान किया था?", "Date - User mentions date"),
        ("पिछले महीने", "भुगतान कब किया था?", "Date - User mentions relative date"),
        ("20 तारीख को", None, "Date - User mentions date without question"),
        
        # Payment mode related
        ("ऑनलाइन", "भुगतान कैसे किया था?", "Payment Mode - User mentions online"),
        ("नकद", "भुगतान का माध्यम क्या था?", "Payment Mode - User mentions cash"),
        ("ब्रांच में", None, "Payment Mode - User mentions branch"),
        
        # Payee/Who paid related
        ("मैंने", "किसने भुगतान किया था?", "Payee - User says 'I paid'"),
        ("मेरे पिता ने", "कौन भुगतान किया था?", "Payee - User mentions relative"),
        ("खुद", None, "Payee - User says 'self'"),
        
        # Reason/Purpose related
        ("ईएमआई", "भुगतान का कारण क्या था?", "Reason - User mentions EMI"),
        ("सेटलमेंट", "किस वजह से भुगतान किया था?", "Reason - User mentions settlement"),
        ("फोरक्लोजर", None, "Reason - User mentions foreclosure"),
        
        # Confirmation/Verification
        ("हाँ सही है", "क्या यह जानकारी सही है?", "Confirmation - User confirms"),
        ("बिल्कुल सही", "यह जानकारी सही है?", "Confirmation - User confirms strongly"),
        
        # General/Transition
        ("ठीक है", "अगला सवाल है...", "General - User acknowledges"),
        ("हाँ", None, "General - Simple yes"),
        
        # Mixed context (should prioritize based on keywords)
        ("5000 रुपये 15 दिसंबर को", "कितने रुपये और कब?", "Mixed - Amount and Date"),
        ("ऑनलाइन ईएमआई", "कैसे और क्यों?", "Mixed - Mode and Reason"),
    ]
    
    print(f"Total Test Cases: {len(test_cases)}")
    print()
    
    # Run all test cases
    for transcript, question, description in test_cases:
        test_filler_selection(transcript, question, description)
    
    # Test with get_filler function (full flow)
    print_separator()
    print("TESTING FULL get_filler() FUNCTION")
    print_separator()
    
    test_cases_full = [
        ("5000 रुपये", "कितने रुपये का भुगतान किया था?", False, False),
        ("15 दिसंबर", "किस तारीख को भुगतान किया था?", False, False),
        ("ऑनलाइन", "भुगतान कैसे किया था?", False, False),
        ("हाँ", None, True, False),  # Opening - should skip
        ("ठीक है", None, False, True),  # Closing - should skip
    ]
    
    for transcript, question, skip_opening, skip_closing in test_cases_full:
        print(f"\nTranscript: '{transcript}'")
        print(f"Question: '{question}'")
        print(f"Skip Opening: {skip_opening}, Skip Closing: {skip_closing}")
        filler = get_filler(
            transcript=transcript,
            question=question,
            skip_for_opening=skip_opening,
            skip_for_closing=skip_closing,
            use_similarity=True
        )
        if filler:
            print(f"✅ Selected Filler: '{filler}'")
        else:
            print("❌ No filler selected (skipped)")
    
    # Show lookup table structure
    print_separator()
    print("LOOKUP TABLE STRUCTURE")
    print_separator()
    for context, fillers in FILLER_LOOKUP_TABLE.items():
        print(f"\n{context}:")
        for filler in fillers:
            print(f"  - {filler}")
    
    print_separator()
    print("TEST COMPLETE")
    print_separator()

if __name__ == "__main__":
    run_tests()

