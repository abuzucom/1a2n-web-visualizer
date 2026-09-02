const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const EPSILON = 1e-6;
const STEPS_PER_BAR = 16;

/* Records every scheduled automation call so a test can prove an envelope was
 * written, and keeps `value` readable for the params set directly. */
function createParam(log) {
  const param = {
    value: 0,
    calls: [],
    setValueAtTime: function (v, t) { param.calls.push(['set', v, t]); param.value = v; return param; },
    linearRampToValueAtTime: function (v, t) { param.calls.push(['lin', v, t]); return param; },
    exponentialRampToValueAtTime: function (v, t) { param.calls.push(['exp', v, t]); return param; },
    setTargetAtTime: function (v, t, c) { param.calls.push(['target', v, t, c]); param.value = v; return param; },
    cancelScheduledValues: function (t) { param.calls.push(['cancel', t]); return param; },
  };
  log.push(param);
  return param;
}

function createNode(kind, state, extra) {
  const node = {
    kind: kind,
    connectedTo: [],
    disconnects: 0,
    startedAt: null,
    stoppedAt: null,
    onended: null,
    connect: function (target) { node.connectedTo.push(target); return target; },
    disconnect: function () { node.disconnects += 1; },
    start: function (t) { node.startedAt = t === undefined ? 0 : t; state.started.push(node); },
    stop: function (t) { node.stoppedAt = t === undefined ? 0 : t; },
  };
  Object.assign(node, extra || {});
  state.nodes.push(node);
  return node;
}

function createFakeContext(options) {
  const opts = options || {};
  const state = { nodes: [], params: [], started: [], buffers: 0 };
  const context = {
    state: 'running',
    currentTime: 0,
    sampleRate: 48000,
    destination: { kind: 'destination', connectedTo: [], connect: function () {} },
    nodes: state.nodes,
    started: state.started,
    createGain: function () { return createNode('gain', state, { gain: createParam(state.params) }); },
    createOscillator: function () {
      return createNode('oscillator', state, {
        type: '', frequency: createParam(state.params), detune: createParam(state.params),
      });
    },
    createBiquadFilter: function () {
      return createNode('biquad', state, {
        type: '', frequency: createParam(state.params), Q: createParam(state.params),
      });
    },
    createBufferSource: function () {
      return createNode('buffersource', state, {
        buffer: null, loop: false, loopStart: 0, loopEnd: 0, playbackRate: createParam(state.params),
      });
    },
    createBuffer: function (channels, length, rate) {
      state.buffers += 1;
      return {
        numberOfChannels: channels, length: length, sampleRate: rate,
        getChannelData: function () { return new Float32Array(length); },
      };
    },
  };
  if (opts.omit) opts.omit.forEach(function (name) { delete context[name]; });
  return context;
}

/* Timers are queued, never real, so a test drives the scheduler by hand. */
function createFakeWindow() {
  const timers = [];
  return {
    timers: timers,
    cleared: [],
    setTimeout: function (callback) { timers.push(callback); return timers.length; },
    clearTimeout: function (handle) { this.cleared.push(handle); },
  };
}

function loadModule() {
  const window = {};
  vm.runInNewContext(fs.readFileSync('src/js/demo-audio.js', 'utf8'), { window: window, console: console });
  return window.BCDemoAudio;
}

function createHarness(createOptions) {
  const BCDemoAudio = loadModule();
  const context = createFakeContext();
  const win = createFakeWindow();
  const demo = BCDemoAudio.create(Object.assign({ audioContext: context, window: win }, createOptions || {}));
  return { BCDemoAudio: BCDemoAudio, context: context, win: win, demo: demo };
}

/** Run the scheduler forward by `seconds` in small clock steps, as the real
 * context clock and pump timer would. */
function advance(harness, seconds) {
  const tick = 0.05;
  const end = harness.context.currentTime + seconds;
  while (harness.context.currentTime < end) {
    harness.context.currentTime = Math.min(end, harness.context.currentTime + tick);
    harness.demo.pump();
  }
}

