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
    new Function('a', source + '\nreturn a;');
  }

  /** Terminate a non-empty equation so butterchurn's space-separated
   * "src return a;" compile parses it. Idempotent. */
  function normalizeEquation(source) {
    if (!source || source.slice(-1) === '\n') return source;
    return source + '\n';
  }

  /** Normalize all equation strings on a preset in place. Empty strings
   * stay empty; butterchurn shallow-copies presets so mutation is safe. */
  function normalizePresetEquations(preset) {
    ['init_eqs_str', 'frame_eqs_str', 'pixel_eqs_str'].forEach(function (field) {
      if (typeof preset[field] === 'string') preset[field] = normalizeEquation(preset[field]);
    });
    [preset.shapes, preset.waves].forEach(function (items) {
      (items || []).forEach(function (item) {
        ['init_eqs_str', 'frame_eqs_str', 'point_eqs_str'].forEach(function (field) {
          if (typeof item[field] === 'string') item[field] = normalizeEquation(item[field]);
        });
      });
    });
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

  const CHUNK_MAX_RETRIES = 2;
  const CHUNK_RETRY_BASE_MS = 500;

  function requestChunk(state, cid, attempt) {
    const timer = setTimeout(function () { failChunk(state, cid); }, 10000);
    const script = document.createElement('script');
    const filename = state.extraIndex.files && state.extraIndex.files[cid]
      ? state.extraIndex.files[cid]
      : 'chunk-' + String(cid).padStart(3, '0') + '.js';
    script.src = 'presets-extra/' + filename;
    script.onerror = function () {
      clearTimeout(timer);
      if (script.parentNode) script.parentNode.removeChild(script);
      // A load failure (e.g. transient 503 from the CDN) is retried with
      // backoff before the chunk is given up on as permanently missing.
      if (attempt < CHUNK_MAX_RETRIES) {
        setTimeout(function () {
          if (state.status[cid] === 'loading') requestChunk(state, cid, attempt + 1);
        }, CHUNK_RETRY_BASE_MS * Math.pow(2, attempt));
        return;
      }
      failChunk(state, cid);
    };
    script.onload = function () { clearTimeout(timer); failChunk(state, cid); };
    state.scripts[cid] = script;
    document.head.appendChild(script);
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
      requestChunk(state, cid, 0);
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
      normalizePresetEquations(preset);
      validatePresetEquations(preset);
      if (controller.linkGuard) controller.linkGuard.failures.length = 0;
      controller.visualizer.loadPreset(preset, effectiveBlend);
      if (controller.linkGuard && controller.linkGuard.failures.length) {
        throw new Error('shader program link failed: ' + controller.linkGuard.failures.join('; '));
      }
    } catch (error) {
      const linkFailed = Boolean(controller.linkGuard && controller.linkGuard.failures.length);
      controller.store.failed.add(name);
      controller.excluded.add(name);
      console.warn('Preset load failed; skipping:', {
        name: name,
        logicalChunk: cid,
        mode: controller.navigationMode,
        error: error,
      });
      // Restore without blending after a link failure: blending keeps the
      // broken program on screen as the previous shader for the whole blend.
      restoreLastGood(controller, linkFailed ? 0 : undefined);
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

  function restoreLastGood(controller, blendOverride) {
    if (!controller.lastGoodPreset) return false;
    const blend = blendOverride != null ? blendOverride : controller.lastGoodBlend;
    try {
      controller.visualizer.loadPreset(controller.lastGoodPreset, blend);
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
    controller.pendingChunkLoads++;
    const ready = controller.ensureExperimentalImages
      ? controller.ensureExperimentalImages()
      : Promise.resolve();
    ready.then(function () {
      return ensureChunk(controller.store.state, controller.store.state.extraChunkOf[name]);
    }).then(function (ok) {
      controller.pendingChunkLoads--;
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

  function favoriteCurrent(controller) {
    if (!controller.store.keys.length) return null;
    const name = controller.store.keys[controller.idx];
    controller.favorites.add(name);
    return name;
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
      favorites: new Set(),
      loadSeq: 0,
      cycleOn: opts.cycleOn !== false,
      shuffleOn: opts.shuffle === true,
      cycleSecs: opts.cycleSecs || 20,
      cycleTimer: null,
      navigationMode: 'sequential',
      linkGuard: null,
      lastGoodPreset: null,
      lastGoodBlend: 0,
      lastGoodName: '',
      driver: null,
      rendering: false,
      pendingChunkLoads: 0,
    };
  }

  function stopRenderLoop(controller) {
    controller.rendering = false;
    if (controller.driver) controller.driver.stop();
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

  function currentTrack(audio) {
    const stream = audio.micStream;
    if (!stream) return null;
    const tracks = typeof stream.getAudioTracks === 'function'
      ? stream.getAudioTracks() : stream.getTracks();
    return tracks[0] || null;
  }

  function currentDeviceLabel(audio) {
    const track = currentTrack(audio);
    if (track && track.label) return track.label;
    const device = audio.inputDevices[audio.deviceIdx];
    return device ? (device.label || '') : '';
  }

  function currentDeviceId(audio) {
    const device = audio.inputDevices[audio.deviceIdx];
    return device ? device.deviceId : '';
  }

  function connectStream(audio, stream) {
    if (audio.micStream && audio.micStream !== stream) {
      audio.micStream.getTracks().forEach(function (track) { track.stop(); });
    }
    if (audio.sourceNode) audio.visualizer.disconnectAudio(audio.sourceNode);
    audio.micStream = stream;
    audio.hadStream = true;
    audio.sourceNode = audio.audioCtx.createMediaStreamSource(stream);
    audio.visualizer.connectAudio(audio.sourceNode);
    // The keepalive must go quiet whenever the input becomes a loopback device,
    // otherwise its tone is captured straight back into the analysis graph.
    if (audio.keepalive) audio.keepalive.setInputLabel(currentDeviceLabel(audio));
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

  function applyExtraImages(audio, images) {
    try {
      audio.visualizer.loadExtraImages(images);
    } catch (error) {
      console.warn('Failed to load extra images (non-critical):', error);
    }
  }

  function loadExtraImages(audio) {
    const library = getLib('butterchurnExtraImages');
    if (library && library.getImages) applyExtraImages(audio, library.getImages());
  }

  function injectImagePart(number) {
    return new Promise(function (resolve) {
      const script = document.createElement('script');
      script.src = 'vendor/butterchurnExtraImagesExp-part-' + number + '.js';
      script.onerror = function () { resolve(false); };
      script.onload = function () { resolve(true); };
      document.head.appendChild(script);
    });
  }

  /** Load the experimental texture parts lazily, feeding each payload to
   * butterchurn as it arrives so no single parse blocks the render loop.
   * Missing parts resolve rather than reject: textures are non-critical. */
  function ensureExperimentalImages(audio) {
    if (audio.experimentalImagesLoading) return audio.experimentalImagesLoading;
    const legacy = getLib('butterchurnExtraImagesExp');
    if (legacy && legacy.getImages) {
      audio.experimentalImagesLoading = Promise.resolve().then(function () {
        applyExtraImages(audio, legacy.getImages());
      });
      return audio.experimentalImagesLoading;
    }
    audio.experimentalImagesLoading = new Promise(function (resolve) {
      let total = null;
      let received = 0;
      global.__bcExtraImagesExpPart = function (number, count, images) {
        total = count;
        received += 1;
        applyExtraImages(audio, images);
        if (received >= total) resolve();
      };
      (function loadNext(number) {
        injectImagePart(number).then(function (loaded) {
          if (!loaded) return resolve();
          if (total == null || number + 1 < total) loadNext(number + 1);
        });
      })(0);
    });
    return audio.experimentalImagesLoading;
  }

  function scheduleImagePrefetch(audio) {
    const prefetch = function () { ensureExperimentalImages(audio); };
    if (typeof global.requestIdleCallback === 'function') {
      global.requestIdleCallback(prefetch, { timeout: 15000 });
    } else {
      setTimeout(prefetch, 5000);
    }
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
    if (!loadInitialPreset(audio, playback, true)) {
      audio.audioCtx.close();
      audio.audioCtx = null;
      throw new Error('no valid preset could be loaded');
    }
    audio.prepared = true;
  }

  /** Wrap gl.linkProgram to record link failures per program; butterchurn
   * never checks LINK_STATUS itself, so unlinked shaders otherwise render
   * broken frames while the browser floods the console with GL errors. */
  function installLinkGuard(canvas) {
    const gl = canvas.getContext ? canvas.getContext('webgl2') : null;
    if (!gl || typeof gl.linkProgram !== 'function') return { failures: [] };
    if (gl.__bcLinkGuard) return gl.__bcLinkGuard;
    const guard = { failures: [] };
    const nativeLinkProgram = gl.linkProgram;
    gl.linkProgram = function (program) {
      nativeLinkProgram.call(gl, program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        guard.failures.push(typeof gl.getProgramInfoLog === 'function'
          ? gl.getProgramInfoLog(program) : 'shader program link failed');
      }
    };
    gl.__bcLinkGuard = guard;
    return guard;
  }

  function createVisualizer(audio, playback) {
    audio.visualizer = audio.Butterchurn.createVisualizer(audio.audioCtx, audio.canvas, {
      width: audio.canvas.width, height: audio.canvas.height, pixelRatio: 1, textureRatio: 1,
    });
    playback.visualizer = audio.visualizer;
    playback.linkGuard = installLinkGuard(audio.canvas);
    playback.ensureExperimentalImages = function () { return ensureExperimentalImages(audio); };
    loadExtraImages(audio);
    scheduleImagePrefetch(audio);
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
    playback.driver.start(audio.audioCtx);
    restartCycle(playback);
  }

  /** One frame, called by whichever tick source the render driver has live. */
  function renderOnce(audio, playback) {
    if (!playback.rendering) return;
    try {
      audio.visualizer.render();
    } catch (error) {
      console.error('Visualizer render failed:', error);
      stopRenderLoop(playback);
      audio.onToast('\u26A0 visualizer render failed');
    }
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
      audio.keepalive.setInputLabel(currentDeviceLabel(audio));
      audio.keepalive.start();
      audio.watchdog.start();
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
      hadStream: false,
      keepalive: null,
      watchdog: null,
      experimentalImagesLoading: null,
    };
  }

  function createRenderDriver(audio, playback) {
    return global.BCRenderDriver.create({
      window: global,
      document: document,
      navigator: navigator,
      workletUrl: 'js/render-tick-processor.js',
      onTick: function () { renderOnce(audio, playback); },
    });
  }

  function createWatchdog(audio, playback) {
    return global.BCWatchdog.create({
      window: global,
      getDriverStats: function () { return playback.driver.stats(); },
      restartDriver: function () { if (audio.started) startRenderLoop(audio, playback, false); },
      recoverVisualizer: function () { if (audio.started) recoverVisualizer(audio, playback); },
      getAudioContext: function () { return audio.audioCtx; },
      getTrack: function () { return currentTrack(audio); },
      // Without a stream there is no input to lose, so do not report one gone.
      isMonitoring: function () { return audio.hadStream; },
      getDeviceId: function () { return currentDeviceId(audio); },
      getDeviceLabel: function () { return currentDeviceLabel(audio); },
      listDevices: function () { return getDevices(audio); },
      reconnect: function (deviceId) { return useDeviceById(audio, deviceId); },
      onToast: audio.onToast,
    });
  }

  function collectDiagnostics(audio, playback) {
    const driver = playback.driver.stats();
    const keepalive = audio.keepalive.stats();
    const watchdog = audio.watchdog.stats();
    const track = currentTrack(audio);
    return {
      fps: driver.fps,
      tickSource: driver.tickSource,
      hidden: driver.hidden,
      wakeLock: driver.wakeLock,
      frames: driver.frames,
      keepalive: keepalive.active ? 'active' : (keepalive.reason || 'off'),
      device: currentDeviceLabel(audio) || 'none',
      trackState: track ? (track.muted ? 'muted' : track.readyState) : 'none',
      armed: watchdog.armed,
      audioLost: watchdog.audioLost,
      recoverInSecs: watchdog.recoverInSecs,
      recoveries: watchdog.recoveries,
      restarts: watchdog.restarts,
      reason: watchdog.reason,
    };
  }

  /* Chromium can suspend the context while the page is hidden, and nothing
   * else ever resumes it: initializeAudio resumes exactly once at startup. */
  function resumeOnVisible(audio) {
    if (document.visibilityState === 'hidden' || !audio.audioCtx) return;
    if (audio.audioCtx.state !== 'suspended') return;
    audio.audioCtx.resume().catch(function (error) {
      console.warn('Audio context resume failed:', error);
    });
  }

  function attachLifecycle(audio, playback, canvas) {
    global.addEventListener('resize', function () { sizeCanvas(audio); });
    if (document.addEventListener) {
      document.addEventListener('visibilitychange', function () { resumeOnVisible(audio); });
    }
    canvas.addEventListener('webglcontextlost', function (event) {
      event.preventDefault();
      stopRenderLoop(playback);
      console.warn('WebGL context lost');
    });
    canvas.addEventListener('webglcontextrestored', function () {
      if (audio.started) recoverVisualizer(audio, playback);
    });
  }

  function create(canvas, opts) {
    opts = opts || {};
    const onToast = opts.onToast || function () {};
    const onPreset = opts.onPreset || function () {};
    let playback;
    const store = createPresetStore(opts, function () { return playback.idx; });
    playback = createPlaybackController(store, opts, onToast, onPreset, canvas);
    const audio = createAudioController(canvas, opts, onToast);
    playback.driver = createRenderDriver(audio, playback);
    audio.keepalive = global.BCKeepalive.create({ window: global });
    audio.watchdog = createWatchdog(audio, playback);
    attachLifecycle(audio, playback, canvas);
    sizeCanvas(audio);

    return {
      start: function (deviceId) { return startAudio(audio, playback, deviceId); },
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
      favoriteCurrentPreset: function () { return favoriteCurrent(playback); },
      favoritesList: function () { return Array.from(playback.favorites); },
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
      isChunkLoading: function () { return playback.pendingChunkLoads > 0; },
      resize: function () { sizeCanvas(audio); },
      diagnostics: function () { return collectDiagnostics(audio, playback); },
      toggleAudioGuard: function () { return audio.watchdog.setArmed(!audio.watchdog.isArmed()); },
      setAudioGuard: function (armed) { return audio.watchdog.setArmed(armed); },
      isAudioGuardArmed: function () { return audio.watchdog.isArmed(); },
    };
  }

  global.BCViz = { create: create };
})(window);
