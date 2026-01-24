# Context Window Recommendations for GPT-OSS-20B

## Current Prompt Analysis

- **Base prompt**: 2,508 tokens
- **Full prompt per turn**: ~3,063 tokens (includes context, instructions)
- **Context usage per turn**: ~74.8% of 4K window

## Recommendation: Use 8K Context Window

### Why 8K instead of 4K?

1. **Safety Margin**: With 4K, you only have ~1,033 tokens remaining per turn. This is tight and could cause issues if:
   - Customer gives long responses
   - Session data grows (multiple retries, corrections)
   - Model needs extra tokens for reasoning

2. **Better Performance**: More context allows the model to:
   - Better understand conversation flow
   - Handle complex multi-part responses
   - Maintain context across longer conversations

3. **Future-Proofing**: If you add features like conversation history or more context, 8K gives you room to grow.

## vLLM Command Recommendation

```bash
# RECOMMENDED: Use 8K context window
vllm serve openai/gpt-oss-20b \
  --max-model-len 8192

# OR if you must use 4K (not recommended):
vllm serve openai/gpt-oss-20b \
  --max-model-len 4096
```

## Testing Your Current Setup

To check if you're hitting context limits, monitor for:
- Context overflow errors in logs
- Truncated or incomplete responses
- Model returning errors about context length

## Memory Considerations

- **4K context**: Lower memory usage, faster inference
- **8K context**: Higher memory usage (~2x), but still manageable for 20B model

If memory is a constraint, 4K will work but monitor closely. If you have sufficient GPU memory, 8K is strongly recommended.

## Summary

✅ **Recommended**: `--max-model-len 8192` (8K)
⚠️ **Minimum**: `--max-model-len 4096` (4K) - use only if memory constrained