function barSeconds(bpm) {
  const SECONDS_PER_MINUTE = 60;
  const BEATS_PER_BAR = 4;
  return SECONDS_PER_MINUTE / bpm * BEATS_PER_BAR;
}

test('create builds a silent tap as the only path to the destination', function () {
  const harness = createHarness();
  const toDestination = harness.context.nodes.filter(function (node) {
    return node.connectedTo.indexOf(harness.context.destination) >= 0;
  });
  assert.equal(toDestination.length, 1, 'exactly one node may reach the destination');
  assert.equal(toDestination[0].kind, 'gain');
  assert.equal(toDestination[0].gain.value, 0, 'the tap must emit digital silence');
  assert.notEqual(toDestination[0], harness.demo.getNode(), 'the tap is not the analysis node');
});

test('getNode returns a node that never reaches the destination directly', function () {
  const harness = createHarness();
  const master = harness.demo.getNode();
  assert.equal(master.kind, 'gain');
  assert.equal(master.connectedTo.indexOf(harness.context.destination), -1);
});

test('create throws on a context missing a required factory', function () {
  const BCDemoAudio = loadModule();
  const context = createFakeContext({ omit: ['createBiquadFilter'] });
  assert.throws(function () {
    BCDemoAudio.create({ audioContext: context, window: createFakeWindow() });
  }, /context/i);
});

test('create throws without an audio context', function () {
  const BCDemoAudio = loadModule();
  assert.throws(function () { BCDemoAudio.create({ window: createFakeWindow() }); }, /context/i);
});

test('start schedules only inside the lookahead window', function () {
  const harness = createHarness();
  harness.context.currentTime = 10;
  harness.demo.start();
  const ahead = harness.BCDemoAudio.SCHEDULE_AHEAD_SEC;
  harness.context.started.forEach(function (node) {
    assert.ok(node.startedAt >= harness.context.currentTime - EPSILON, 'never schedules in the past');
    assert.ok(node.startedAt <= harness.context.currentTime + ahead + EPSILON, 'never overruns the lookahead');
  });
  assert.ok(harness.demo.stats().scheduled > 0, 'start primes the queue');
});

test('pump is idempotent while the clock stands still', function () {
  const harness = createHarness();
  harness.demo.start();
  const after = harness.context.started.length;
  for (let i = 0; i < 5; i += 1) harness.demo.pump();
  assert.equal(harness.context.started.length, after, 'a frozen clock schedules nothing new');
});

test('pump does nothing before start and after stop', function () {
  const harness = createHarness();
  harness.demo.pump();
  assert.equal(harness.context.started.length, 0);
  harness.demo.start();
  harness.demo.stop();
  const after = harness.context.started.length;
  advance(harness, 4);
  assert.equal(harness.context.started.length, after, 'a stopped generator schedules nothing');
});

test('kick spacing follows the tempo', function () {
  const harness = createHarness({ bpm: 120 });
  harness.demo.start();
  advance(harness, barSeconds(120) * 2);
  const kicks = harness.context.started
    .filter(function (node) { return node.kind === 'oscillator' && node.type === 'sine'; })
    .map(function (node) { return node.startedAt; })
    .sort(function (a, b) { return a - b; });
  assert.ok(kicks.length >= 4, 'expected several kicks');
  const SECONDS_PER_BEAT = 0.5;
  for (let i = 1; i < kicks.length; i += 1) {
    assert.ok(Math.abs((kicks[i] - kicks[i - 1]) - SECONDS_PER_BEAT) < 0.01,
      'kicks land one beat apart at 120 BPM');
  }
});

test('a tempo change leaves already-scheduled notes untouched', function () {
  const harness = createHarness({ bpm: 120 });
  harness.demo.start();
  const before = harness.context.started.map(function (node) { return node.startedAt; });
  harness.demo.setTempo(180);
  const after = harness.context.started.slice(0, before.length)
    .map(function (node) { return node.startedAt; });
  assert.deepEqual(after, before, 'queued notes keep their original times');
});

