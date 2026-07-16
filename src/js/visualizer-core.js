/*
 * visualizer-core.js
 * Shared butterchurn controller used by both obs.html and fullscreen.html.
 *
 * Loaded as a classic script so it works from file:// without CORS issues.
 * Exposes a single global: window.BCViz.
 */
(function (global) {
  'use strict';

  const MAX_PIXEL_RATIO = 2;
  const PRESET_PACKS = [
    'butterchurnPresets', 'butterchurnPresetsExtra',
    'butterchurnPresetsExtra2', 'butterchurnPresetsMD1',
  ];

  function getLib(name) {
    const library = global[name];
    return library && (library.default || library);
  }

  function mergePresetPacks() {
    const presets = {};
    PRESET_PACKS.forEach(function (name) {
      const pack = getLib(name);
      if (!pack || !pack.getPresets) return;
      const packPresets = pack.getPresets();
      Object.keys(packPresets).forEach(function (key) {
        if (!(key in presets)) presets[key] = packPresets[key];
      });
    });
    return presets;
  }

  function buildExtraChunkMap(presets, extraIndex) {
    const extraChunkOf = {};
    if (!extraIndex || !extraIndex.chunks) return extraChunkOf;
    extraIndex.chunks.forEach(function (names, cid) {
      names.forEach(function (name) {
        if (!(name in presets) && !(name in extraChunkOf)) extraChunkOf[name] = cid;
      });
    });
    return extraChunkOf;
  }

  function validateEquation(source) {
    if (!source || !source.trim()) return;
    // Compile only. Butterchurn also uses dynamic functions for equations;
    // this prevents malformed text from reaching its shader setup path.
    new Function('a', source + ' return a;');
  }

  function validatePresetEquations(preset) {
    ['init_eqs_str', 'frame_eqs_str', 'pixel_eqs_str'].forEach(function (field) {
      validateEquation(preset[field]);
    });
    [['shape', preset.shapes], ['wave', preset.waves]].forEach(function (group) {
      (group[1] || []).forEach(function (item) {
        ['init_eqs_str', 'frame_eqs_str', 'point_eqs_str'].forEach(function (field) {
          validateEquation(item[field]);
        });
      });
    });
  }

  function settleChunk(state, cid, ok) {
    const waiters = state.waiters[cid] || [];
    delete state.waiters[cid];
    waiters.forEach(function (resolve) { resolve(ok); });
  }

  function touchChunk(state, cid) {
    state.lru = state.lru.filter(function (current) { return current !== cid; });
    state.lru.push(cid);
  }

  function evictChunks(state) {
    const currentCid = state.extraChunkOf[state.keys[state.getCurrentIndex()]];
    while (state.lru.length > state.cacheMax) {
      const evictIndex = state.lru.findIndex(function (cid) { return cid !== currentCid; });
      if (evictIndex < 0) return;
      const cid = state.lru.splice(evictIndex, 1)[0];
      (state.owned[cid] || []).forEach(function (name) { delete state.presets[name]; });
      delete state.owned[cid];
      delete state.status[cid];
      const script = state.scripts[cid];
      if (script && script.parentNode) script.parentNode.removeChild(script);
      delete state.scripts[cid];
    }
  }

  function registerChunk(state, cid, chunkPresets) {
    if (state.status[cid] === 'loaded') return;
    const owned = [];
    Object.keys(chunkPresets).forEach(function (name) {
      if (state.extraChunkOf[name] !== cid) return;
      state.presets[name] = chunkPresets[name];
      owned.push(name);
    });
    state.owned[cid] = owned;
    state.status[cid] = 'loaded';
    touchChunk(state, cid);
    evictChunks(state);
    settleChunk(state, cid, true);
  }

  function failChunk(state, cid) {
    if (state.status[cid] !== 'loading') return;
    state.status[cid] = 'failed';
    (state.extraIndex.chunks[cid] || []).forEach(function (name) {
      if (state.extraChunkOf[name] === cid) state.failed.add(name);
    });
    settleChunk(state, cid, false);
  }

  function ensureChunk(state, cid) {
    if (state.status[cid] === 'loaded') {
      touchChunk(state, cid);
      return Promise.resolve(true);
    }
    if (state.status[cid] === 'failed') return Promise.resolve(false);
    return new Promise(function (resolve) {
      (state.waiters[cid] = state.waiters[cid] || []).push(resolve);
      if (state.status[cid] === 'loading') return;
      state.status[cid] = 'loading';
      const timer = setTimeout(function () { failChunk(state, cid); }, 10000);
      const script = document.createElement('script');
      const filename = state.extraIndex.files && state.extraIndex.files[cid]
        ? state.extraIndex.files[cid]
        : 'chunk-' + String(cid).padStart(3, '0') + '.js';
      script.src = 'presets-extra/' + filename;
      script.onerror = function () { clearTimeout(timer); failChunk(state, cid); };
      script.onload = function () { clearTimeout(timer); failChunk(state, cid); };
      state.scripts[cid] = script;
      document.head.appendChild(script);
    });
  }

  function createPresetStore(opts, getCurrentIndex) {
    const presets = mergePresetPacks();
    const residentKeys = Object.keys(presets);
    const extraIndex = global.BCExtraPresetIndex || { chunks: [] };
    const extraChunkOf = buildExtraChunkMap(presets, extraIndex);
    const keys = residentKeys.concat(Object.keys(extraChunkOf)).sort();
    const failed = new Set();
    const state = {
      presets: presets,
      keys: keys,
      extraIndex: extraIndex,
      extraChunkOf: extraChunkOf,
      failed: failed,
      status: {},
      waiters: {},
      scripts: {},
      owned: {},
      lru: [],
      cacheMax: opts.chunkCacheMax || 16,
      getCurrentIndex: getCurrentIndex,
    };
    global.__bcPresetChunk = function (cid, chunkPresets) {
      registerChunk(state, cid, chunkPresets);
    };
    return {
      state: state,
      presets: presets,
      residentKeys: residentKeys,
      keys: keys,
      failed: failed,
    };
  }

  function stepIndex(controller, direction) {
    if (!controller.store.keys.length) return controller.idx;
    let index = controller.idx;
    for (let count = 0; count < controller.store.keys.length; count++) {
      index = (index + direction + controller.store.keys.length) % controller.store.keys.length;
      const name = controller.store.keys[index];
      if (!controller.excluded.has(name) && !controller.store.failed.has(name)) return index;
    }
    return (controller.idx + direction + controller.store.keys.length) % controller.store.keys.length;
  }

  function candidatePool(controller, includeFailedFallback) {
    let pool = controller.store.keys.map(function (_, index) { return index; })
      .filter(function (index) {
        const name = controller.store.keys[index];
        return index !== controller.idx && !controller.excluded.has(name) && !controller.store.failed.has(name);
      });
    if (!pool.length && includeFailedFallback !== false) {
      pool = controller.store.keys.map(function (_, index) { return index; })
        .filter(function (index) { return index !== controller.idx; });
    }
    return pool;
  }

  function applyPreset(controller, index, blend, announce) {
    const name = controller.store.keys[index];
    const cid = controller.store.state.extraChunkOf[name];
    const preset = controller.store.presets[name];
    const effectiveBlend = blend != null ? blend : controller.defaultBlend;
    if (cid != null) touchChunk(controller.store.state, cid);
    try {
      validatePresetEquations(preset);
      controller.visualizer.loadPreset(preset, effectiveBlend);
    } catch (error) {
      controller.store.failed.add(name);
      console.warn('Preset load failed; skipping:', {
        name: name,
        logicalChunk: cid,
        mode: controller.navigationMode,
        error: error,
      });
      restoreLastGood(controller);
      controller.onToast('\u26A0 broken preset skipped: ' + name);
      return false;
    }
    controller.idx = index;
    controller.lastGoodPreset = preset;
    controller.lastGoodBlend = effectiveBlend;
    controller.lastGoodName = name;
    controller.onPreset(index, name);
    if (announce !== false) controller.onToast(name);
    return true;
  }

  function restoreLastGood(controller) {
    if (!controller.lastGoodPreset) return false;
    try {
      controller.visualizer.loadPreset(controller.lastGoodPreset, controller.lastGoodBlend);
      return true;
    } catch (error) {
      console.error('Unable to restore last known-good preset:', {
        name: controller.lastGoodName,
        error: error,
      });
      stopRenderLoop(controller);
      controller.onToast('\u26A0 visualizer recovery failed');
      return false;
    }
  }

  function loadMissingPreset(controller, index, blend, announce, seq, mode) {
    const name = controller.store.keys[index];
    const ready = controller.ensureExperimentalImages
      ? controller.ensureExperimentalImages()
      : Promise.resolve();
    ready.then(function () {
      return ensureChunk(controller.store.state, controller.store.state.extraChunkOf[name]);
    }).then(function (ok) {
      if (seq !== controller.loadSeq) return;
      if (!ok || !(name in controller.store.presets)) {
        controller.onToast('\u26A0 preset unavailable, skipping: ' + name);
        if (controller.store.failed.size + controller.excluded.size < controller.store.keys.length) {
          const fallback = fallbackIndex(controller, mode);
          if (fallback != null) loadPreset(controller, fallback, blend, announce, mode);
        }
        return;
      }
      loadPreset(controller, index, blend, announce, mode);
    });
  }

  function fallbackIndex(controller, mode) {
    if (mode === 'random') {
      const pool = candidatePool(controller, false);
      return pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
    }
    return stepIndex(controller, 1);
  }

  function loadPreset(controller, requestedIndex, blend, announce, mode) {
    if (!controller.visualizer || !controller.store.keys.length) return false;
    let index = (requestedIndex + controller.store.keys.length) % controller.store.keys.length;
    const seq = ++controller.loadSeq;
    controller.navigationMode = mode || 'sequential';
    for (let attempts = 0; attempts < controller.store.keys.length; attempts++) {
      const name = controller.store.keys[index];
      if (!(name in controller.store.presets)) {
        loadMissingPreset(controller, index, blend, announce, seq, controller.navigationMode);
        return undefined;
      }
      if (applyPreset(controller, index, blend, announce)) return true;
      const fallback = fallbackIndex(controller, controller.navigationMode);
      if (fallback == null) break;
      index = fallback;
    }
    controller.onToast('\u26A0 no working preset found');
    stopRenderLoop(controller);
    return false;
  }

  function restartCycle(controller) {
    if (controller.cycleTimer) clearInterval(controller.cycleTimer);
    if (!controller.cycleOn) return;
    controller.cycleTimer = setInterval(function () {
      if (controller.shuffleOn) loadRandom(controller);
      else loadPreset(controller, stepIndex(controller, 1));
    }, controller.cycleSecs * 1000);
  }

  function loadRandom(controller) {
    if (controller.store.keys.length < 2) return loadPreset(controller, 0, undefined, true, 'random');
    const pool = candidatePool(controller, false);
    if (!pool.length) {
      controller.onToast('\u26A0 no working random preset found');
      return false;
    }
    loadPreset(controller, pool[Math.floor(Math.random() * pool.length)], undefined, true, 'random');
  }

  function removeCurrent(controller) {
    if (!controller.store.keys.length) return null;
    const removed = controller.store.keys[controller.idx];
    controller.excluded.add(removed);
    if (controller.shuffleOn) loadRandom(controller);
    else loadPreset(controller, stepIndex(controller, 1));
    restartCycle(controller);
    return removed;
  }

  function createPlaybackController(store, opts, onToast, onPreset, canvas) {
    return {
      store: store,
      onToast: onToast,
      onPreset: onPreset,
      canvas: canvas,
      defaultBlend: opts.blend != null ? opts.blend : 2.7,
      visualizer: null,
      idx: 0,
      excluded: new Set(),
      loadSeq: 0,
      cycleOn: opts.cycleOn !== false,
      shuffleOn: opts.shuffle === true,
      cycleSecs: opts.cycleSecs || 20,
      cycleTimer: null,
      navigationMode: 'sequential',
      lastGoodPreset: null,
      lastGoodBlend: 0,
      lastGoodName: '',
      renderFrame: null,
      rendering: false,
    };
  }

  function stopRenderLoop(controller) {
    controller.rendering = false;
    if (controller.renderFrame != null) {
      global.cancelAnimationFrame(controller.renderFrame);
      controller.renderFrame = null;
    }
  }

  function sizeCanvas(audio) {
    const dpr = Math.min(global.devicePixelRatio || 1, MAX_PIXEL_RATIO);
    audio.canvas.width = Math.round(global.innerWidth * dpr);
    audio.canvas.height = Math.round(global.innerHeight * dpr);
    if (audio.visualizer) audio.visualizer.setRendererSize(audio.canvas.width, audio.canvas.height);
  }

  async function getDevices(audio) {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      audio.inputDevices = all.filter(function (device) { return device.kind === 'audioinput'; });
    } catch (error) {
      audio.inputDevices = [];
      console.warn('Unable to enumerate audio devices:', error);
    }
    return audio.inputDevices;
  }

  function connectStream(audio, stream) {
    if (audio.micStream && audio.micStream !== stream) {
      audio.micStream.getTracks().forEach(function (track) { track.stop(); });
    }
    if (audio.sourceNode) audio.visualizer.disconnectAudio(audio.sourceNode);
    audio.micStream = stream;
    audio.sourceNode = audio.audioCtx.createMediaStreamSource(stream);
    audio.visualizer.connectAudio(audio.sourceNode);
  }

  function openStream(deviceId) {
    const constraints = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
    if (deviceId) constraints.deviceId = { exact: deviceId };
    return navigator.mediaDevices.getUserMedia({ audio: constraints });
  }

  async function useDevice(audio, index) {
    const requestSeq = ++audio.deviceRequestSeq;
    if (!audio.inputDevices.length) await getDevices(audio);
    if (!audio.inputDevices.length) return null;
    audio.deviceIdx = (index + audio.inputDevices.length) % audio.inputDevices.length;
    const device = audio.inputDevices[audio.deviceIdx];
    const stream = await openStream(device.deviceId);
    if (requestSeq !== audio.deviceRequestSeq) {
      stream.getTracks().forEach(function (track) { track.stop(); });
      return null;
    }
    connectStream(audio, stream);
    audio.onToast('\uD83C\uDF99 ' + (device.label || ('Input ' + (audio.deviceIdx + 1))));
    return device;
  }

  async function useDeviceById(audio, id) {
    if (!audio.inputDevices.length) await getDevices(audio);
    const index = audio.inputDevices.findIndex(function (device) { return device.deviceId === id; });
    return index >= 0 ? useDevice(audio, index) : null;
  }

  function loadExtraImages(audio, includeExperimental) {
    const libraryNames = includeExperimental
      ? ['butterchurnExtraImagesExp']
      : ['butterchurnExtraImages'];
    const libraries = libraryNames.map(getLib).filter(function (library) {
      return library && library.getImages;
    });
    if (!libraries.length) return;
    try {
      const images = {};
      libraries.forEach(function (library) { Object.assign(images, library.getImages()); });
      audio.visualizer.loadExtraImages(images);
    } catch (error) {
      console.warn('Failed to load extra images (non-critical):', error);
    }
  }

  function ensureExperimentalImages(audio) {
    if (audio.experimentalImagesReady) return Promise.resolve();
    if (!audio.experimentalImagesLoading) {
      audio.experimentalImagesLoading = Promise.resolve().then(function () {
        loadExtraImages(audio, true);
        audio.experimentalImagesReady = true;
      });
    }
    return audio.experimentalImagesLoading;
  }

  async function connectInitialStream(audio, deviceId) {
    try {
      const stream = await openStream(deviceId);
      await getDevices(audio);
      if (audio.started) connectStream(audio, stream);
      else stream.getTracks().forEach(function (track) { track.stop(); });
    } catch (error) {
      console.warn('Audio input unavailable; visualizer will continue:', error);
      audio.onToast('Audio input unavailable; visualizer is running');
    }
  }

  function initializeAudio(audio, playback, deviceId) {
    if (!audio.prepared) prepareAudio(audio, playback);
    audio.audioCtx.resume().catch(function (error) {
      console.warn('Audio context resume failed:', error);
    });
    connectInitialStream(audio, deviceId);
  }

  function prepareAudio(audio, playback) {
    if (audio.prepared) return;
    audio.audioCtx = new (global.AudioContext || global.webkitAudioContext)();
    createVisualizer(audio, playback);
    if (!loadInitialPreset(audio, playback, false)) {
      audio.audioCtx.close();
      audio.audioCtx = null;
      throw new Error('no valid preset could be loaded');
    }
    audio.prepared = true;
  }

  function createVisualizer(audio, playback) {
    audio.visualizer = audio.Butterchurn.createVisualizer(audio.audioCtx, audio.canvas, {
      width: audio.canvas.width, height: audio.canvas.height, pixelRatio: 1, textureRatio: 1,
    });
    playback.visualizer = audio.visualizer;
    playback.ensureExperimentalImages = function () { return ensureExperimentalImages(audio); };
    loadExtraImages(audio, false);
  }

  function loadInitialPreset(audio, playback, randomFirst) {
    const resident = playback.store.residentKeys;
    let first = resident.length ? playback.store.keys.indexOf(resident[0]) : 0;
    if (randomFirst && audio.opts.randomFirst && resident.length) {
      first = playback.store.keys.indexOf(resident[Math.floor(Math.random() * resident.length)]);
    }
    const loaded = loadPreset(playback, first, 0, false, 'startup');
    if (loaded === false || !playback.lastGoodPreset) {
      audio.onToast('\u26A0 no valid preset could be loaded');
      return false;
    }
    return true;
  }

  function startRenderLoop(audio, playback, loadInitial) {
    if (loadInitial && !loadInitialPreset(audio, playback, true)) return;
    playback.rendering = true;
    scheduleRender(audio, playback);
    restartCycle(playback);
  }

  function scheduleRender(audio, playback) {
    (function render() {
      if (!playback.rendering) return;
      try {
        audio.visualizer.render();
      } catch (error) {
        console.error('Visualizer render failed:', error);
        stopRenderLoop(playback);
        audio.onToast('\u26A0 visualizer render failed');
        return;
      }
      playback.renderFrame = global.requestAnimationFrame(render);
    }());
  }

  function recoverVisualizer(audio, playback) {
    try {
      createVisualizer(audio, playback);
      if (!playback.lastGoodPreset) throw new Error('no known-good preset available');
      audio.visualizer.loadPreset(playback.lastGoodPreset, playback.lastGoodBlend);
      startRenderLoop(audio, playback, false);
      console.info('WebGL context restored:', playback.lastGoodName);
    } catch (error) {
      console.error('WebGL context recovery failed:', error);
      stopRenderLoop(playback);
      audio.onToast('\u26A0 WebGL recovery failed');
    }
  }

  async function startAudio(audio, playback, deviceId) {
    if (audio.started || audio.starting) return;
    if (!audio.Butterchurn) {
      audio.onToast('\u26A0 butterchurn failed to load');
      throw new Error('butterchurn library not loaded');
    }
    audio.starting = true;
    try {
      await initializeAudio(audio, playback, deviceId);
      audio.started = true;
      startRenderLoop(audio, playback, false);
    } catch (error) {
      stopRenderLoop(playback);
      if (audio.audioCtx) { audio.audioCtx.close(); audio.audioCtx = null; }
      throw error;
    } finally {
      audio.starting = false;
    }
  }

  function createAudioController(canvas, opts, onToast) {
    return {
      canvas: canvas,
      opts: opts,
      Butterchurn: getLib('butterchurn'),
      onToast: onToast,
      audioCtx: null,
      visualizer: null,
      micStream: null,
      sourceNode: null,
      inputDevices: [],
      deviceIdx: 0,
      deviceRequestSeq: 0,
      started: false,
      starting: false,
      prepared: false,
      experimentalImagesReady: false,
      experimentalImagesLoading: null,
    };
  }

  function create(canvas, opts) {
    opts = opts || {};
    const onToast = opts.onToast || function () {};
    const onPreset = opts.onPreset || function () {};
    let playback;
    const store = createPresetStore(opts, function () { return playback.idx; });
    playback = createPlaybackController(store, opts, onToast, onPreset, canvas);
    const audio = createAudioController(canvas, opts, onToast);
    global.addEventListener('resize', function () { sizeCanvas(audio); });
    canvas.addEventListener('webglcontextlost', function (event) {
      event.preventDefault();
      stopRenderLoop(playback);
      console.warn('WebGL context lost');
    });
    canvas.addEventListener('webglcontextrestored', function () {
      if (audio.started) recoverVisualizer(audio, playback);
    });
    sizeCanvas(audio);

    return {
      start: function (deviceId) { return startAudio(audio, playback, deviceId); },
      prepare: function () { return prepareAudio(audio, playback); },
      next: function () { loadPreset(playback, stepIndex(playback, 1)); restartCycle(playback); },
      prev: function () { loadPreset(playback, stepIndex(playback, -1)); restartCycle(playback); },
      random: function () { loadRandom(playback); restartCycle(playback); },
      goto: function (index, announce) { loadPreset(playback, index, undefined, announce); restartCycle(playback); },
      toggleCycle: function () {
        playback.cycleOn = !playback.cycleOn;
        restartCycle(playback);
        return playback.cycleOn;
      },
      toggleShuffle: function () { playback.shuffleOn = !playback.shuffleOn; return playback.shuffleOn; },
      isShuffling: function () { return playback.shuffleOn; },
      removeCurrentFromShuffle: function () { return removeCurrent(playback); },
      excludedList: function () { return Array.from(playback.excluded); },
      setCycleSecs: function (seconds) {
        playback.cycleSecs = Math.max(3, seconds | 0);
        restartCycle(playback);
        return playback.cycleSecs;
      },
      getCycleSecs: function () { return playback.cycleSecs; },
      isCycling: function () { return playback.cycleOn; },
      nextDevice: function () { return useDevice(audio, audio.deviceIdx + 1); },
      useDevice: function (index) { return useDevice(audio, index); },
      useDeviceById: function (id) { return useDeviceById(audio, id); },
      getDevices: function () { return getDevices(audio); },
      listDevices: function () { return audio.inputDevices.slice(); },
      keys: function () { return store.keys.slice(); },
      currentIndex: function () { return playback.idx; },
      currentName: function () { return store.keys[playback.idx] || ''; },
      isStarted: function () { return audio.started; },
      resize: function () { sizeCanvas(audio); },
    };
  }

  global.BCViz = { create: create };
})(window);
