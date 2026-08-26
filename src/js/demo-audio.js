/* Synthetic demo track.
 *
 * The visualizer normally reads an audio input device, which means a visitor
 * sees nothing until they have granted microphone permission and, to visualize
 * music rather than room noise, routed system audio through a virtual cable.
 * Demo mode removes that entirely: this module generates a track inside the
 * page and hands it to the same butterchurn analyzer a capture stream would
 * feed, so the presets react with no permissions and no devices.
 *
 * It is silent. The master bus reaches the destination only through a gain of
 * exactly 0, which is bit-exact digital silence: inaudible, invisible to a
 * loopback capture, and not enough to mark the tab audible. That tap exists
 * because butterchurn's analyser chain never connects to the destination
 * itself, so the synthetic sources would otherwise sit on a subgraph that only
 * runs by virtue of an engine's automatic-pull behavior for an
 * output-unconnected AnalyserNode. The tap costs one node and removes the
 * dependency on that.
 *
 * Three tempos, three genres. Each is a different pattern rather than the same
 * loop played faster, because the point is to show the presets reacting to
 * recognizably different music.
 */
(function (global) {
  'use strict';

  const DEMO_LABEL = 'Synthetic demo track';

  const SECONDS_PER_MINUTE = 60;
  const STEPS_PER_BEAT = 4;
  const STEPS_PER_BAR = 16;

  const MIN_BPM = 60;
  const MAX_BPM = 200;
  const MIN_INTENSITY = 0.1;
  const MAX_INTENSITY = 1;
  const DEFAULT_INTENSITY = 0.6;

  /* Two seconds of lookahead against a 25 ms pump. A hidden tab throttles
   * timers to roughly 1 Hz, which is still well inside the horizon, so the
   * queue does not run dry while backgrounded. */
  const SCHEDULE_AHEAD_SEC = 2;
  const SCHEDULE_INTERVAL_MS = 25;
  const MAX_STEPS_PER_PUMP = 64;
  /* Past this much lag the missed steps are dropped rather than played late,
   * so returning from a long stall cannot stack a burst of notes at once. */
  const RESYNC_LAG_SEC = 4;
  const STEP_LEAD_SEC = 0.06;

  /* An exponential ramp cannot reach zero, so decays land here instead. */
  const MIN_LEVEL = 0.0001;
  const ATTACK_SEC = 0.002;
  const RELEASE_PAD_SEC = 0.05;

  const MASTER_BASE = 0.15;
  const MASTER_RANGE = 0.7;
  const MASTER_GLIDE_SEC = 0.08;

  const KICK_LEVEL = 0.9;
  const KICK_PITCH_SEC = 0.055;
  const SNARE_LEVEL = 0.3;
  const SNARE_DECAY_SEC = 0.16;
  const SNARE_CENTER_HZ = 1800;
  const SNARE_Q = 1.2;
  const BASS_LEVEL = 0.45;
  const BASS_CUTOFF_RANGE = 260;
  const HAT_HIGHPASS_HZ = 6500;
  const HAT_DENSITY_THRESHOLD = 0.35;
  const HAT_NONE = 0;
  const HAT_CLOSED = 1;
  const HAT_OPEN = 2;

  const PAD_ATTACK_SEC = 0.9;
  const PAD_RELEASE_SEC = 0.7;
  const PAD_DETUNE_CENTS = 8;
  const PAD_CUTOFF_RANGE = 1600;
  const HALF_DIVISOR = 2;

  const LFO_HZ = 0.05;
  const LFO_DEPTH_HZ = 600;

  const NOISE_SECONDS = 2;
  const NOISE_SCALE = 2;

  const BASS_ROOT_HZ = 110;
  const PAD_ROOT_HZ = 220;
  const SEMITONES_PER_OCTAVE = 12;
  const OCTAVE_RATIO = 2;

  /* Step patterns are 16 bit masks over the bar, one bit per sixteenth note,
   * tested with (mask >>> step) & 1. A mask keeps each pattern to a single
   * number, which is also the only form the magic-number lint accepts here. */
  const GENRES = {
    /* Four to the floor under the offbeat open hat that defines the genre. */
    house: {
      name: 'house', bpm: 87,
      kick: 0x1111, snare: 0x1010, closedHat: 0x5555, openHat: 0x4444, bass: 0x4444,
      kickDecay: 0.34, kickStartHz: 140, kickEndHz: 48,
      bassDecay: 0.16, bassCutoff: 300, bassOctave: -1,
      padBars: 2, padVoices: 3, padSeventh: false, padCutoff: 900, padLevel: 0.15,
      hatDecay: 0.045, hatOpenDecay: 0.18, hatLevel: 0.14,
    },
    /* Rolling sixteenth bass around the kick, and a wide supersaw pad. */
    trance: {
      name: 'trance', bpm: 140,
      kick: 0x1111, snare: 0x1010, closedHat: 0xffff, openHat: 0x4444, bass: 0xeeee,
      kickDecay: 0.26, kickStartHz: 160, kickEndHz: 45,
      bassDecay: 0.1, bassCutoff: 420, bassOctave: -1,
      padBars: 2, padVoices: 7, padSeventh: false, padCutoff: 1400, padLevel: 0.2,
      hatDecay: 0.035, hatOpenDecay: 0.14, hatLevel: 0.12,
    },
    /* A two-step break over sustained sub bass and jazzy sevenths. Fast
     * percussion above half-time harmony is what makes it read as liquid
     * rather than as sped-up trance. */
    liquid: {
      name: 'liquid', bpm: 174,
      kick: 0x0401, snare: 0x1010, closedHat: 0xdbdb, openHat: 0x0420, bass: 0x0001,
      kickDecay: 0.3, kickStartHz: 150, kickEndHz: 42,
      bassDecay: 1.6, bassCutoff: 180, bassOctave: -2,
      padBars: 4, padVoices: 4, padSeventh: true, padCutoff: 1100, padLevel: 0.17,
      hatDecay: 0.03, hatOpenDecay: 0.12, hatLevel: 0.1,
    },
  };

  const GENRE_ORDER = [GENRES.trance, GENRES.house, GENRES.liquid];
  const DEFAULT_BPM = GENRES.trance.bpm;

  /* Am - F - C - G, as semitone offsets from A. */
  const CHORDS = [
    { root: 0, third: 3, fifth: 7, seventh: 10 },
    { root: -4, third: 4, fifth: 7, seventh: 11 },
    { root: 3, third: 4, fifth: 7, seventh: 11 },
    { root: -2, third: 4, fifth: 7, seventh: 10 },
  ];

  const REQUIRED_FACTORIES = [
    'createGain', 'createOscillator', 'createBiquadFilter',
    'createBuffer', 'createBufferSource',
  ];

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function bitAt(mask, step) {
    return (mask >>> step) & 1;
  }

  function noteHz(base, semitones) {
    return base * Math.pow(OCTAVE_RATIO, semitones / SEMITONES_PER_OCTAVE);
  }

  function genreForTempo(bpm) {
    let best = GENRE_ORDER[0];
    GENRE_ORDER.forEach(function (genre) {
      if (Math.abs(genre.bpm - bpm) < Math.abs(best.bpm - bpm)) best = genre;
    });
    return best;
  }

  function requireContext(context) {
    if (!context || typeof context.currentTime !== 'number' || !context.destination) {
      throw new Error('demo audio requires an audio context');
    }
    REQUIRED_FACTORIES.forEach(function (name) {
      if (typeof context[name] !== 'function') {
        throw new Error('demo audio needs a fuller audio context, missing ' + name);
      }
    });
  }

  function createNoiseBuffer(context) {
    const length = Math.floor(context.sampleRate * NOISE_SECONDS);
    const buffer = context.createBuffer(1, length, context.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * NOISE_SCALE - 1;
    return buffer;
  }

  function createFilter(context, type, frequency, target) {
    const filter = context.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = frequency;
    filter.connect(target);
    return filter;
  }

  function buildGraph(state) {
    const context = state.context;
    state.master = context.createGain();
    state.silentTap = context.createGain();
    state.silentTap.gain.value = 0;
    state.master.connect(state.silentTap);
    state.silentTap.connect(context.destination);
    state.bassFilter = createFilter(context, 'lowpass', state.genre.bassCutoff, state.master);
    state.padFilter = createFilter(context, 'lowpass', state.genre.padCutoff, state.master);
    state.hatFilter = createFilter(context, 'highpass', HAT_HIGHPASS_HZ, state.master);
    state.snareFilter = createFilter(context, 'bandpass', SNARE_CENTER_HZ, state.master);
    state.snareFilter.Q.value = SNARE_Q;
    state.noise = createNoiseBuffer(context);
    buildLfo(state);
    applyIntensity(state);
  }

  /* The drift runs as a real modulation edge rather than a timer, so it keeps
   * moving at full resolution on the audio thread while the page is hidden. */
  function buildLfo(state) {
    state.lfo = state.context.createOscillator();
    state.lfo.type = 'triangle';
    state.lfo.frequency.value = LFO_HZ;
    state.lfoDepth = state.context.createGain();
    state.lfoDepth.gain.value = LFO_DEPTH_HZ;
    state.lfo.connect(state.lfoDepth);
    state.lfoDepth.connect(state.padFilter.frequency);
  }

  function applyIntensity(state) {
    const now = state.context.currentTime;
    const level = MASTER_BASE + state.intensity * MASTER_RANGE;
    state.master.gain.setTargetAtTime(level, now, MASTER_GLIDE_SEC);
    state.bassFilter.frequency.setTargetAtTime(
      state.genre.bassCutoff + state.intensity * BASS_CUTOFF_RANGE, now, MASTER_GLIDE_SEC);
    state.padFilter.frequency.setTargetAtTime(
      state.genre.padCutoff + state.intensity * PAD_CUTOFF_RANGE, now, MASTER_GLIDE_SEC);
  }

  /* Percussive envelope shared by every one-shot voice. */
  function strike(param, peak, time, decaySec) {
    param.setValueAtTime(0, time);
    param.linearRampToValueAtTime(peak, time + ATTACK_SEC);
    param.exponentialRampToValueAtTime(MIN_LEVEL, time + decaySec);
  }

  function releaseVoice(state, voice) {
    try {
      voice.source.disconnect();
      voice.env.disconnect();
    } catch (error) {
      console.warn('Demo audio could not release a voice:', error);
    }
    const index = state.voices.indexOf(voice);
    if (index >= 0) state.voices.splice(index, 1);
  }

  function addVoice(state, source, env, time, duration) {
    const voice = { source: source, env: env };
    source.connect(env);
    source.start(time);
    source.stop(time + duration);
    source.onended = function () { releaseVoice(state, voice); };
    state.voices.push(voice);
    state.scheduled += 1;
    return voice;
  }

  function scheduleKick(state, time) {
    const genre = state.genre;
    const osc = state.context.createOscillator();
    const env = state.context.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(genre.kickStartHz, time);
    osc.frequency.exponentialRampToValueAtTime(genre.kickEndHz, time + KICK_PITCH_SEC);
    strike(env.gain, KICK_LEVEL, time, genre.kickDecay);
    env.connect(state.master);
    addVoice(state, osc, env, time, genre.kickDecay);
    state.notes.kick += 1;
  }

  function scheduleNoiseHit(state, time, level, decaySec, filter) {
    const source = state.context.createBufferSource();
    const env = state.context.createGain();
    source.buffer = state.noise;
    source.loop = true;
    strike(env.gain, level, time, decaySec);
    env.connect(filter);
    addVoice(state, source, env, time, decaySec);
  }

  function scheduleSnare(state, time) {
    scheduleNoiseHit(state, time, SNARE_LEVEL, SNARE_DECAY_SEC, state.snareFilter);
    state.notes.snare += 1;
  }

  function scheduleHat(state, time, open) {
    const genre = state.genre;
    const decay = open ? genre.hatOpenDecay : genre.hatDecay;
    scheduleNoiseHit(state, time, genre.hatLevel, decay, state.hatFilter);
    state.notes.hat += 1;
  }

  function scheduleBass(state, time) {
    const genre = state.genre;
    const chord = currentChord(state);
    const osc = state.context.createOscillator();
    const env = state.context.createGain();
    osc.type = 'sawtooth';
    osc.frequency.value = noteHz(BASS_ROOT_HZ, chord.root + genre.bassOctave * SEMITONES_PER_OCTAVE);
    strike(env.gain, BASS_LEVEL, time, genre.bassDecay);
    env.connect(state.bassFilter);
    addVoice(state, osc, env, time, genre.bassDecay);
    state.notes.bass += 1;
  }

  function currentChord(state) {
    const perChord = state.genre.padBars;
    return CHORDS[Math.floor(state.bar / perChord) % CHORDS.length];
  }

  function chordTones(chord, useSeventh) {
    const tones = [chord.root, chord.root + chord.third, chord.root + chord.fifth];
    if (useSeventh) tones.push(chord.root + chord.seventh);
    return tones;
  }

  function schedulePad(state, time) {
    const genre = state.genre;
    const tones = chordTones(currentChord(state), genre.padSeventh);
    const hold = barSeconds(state) * genre.padBars;
    const env = state.context.createGain();
    env.connect(state.padFilter);
    padEnvelope(env.gain, genre.padLevel * state.intensity, time, hold);
    for (let i = 0; i < genre.padVoices; i += 1) {
      const osc = state.context.createOscillator();
      osc.type = 'sawtooth';
      osc.frequency.value = noteHz(PAD_ROOT_HZ, tones[i % tones.length]);
      osc.detune.value = (i - (genre.padVoices - 1) / HALF_DIVISOR) * PAD_DETUNE_CENTS;
      addVoice(state, osc, env, time, hold + PAD_RELEASE_SEC);
    }
    state.notes.pad += 1;
  }

  function padEnvelope(param, peak, time, hold) {
    param.setValueAtTime(0, time);
    param.linearRampToValueAtTime(peak, time + PAD_ATTACK_SEC);
    param.setValueAtTime(peak, time + hold);
    param.linearRampToValueAtTime(0, time + hold + PAD_RELEASE_SEC - RELEASE_PAD_SEC);
  }

  /* Below the density threshold the offbeat filler drops out, so lowering
   * intensity thins the pattern instead of only turning it down. */
  function hatKind(state, step) {
    const genre = state.genre;
    if (bitAt(genre.openHat, step)) return HAT_OPEN;
    if (!bitAt(genre.closedHat, step)) return HAT_NONE;
    if (state.intensity < HAT_DENSITY_THRESHOLD && step % STEPS_PER_BEAT !== 0) return HAT_NONE;
    return HAT_CLOSED;
  }

  function scheduleStep(state, time, step) {
    const genre = state.genre;
    const hat = hatKind(state, step);
    if (bitAt(genre.kick, step)) scheduleKick(state, time);
    if (bitAt(genre.snare, step)) scheduleSnare(state, time);
    if (bitAt(genre.bass, step)) scheduleBass(state, time);
    if (hat !== HAT_NONE) scheduleHat(state, time, hat === HAT_OPEN);
    if (step === 0 && state.bar % genre.padBars === 0) schedulePad(state, time);
  }

  function secondsPerStep(state) {
    return SECONDS_PER_MINUTE / state.bpm / STEPS_PER_BEAT;
  }

  function barSeconds(state) {
    return secondsPerStep(state) * STEPS_PER_BAR;
  }

  function advanceStep(state) {
    state.step += 1;
    if (state.step >= STEPS_PER_BAR) {
      state.step = 0;
      state.bar += 1;
    }
    state.nextStepTime += secondsPerStep(state);
  }

  function drain(state) {
    const context = state.context;
    if (state.nextStepTime < context.currentTime - RESYNC_LAG_SEC) {
      state.nextStepTime = context.currentTime + STEP_LEAD_SEC;
    }
    const horizon = context.currentTime + SCHEDULE_AHEAD_SEC;
    let count = 0;
    while (state.nextStepTime < horizon && count < MAX_STEPS_PER_PUMP) {
      scheduleStep(state, state.nextStepTime, state.step);
      advanceStep(state);
      count += 1;
    }
  }

  /* Idempotent and rate independent: it only ever compares nextStepTime
   * against the context clock, so calling it every frame and calling it once
   * a second produce the same output. That is what lets both the pump timer
   * and the render loop drive it without coordinating. */
  function pump(state) {
    if (!state.running) return;
    try {
      drain(state);
    } catch (error) {
      state.running = false;
      console.warn('Demo audio stopped after a graph failure:', error);
    }
  }

  function armTimer(state) {
    state.timer = state.win.setTimeout(function () {
      state.timer = null;
      if (!state.running) return;
      pump(state);
      armTimer(state);
    }, SCHEDULE_INTERVAL_MS);
  }

  function disarmTimer(state) {
    if (state.timer === null) return;
    state.win.clearTimeout(state.timer);
    state.timer = null;
  }

  function start(state) {
    if (state.running) return;
    state.running = true;
    state.nextStepTime = state.context.currentTime + STEP_LEAD_SEC;
    try {
      state.lfo.start(state.context.currentTime);
      state.lfoStarted = true;
    } catch (error) {
      console.warn('Demo audio could not start its drift oscillator:', error);
    }
    armTimer(state);
    pump(state);
  }

  function stopNode(node) {
    try {
      if (typeof node.stop === 'function') node.stop();
      node.disconnect();
    } catch (error) {
      console.warn('Demo audio could not tear a node down:', error);
    }
  }

  function stop(state) {
    state.running = false;
    disarmTimer(state);
    state.voices.slice().forEach(function (voice) {
      stopNode(voice.source);
      stopNode(voice.env);
    });
    state.voices.length = 0;
    if (state.lfoStarted) stopNode(state.lfo);
    state.lfoStarted = false;
    [state.lfoDepth, state.bassFilter, state.padFilter, state.hatFilter,
      state.snareFilter, state.master, state.silentTap].forEach(function (node) {
      if (node) node.disconnect();
    });
    state.step = 0;
    state.bar = 0;
  }

  function setTempo(state, bpm) {
    if (!Number.isFinite(bpm)) return state.bpm;
    state.bpm = clamp(bpm, MIN_BPM, MAX_BPM);
    state.genre = genreForTempo(state.bpm);
    applyIntensity(state);
    return state.bpm;
  }

  function cycleTempo(state) {
    const index = GENRE_ORDER.indexOf(state.genre);
    return setTempo(state, GENRE_ORDER[(index + 1) % GENRE_ORDER.length].bpm);
  }

  function setIntensity(state, value) {
    if (!Number.isFinite(value)) return state.intensity;
    state.intensity = clamp(value, MIN_INTENSITY, MAX_INTENSITY);
    applyIntensity(state);
    return state.intensity;
  }

  function stats(state) {
    return {
      running: state.running,
      genre: state.genre.name,
      bpm: state.bpm,
      intensity: state.intensity,
      bar: state.bar,
      step: state.step,
      voices: state.voices.length,
      scheduled: state.scheduled,
      aheadSec: state.nextStepTime - state.context.currentTime,
      notes: Object.assign({}, state.notes),
    };
  }

  function createState(opts) {
    const bpm = Number.isFinite(opts.bpm) ? clamp(opts.bpm, MIN_BPM, MAX_BPM) : DEFAULT_BPM;
    const intensity = Number.isFinite(opts.intensity)
      ? clamp(opts.intensity, MIN_INTENSITY, MAX_INTENSITY) : DEFAULT_INTENSITY;
    return {
      context: opts.audioContext,
      win: opts.window || global,
      bpm: bpm,
      genre: genreForTempo(bpm),
      intensity: intensity,
      running: false,
      lfoStarted: false,
      timer: null,
      step: 0,
      bar: 0,
      nextStepTime: 0,
      scheduled: 0,
      voices: [],
      notes: { kick: 0, snare: 0, hat: 0, bass: 0, pad: 0 },
    };
  }

  function create(options) {
    const opts = options || {};
    requireContext(opts.audioContext);
    const state = createState(opts);
    buildGraph(state);
    return {
      getNode: function () { return state.master; },
      start: function () { start(state); },
      stop: function () { stop(state); },
      pump: function () { pump(state); },
      setTempo: function (bpm) { return setTempo(state, bpm); },
      getTempo: function () { return state.bpm; },
      cycleTempo: function () { return cycleTempo(state); },
      setIntensity: function (value) { return setIntensity(state, value); },
      getIntensity: function () { return state.intensity; },
      label: function () { return DEMO_LABEL; },
      stats: function () { return stats(state); },
    };
  }

  global.BCDemoAudio = {
    create: create,
    GENRES: GENRES,
    LABEL: DEMO_LABEL,
    DEFAULT_BPM: DEFAULT_BPM,
    MIN_BPM: MIN_BPM,
    MAX_BPM: MAX_BPM,
    MIN_INTENSITY: MIN_INTENSITY,
    MAX_INTENSITY: MAX_INTENSITY,
    SCHEDULE_AHEAD_SEC: SCHEDULE_AHEAD_SEC,
  };
}(window));