test('setTempo clamps, ignores nonsense, and snaps to a genre', function () {
  const harness = createHarness();
  assert.equal(harness.demo.setTempo(0), harness.BCDemoAudio.MIN_BPM);
  assert.equal(harness.demo.setTempo(9999), harness.BCDemoAudio.MAX_BPM);
  harness.demo.setTempo(140);
  assert.equal(harness.demo.setTempo(NaN), 140, 'a non-finite tempo is ignored');
  harness.demo.setTempo(88);
  assert.equal(harness.demo.stats().genre, 'house', 'a nearby tempo adopts that genre');
});

test('cycleTempo walks the three genres and returns home', function () {
  const harness = createHarness();
  assert.equal(harness.demo.getTempo(), harness.BCDemoAudio.DEFAULT_BPM);
  assert.equal(harness.demo.stats().genre, 'trance');
  assert.equal(harness.demo.cycleTempo(), 87);
  assert.equal(harness.demo.stats().genre, 'house');
  assert.equal(harness.demo.cycleTempo(), 174);
  assert.equal(harness.demo.stats().genre, 'liquid');
  assert.equal(harness.demo.cycleTempo(), 140);
  assert.equal(harness.demo.stats().genre, 'trance');
});

test('each genre plays its own pattern, not the same loop faster', function () {
  const counts = {};
  ['house', 'trance', 'liquid'].forEach(function (name) {
    const harness = createHarness();
    const genre = harness.BCDemoAudio.GENRES[name];
    harness.demo.setTempo(genre.bpm);
    harness.demo.start();
    const startNotes = harness.demo.stats().notes;
    advance(harness, barSeconds(genre.bpm) * 4);
    const endNotes = harness.demo.stats().notes;
    counts[name] = {
      kick: endNotes.kick - startNotes.kick,
      hat: endNotes.hat - startNotes.hat,
      pad: endNotes.pad - startNotes.pad,
    };
  });
  assert.ok(counts.house.kick > counts.liquid.kick,
    'four-to-the-floor genres kick more often per bar than a breakbeat');
  assert.ok(counts.liquid.hat > counts.house.hat,
    'liquid drum and bass carries busier hats than house');
  assert.ok(counts.liquid.pad < counts.trance.pad,
    'liquid changes chords half as often, its half-time harmony');
});

test('the kick mask matches the genre definition', function () {
  const harness = createHarness();
  const GENRES = harness.BCDemoAudio.GENRES;
  function popcount(mask) {
    let total = 0;
    for (let i = 0; i < STEPS_PER_BAR; i += 1) total += (mask >>> i) & 1;
    return total;
  }
  assert.equal(popcount(GENRES.house.kick), 4, 'house is four to the floor');
  assert.equal(popcount(GENRES.trance.kick), 4, 'trance is four to the floor');
  assert.equal(popcount(GENRES.liquid.kick), 2, 'liquid rides a two-step break');
  assert.equal(GENRES.liquid.padBars, 4, 'liquid holds each chord twice as long');
});

test('setIntensity clamps and opens up the bus', function () {
  const harness = createHarness({ intensity: 0.2 });
  assert.equal(harness.demo.setIntensity(9), 1);
  assert.equal(harness.demo.setIntensity(-9), harness.BCDemoAudio.MIN_INTENSITY);
  const master = harness.demo.getNode();
  harness.demo.setIntensity(1);
  const loud = master.gain.value;
  harness.demo.setIntensity(harness.BCDemoAudio.MIN_INTENSITY);
  assert.ok(master.gain.value < loud, 'lower intensity lowers the master bus');
  assert.equal(harness.demo.setIntensity(NaN), harness.BCDemoAudio.MIN_INTENSITY);
});

test('a long stall resyncs instead of firing a stacked burst', function () {
  const harness = createHarness();
  harness.demo.start();
  const before = harness.context.started.length;
  harness.context.currentTime += 60;
  harness.demo.pump();
  const scheduled = harness.context.started.length - before;
  assert.ok(scheduled > 0, 'the generator keeps running after a stall');
  assert.ok(scheduled < 200, 'a 60 second stall must not stack a minute of notes');
  const ahead = harness.demo.stats().aheadSec;
  const stepSec = 60 / harness.demo.getTempo() / 4;
  assert.ok(ahead > 0, 'the queue is ahead of the clock again, not 60 seconds behind');
  assert.ok(ahead <= harness.BCDemoAudio.SCHEDULE_AHEAD_SEC + stepSec + EPSILON,
    'the queue stops within one step of the lookahead horizon');
});

