const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

const QUANTUM_FRAMES = 128;
const DEFAULT_TICK_HZ = 60;
const SAMPLE_RATE = 48000;
const DEFAULT_FRAMES_PER_TICK = SAMPLE_RATE / DEFAULT_TICK_HZ;

/** Run the worklet source against a stub AudioWorkletGlobalScope. */
function loadProcessor(sampleRate) {
  const registered = {};
  class AudioWorkletProcessor {
    constructor() {
      const messages = [];
      this.port = { messages: messages, postMessage: function (message) { messages.push(message); } };
    }
  }
  vm.runInNewContext(fs.readFileSync('src/js/render-tick-processor.js', 'utf8'), {
    AudioWorkletProcessor: AudioWorkletProcessor,
    sampleRate: sampleRate,
    registerProcessor: function (name, constructor) { registered[name] = constructor; },
  });
  return registered;
}

function createProcessor(options, sampleRate) {
  const Processor = loadProcessor(sampleRate || SAMPLE_RATE)['bc-render-tick'];
  return new Processor(options);
}

function runQuanta(processor, count) {
  for (let i = 0; i < count; i += 1) processor.process([], [[new Float32Array(QUANTUM_FRAMES)]]);
}

test('registers the processor under the name the render driver requests', function () {
  assert.deepEqual(Object.keys(loadProcessor(SAMPLE_RATE)), ['bc-render-tick']);
});

test('derives frames per tick from the sample rate and requested rate', function () {
  const processor = createProcessor({ processorOptions: { tickHz: 30 } });
  assert.equal(processor.framesPerTick, SAMPLE_RATE / 30);
});

test('falls back to 60 Hz when the requested rate is missing or unusable', function () {
  [undefined, null, 0, -5, NaN, 'abc'].forEach(function (tickHz) {
    const processor = createProcessor({ processorOptions: { tickHz: tickHz } });
    assert.equal(processor.framesPerTick, DEFAULT_FRAMES_PER_TICK, 'tickHz ' + String(tickHz));
  });
  assert.equal(createProcessor({}).framesPerTick, DEFAULT_FRAMES_PER_TICK);
  assert.equal(createProcessor(undefined).framesPerTick, DEFAULT_FRAMES_PER_TICK);
});

test('never ticks faster than once per audio quantum', function () {
  const processor = createProcessor({ processorOptions: { tickHz: 1000 } });
  assert.equal(processor.framesPerTick, QUANTUM_FRAMES);
  runQuanta(processor, 3);
  assert.deepEqual(processor.port.messages, [1, 2, 3]);
});

test('posts an incrementing tick only once a frame interval of audio has elapsed', function () {
  const processor = createProcessor({ processorOptions: { tickHz: DEFAULT_TICK_HZ } });
  const quantaPerTick = Math.ceil(DEFAULT_FRAMES_PER_TICK / QUANTUM_FRAMES);
  runQuanta(processor, quantaPerTick - 1);
  assert.deepEqual(processor.port.messages, []);
  runQuanta(processor, 1);
  assert.deepEqual(processor.port.messages, [1]);
  runQuanta(processor, quantaPerTick);
  assert.deepEqual(processor.port.messages, [1, 2]);
});

test('zero-fills every output channel', function () {
  const processor = createProcessor();
  const left = new Float32Array(QUANTUM_FRAMES).fill(1);
  const right = new Float32Array(QUANTUM_FRAMES).fill(-1);
  processor.process([], [[left, right]]);
  assert.ok(left.every(function (sample) { return sample === 0; }));
  assert.ok(right.every(function (sample) { return sample === 0; }));
});

test('keeps running when no output buffer is provided', function () {
  const processor = createProcessor();
  assert.equal(processor.process([], []), true);
});

test('returns true so the node is never garbage collected', function () {
  const processor = createProcessor();
  assert.equal(processor.process([], [[new Float32Array(QUANTUM_FRAMES)]]), true);
});
