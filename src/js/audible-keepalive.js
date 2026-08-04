/* Audible-tab keepalive.
 *
 * Chromium exempts a tab that is playing audio from background timer
 * throttling and from tab discarding. This page captures audio but never
 * outputs any, so it is treated as an ordinary idle tab. Emitting a
 * far-below-audible tone flips the tab into the audible state and keeps the
 * timer fallback in render-driver.js running at full rate while hidden.
 *
 * Feedback guard: many of these setups capture a loopback or monitor device,
 * so anything this page outputs can be captured straight back into its own
 * analysis input. When the selected input looks like a loopback, the keepalive
 * stays silent and the AudioWorklet tick carries the load instead. An
 * unidentified input (empty label, which is what getUserMedia reports before
 * permission is granted) is treated the same way.
 *
 * The signal runs on its own AudioContext, never the analysis context, so it
 * can never reach visualizer.connectAudio or perturb the FFT presets read.
 */
(function (global) {
  'use strict';

  /* About -56 dBFS. Inaudible at any normal listening level, and far enough
   * above digital silence for Chromium's audibility detector to register it.
   * See docs/background-rendering.md for the calibration procedure before
   * changing this. */
  const KEEPALIVE_GAIN = 0.0015;

  /* Below the usable range of typical playback hardware, so even at an
   * unexpected gain the tone stays out of the way of the actual audio. */
  const KEEPALIVE_HZ = 20;

  const LOOPBACK_PATTERNS = [
    /voicemeeter/i,
    /vb-?audio/i,
    /vb-?cable/i,
    /cable\s*output/i,
    /stereo\s*mix/i,
    /monitor\s+of/i,
    /blackhole/i,
    /loopback/i,
    /soundflower/i,
    /what\s*u\s*hear/i,
  ];

  function isLoopbackLabel(label) {
    return LOOPBACK_PATTERNS.some(function (pattern) { return pattern.test(label); });
  }

  /** Return the reason this label must stay silent, or an empty string. */
  function suppressionReason(label) {
    const name = typeof label === 'string' ? label.trim() : '';
    if (!name) return 'suppressed: unidentified input, possible loopback';
    if (isLoopbackLabel(name)) return 'suppressed: loopback input';
    return '';
  }

  function createContext(state) {
    const Ctor = state.win.AudioContext || state.win.webkitAudioContext;
    if (typeof Ctor !== 'function') {
      state.reason = 'unavailable: no AudioContext';
      return null;
    }
    try {
      return new Ctor();
    } catch (error) {
      state.reason = 'unavailable: AudioContext creation failed';
      console.warn('Keepalive: could not create its audio context', error);
      return null;
    }
  }

  function buildGraph(state, context) {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = KEEPALIVE_HZ;
    gain.gain.value = KEEPALIVE_GAIN;
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    state.oscillator = oscillator;
    state.gain = gain;
  }

  function engage(state) {
    if (state.active) return;
    const context = state.context || createContext(state);
    if (!context) return;
    state.context = context;
    try {
      buildGraph(state, context);
    } catch (error) {
      state.reason = 'unavailable: audio graph failed';
      console.warn('Keepalive: could not build its audio graph', error);
      return;
    }
    if (context.state === 'suspended' && typeof context.resume === 'function') {
      context.resume().catch(function (error) {
        console.warn('Keepalive: could not resume its audio context', error);
      });
    }
    state.active = true;
    state.reason = '';
  }

  function disengage(state) {
    if (state.oscillator) {
      try {
        state.oscillator.stop();
        state.oscillator.disconnect();
      } catch (error) {
        console.warn('Keepalive: could not stop its oscillator', error);
      }
      state.oscillator = null;
    }
    if (state.gain) {
      state.gain.disconnect();
      state.gain = null;
    }
    state.active = false;
  }

  function evaluate(state) {
    if (!state.wanted) {
      disengage(state);
      return;
    }
    const reason = suppressionReason(state.label);
    state.suppressed = Boolean(reason);
    if (reason) {
      state.reason = reason;
      disengage(state);
      return;
    }
    engage(state);
  }

  function closeContext(state) {
    const context = state.context;
    state.context = null;
    if (!context || typeof context.close !== 'function') return;
    const closing = context.close();
    if (closing && typeof closing.catch === 'function') {
      closing.catch(function (error) {
        console.warn('Keepalive: could not close its audio context', error);
      });
    }
  }

  function create(options) {
    const opts = options || {};
    const state = {
      win: opts.window || global,
      label: '',
      wanted: false,
      active: false,
      suppressed: false,
      reason: '',
      context: null,
      oscillator: null,
      gain: null,
    };
    return {
      setInputLabel: function (label) {
        state.label = typeof label === 'string' ? label : '';
        evaluate(state);
      },
      start: function () {
        state.wanted = true;
        evaluate(state);
      },
      stop: function () {
        state.wanted = false;
        disengage(state);
        closeContext(state);
      },
      stats: function () {
        return {
          active: state.active,
          suppressed: state.suppressed,
          reason: state.reason,
          gain: state.active ? KEEPALIVE_GAIN : 0,
          label: state.label,
        };
      },
    };
  }

  global.BCKeepalive = { create: create };
}(window));