test('the pad filter is modulated by a low frequency oscillator', function () {
  const harness = createHarness();
  const slow = harness.context.nodes.filter(function (node) {
    return node.kind === 'oscillator' && node.frequency.value > 0 && node.frequency.value < 1;
  });
  assert.equal(slow.length, 1, 'exactly one sub-hertz oscillator, the drift LFO');
  const depth = slow[0].connectedTo[0];
  assert.equal(depth.kind, 'gain');
  const target = depth.connectedTo[0];
  const filters = harness.context.nodes.filter(function (node) { return node.kind === 'biquad'; });
  const isFilterFrequency = filters.some(function (node) { return node.frequency === target; });
  assert.ok(isFilterFrequency, 'the LFO depth drives a filter frequency param');
});

test('stop tears the graph down and is idempotent', function () {
  const harness = createHarness();
  harness.demo.start();
  advance(harness, 1);
  harness.demo.stop();
  assert.equal(harness.demo.stats().running, false);
  assert.ok(harness.win.cleared.length > 0, 'the pump timer is cleared');
  const master = harness.demo.getNode();
  assert.ok(master.disconnects > 0, 'the master bus is disconnected');
  harness.context.started.forEach(function (node) {
    assert.notEqual(node.stoppedAt, null, 'every started source is stopped');
  });
  harness.demo.stop();
  assert.equal(harness.demo.stats().running, false, 'a second stop is harmless');
});

test('stop before start is harmless', function () {
  const harness = createHarness();
  harness.demo.stop();
  assert.equal(harness.demo.stats().running, false);
});

test('pump never throws and shuts itself down on a graph failure', function () {
  const BCDemoAudio = loadModule();
  const context = createFakeContext();
  const demo = BCDemoAudio.create({ audioContext: context, window: createFakeWindow() });
  demo.start();
  context.createOscillator = function () { throw new Error('node budget exhausted'); };
  context.createBufferSource = function () { throw new Error('node budget exhausted'); };
  context.currentTime += 30;
  assert.doesNotThrow(function () { demo.pump(); });
  assert.equal(demo.stats().running, false, 'a broken graph stops the generator');
});

test('stats reports the live state', function () {
  const harness = createHarness({ bpm: 140, intensity: 0.5 });
  const idle = harness.demo.stats();
  assert.equal(idle.running, false);
  assert.equal(idle.bpm, 140);
  assert.equal(idle.intensity, 0.5);
  assert.equal(idle.genre, 'trance');
  harness.demo.start();
  advance(harness, barSeconds(140));
  const live = harness.demo.stats();
  assert.equal(live.running, true);
  assert.ok(live.scheduled > idle.scheduled, 'the scheduled counter is monotonic');
  assert.ok(live.notes.kick > 0 && live.notes.hat > 0, 'drums are being scheduled');
  assert.ok(live.bar >= 0 && live.step >= 0 && live.step < STEPS_PER_BAR);
});

test('label names the synthetic input and reads as no known loopback device', function () {
  const harness = createHarness();
  const label = harness.demo.label();
  assert.ok(label.length > 0);
  assert.ok(!/voicemeeter|vb-?audio|vb-?cable|cable\s*output|stereo\s*mix|monitor\s+of|blackhole|loopback|soundflower|what\s*u\s*hear/i
    .test(label), 'the keepalive must not read the demo label as a loopback');
});

test('the module never touches navigator or a real timer', function () {
  const window = {};
  const source = fs.readFileSync('src/js/demo-audio.js', 'utf8');
  vm.runInNewContext(source, { window: window, console: console });
  const harness = createHarness();
  harness.demo.start();
  advance(harness, 2);
  assert.ok(harness.win.timers.length > 0, 'the pump timer goes through the injected window');
});
