/* AudioWorklet frame-tick source.
 *
 * Chromium stops delivering requestAnimationFrame entirely to a hidden
 * document, and window-occlusion tracking marks a fully covered or minimized
 * window hidden, not just a background tab. The audio thread keeps running
 * regardless, and a port message is delivered to the main thread as a task
 * rather than a timer, so it escapes hidden-page timer throttling. That makes
 * this processor a usable frame clock while the page is hidden.
 *
 * Loaded through AudioContext.audioWorklet.addModule, never as a <script> tag.
 */

const QUANTUM_FRAMES = 128;
const DEFAULT_TICK_HZ = 60;

class RenderTickProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    const requested = Number(opts.tickHz);
    const tickHz = requested > 0 ? requested : DEFAULT_TICK_HZ;
    this.framesPerTick = Math.max(QUANTUM_FRAMES, Math.round(sampleRate / tickHz));
    this.framesSinceTick = 0;
    this.ticks = 0;
  }

  /** Emit silence, and post a tick once a frame interval of audio has elapsed. */
  process(inputs, outputs) {
    const output = outputs[0];
    if (output) {
      for (let channel = 0; channel < output.length; channel += 1) {
        output[channel].fill(0);
      }
    }
    this.framesSinceTick += QUANTUM_FRAMES;
    if (this.framesSinceTick >= this.framesPerTick) {
      this.framesSinceTick = 0;
      this.ticks += 1;
      this.port.postMessage(this.ticks);
    }
    return true;
  }
}

registerProcessor('bc-render-tick', RenderTickProcessor);
