#!/usr/bin/env python3
"""
Calculate token count and context length for the prompt in prompt.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.config.prompt import PROMPT

def count_tokens_tiktoken(text: str) -> int:
    """Count tokens using tiktoken (OpenAI's tokenizer)"""
    try:
        import tiktoken
        # Use cl100k_base encoding (used by GPT-3.5, GPT-4, and GPT-OSS models)
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        return len(tokens)
    except ImportError:
        return None

def estimate_tokens_rough(text: str) -> int:
    """Rough estimation: ~4 characters per token for English, but Hindi/Devanagari may differ"""
    # For mixed Hindi/English, a rough estimate is 3-4 chars per token
    # We'll use 3.5 as a middle ground
    return int(len(text) / 3.5)

def count_characters(text: str) -> dict:
    """Count various character metrics"""
    return {
        "total_chars": len(text),
        "total_chars_no_spaces": len(text.replace(" ", "")),
        "total_chars_no_newlines": len(text.replace("\n", "")),
        "lines": text.count("\n") + 1,
        "words": len(text.split()),
    }

def main():
    print("=" * 70)
    print("PROMPT TOKEN & CONTEXT LENGTH ANALYSIS")
    print("=" * 70)
    print()
    
    # Character analysis
    char_stats = count_characters(PROMPT)
    print("CHARACTER STATISTICS:")
    print(f"  Total characters: {char_stats['total_chars']:,}")
    print(f"  Characters (no spaces): {char_stats['total_chars_no_spaces']:,}")
    print(f"  Characters (no newlines): {char_stats['total_chars_no_newlines']:,}")
    print(f"  Lines: {char_stats['lines']}")
    print(f"  Words: {char_stats['words']:,}")
    print()
    
    # Token counting
    print("TOKEN COUNT:")
    token_count = count_tokens_tiktoken(PROMPT)
    
    if token_count is not None:
        print(f"  Exact token count (tiktoken cl100k_base): {token_count:,} tokens")
    else:
        print("  tiktoken not available - installing...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "tiktoken", "-q"])
            token_count = count_tokens_tiktoken(PROMPT)
            if token_count is not None:
                print(f"  Exact token count (tiktoken cl100k_base): {token_count:,} tokens")
            else:
                raise Exception("Failed to count tokens")
        except Exception as e:
            print(f"  Could not install/use tiktoken: {e}")
            estimated = estimate_tokens_rough(PROMPT)
            print(f"  Estimated token count (rough): ~{estimated:,} tokens")
            print("  Note: This is a rough estimate. Install tiktoken for accurate count.")
            token_count = estimated
    
    print()
    
    # Context length analysis
    print("CONTEXT LENGTH ANALYSIS:")
    print(f"  Prompt tokens: {token_count:,}")
    
    # Common model context windows
    context_windows = {
        "GPT-3.5-turbo": 16385,
        "GPT-4": 8192,
        "GPT-4-turbo": 128000,
        "GPT-4o": 128000,
        "GPT-OSS-20B (typical)": 4096,  # Many 20B models have 4K context
        "GPT-OSS-20B (extended)": 8192,  # Some have 8K
    }
    
    print()
    print("  Remaining context for conversation (typical model windows):")
    for model, window in context_windows.items():
        remaining = window - token_count
        percentage_used = (token_count / window) * 100
        status = "✓ OK" if remaining > 0 else "✗ EXCEEDED"
        print(f"    {model:25s} {window:6,} tokens → {remaining:6,} remaining ({percentage_used:5.1f}% used) {status}")
    
    print()
    print("=" * 70)
    print("RECOMMENDATIONS:")
    if token_count > 4000:
        print("  ⚠️  WARNING: Prompt is very large (>4000 tokens)")
        print("     Consider optimizing or splitting the prompt if using models with")
        print("     limited context windows (e.g., 4K or 8K models)")
    elif token_count > 2000:
        print("  ⚠️  CAUTION: Prompt is moderately large (>2000 tokens)")
        print("     Monitor context usage during conversations")
    else:
        print("  ✓ Prompt size is reasonable for most models")
    print("=" * 70)

if __name__ == "__main__":
    main()
