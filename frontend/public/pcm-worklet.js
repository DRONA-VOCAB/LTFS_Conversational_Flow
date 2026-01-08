// AudioWorklet processor for converting audio to PCM16
class PCMWorkletProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.frameSamples = options.processorOptions?.frameSamples || 320;
    this.buffer = [];
  }

  process(inputs, outputs) {
    const input = inputs[0];
    
    if (input.length > 0) {
      const inputChannel = input[0];
      
      // Add samples to buffer
      this.buffer.push(...inputChannel);
      
      // When we have enough samples for a frame, send it
      while (this.buffer.length >= this.frameSamples) {
        const frame = this.buffer.slice(0, this.frameSamples);
        this.buffer = this.buffer.slice(this.frameSamples);
        
        // Convert Float32 to Int16
        const int16Array = new Int16Array(this.frameSamples);
        for (let i = 0; i < this.frameSamples; i++) {
          const s = Math.max(-1, Math.min(1, frame[i]));
          int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // Send to main thread
        this.port.postMessage(int16Array.buffer);
      }
    }
    
    return true;
  }
}

registerProcessor('pcm-worklet', PCMWorkletProcessor);

