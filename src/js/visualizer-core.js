/*
 * visualizer-core.js
 * Shared butterchurn controller used by both obs.html and fullscreen.html.
 *
 * Loaded as a classic script (NOT an ES module) so it works from file://
 * without CORS issues. Exposes a single global: window.BCViz.
 *
 * Requires butterchurn + butterchurn-presets to be loaded first.
 *
 * Usage:
 *   const viz = BCViz.create(canvasEl, {
 *     onToast:  (msg)        => {},   // brief status messages
 *     onPreset: (index,name) => {},   // fires whenever the preset changes
 *     cycleSecs: 20,
 *     cycleOn:  true
 *   });
 *   await viz.start();                // needs a user gesture first
 */
(function (global) {
  'use strict';

  function getLib(name) {
    const m = global[name];
    return m && (m.default || m);
  }

  function create(canvas, opts) {
    opts = opts || {};
    const Butterchurn = getLib('butterchurn');
    const onToast = opts.onToast || function () { };
    const onPreset = opts.onPreset || function () { };
    const defaultBlend = opts.blend != null ? opts.blend : 2.7;

    let audioCtx, visualizer, micStream, sourceNode;
    let presets = {}, keys = [], idx = 0;
    let excluded = new Set(); // preset keys removed from rotation for this session
    let cycleOn = opts.cycleOn !== false;
    let shuffleOn = opts.shuffle === true;
    let cycleSecs = opts.cycleSecs || 20;
    let cycleTimer = null;
    let inputDevices = [], deviceIdx = 0;
    let started = false, starting = false;

    // Merge every available preset pack. Packs are optional (a missing
    // script just means fewer presets); on name collisions the earlier
    // pack wins, so add-on packs never override or duplicate base presets.
    ['butterchurnPresets', 'butterchurnPresetsExtra',
      'butterchurnPresetsExtra2', 'butterchurnPresetsMD1'].forEach(function (name) {
        const pack = getLib(name);
        if (!pack || !pack.getPresets) return;
        const packPresets = pack.getPresets();
        Object.keys(packPresets).forEach(function (k) {
          if (!(k in presets)) presets[k] = packPresets[k];
        });
      });
    keys = Object.keys(presets).sort();

    function sizeCanvas() {
      const dpr = global.devicePixelRatio || 1;
      canvas.width = global.innerWidth * dpr;
      canvas.height = global.innerHeight * dpr;
      if (visualizer) visualizer.setRendererSize(canvas.width, canvas.height);
    }

    function loadPreset(i, blend, announce) {
      if (!visualizer || !keys.length) return;
      idx = (i + keys.length) % keys.length;
      visualizer.loadPreset(presets[keys[idx]], blend != null ? blend : defaultBlend);
      onPreset(idx, keys[idx]);
      if (announce !== false) onToast(keys[idx]);
    }

    // Steps from idx in the given direction, skipping excluded presets.
    // Falls back to a plain step if every other preset is excluded, so
    // playback never gets stuck.
    function stepIndex(dir) {
      if (!keys.length) return idx;
      let i = idx;
      for (let n = 0; n < keys.length; n++) {
        i = (i + dir + keys.length) % keys.length;
        if (!excluded.has(keys[i])) return i;
      }
      return (idx + dir + keys.length) % keys.length;
    }

    // Indices eligible for a random pick: everything but the current preset
    // and anything excluded. Falls back to "everything but current" if that
    // would otherwise be empty.
    function candidatePool() {
      let pool = keys.map(function (_, i) { return i; })
        .filter(function (i) { return i !== idx && !excluded.has(keys[i]); });
      if (!pool.length) {
        pool = keys.map(function (_, i) { return i; }).filter(function (i) { return i !== idx; });
      }
      return pool;
    }

    function loadRandom() {
      if (keys.length < 2) return loadPreset(0);
      const pool = candidatePool();
      loadPreset(pool[Math.floor(Math.random() * pool.length)]);
    }

    function restartCycle() {
      if (cycleTimer) clearInterval(cycleTimer);
      if (cycleOn) cycleTimer = setInterval(function () {
        if (shuffleOn) loadRandom(); else loadPreset(stepIndex(1));
      }, cycleSecs * 1000);
    }

    // Excludes the currently playing preset from shuffle/cycle rotation for
    // the rest of this session (in-memory only) and advances off it.
    function removeCurrentFromShuffle() {
      if (!keys.length) return null;
      const removed = keys[idx];
      excluded.add(removed);
      loadPreset(stepIndex(1));
      return removed;
    }

    async function getDevices() {
      try {
        const all = await navigator.mediaDevices.enumerateDevices();
        inputDevices = all.filter(function (d) { return d.kind === 'audioinput'; });
      } catch (e) {
        inputDevices = [];
      }
      return inputDevices;
    }

    function connectStream(stream) {
      if (micStream && micStream !== stream) {
        micStream.getTracks().forEach(function (t) { t.stop(); });
      }
      if (sourceNode) visualizer.disconnectAudio(sourceNode);
      micStream = stream;
      sourceNode = audioCtx.createMediaStreamSource(stream);
      visualizer.connectAudio(sourceNode);
    }

    async function openStream(deviceId) {
      const audio = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };
      if (deviceId) audio.deviceId = { exact: deviceId };
      return navigator.mediaDevices.getUserMedia({ audio: audio });
    }

    async function useDevice(i) {
      if (!inputDevices.length) await getDevices();
      if (!inputDevices.length) return null;
      deviceIdx = (i + inputDevices.length) % inputDevices.length;
      const dev = inputDevices[deviceIdx];
      connectStream(await openStream(dev.deviceId));
      onToast('\uD83C\uDF99 ' + (dev.label || ('Input ' + (deviceIdx + 1))));
      return dev;
    }

    async function useDeviceById(id) {
      if (!inputDevices.length) await getDevices();
      const i = inputDevices.findIndex(function (d) { return d.deviceId === id; });
      if (i >= 0) return useDevice(i);
      return null;
    }

    async function start(deviceId) {
      if (started || starting) return;
      if (!Butterchurn) {
        onToast('\u26A0 butterchurn failed to load');
        throw new Error('butterchurn library not loaded');
      }
      starting = true;
      try {
        audioCtx = new (global.AudioContext || global.webkitAudioContext)();
        await audioCtx.resume();

        const stream = await openStream(deviceId);   // also triggers the permission prompt
        await getDevices();                           // labels populate after permission

        visualizer = Butterchurn.createVisualizer(audioCtx, canvas, {
          width: canvas.width, height: canvas.height, pixelRatio: 1, textureRatio: 1
        });
        const ImagesLib = getLib('butterchurnExtraImages');
        if (ImagesLib && ImagesLib.getImages) {
          // Custom textures used by a handful of presets; optional — presets
          // render without them, just with plainer backgrounds.
          try { visualizer.loadExtraImages(ImagesLib.getImages()); } catch (e) { }
        }
        connectStream(stream);
        started = true;
      } catch (e) {
        // Don't leak an AudioContext per failed attempt \u2014 browsers cap them.
        if (audioCtx) { audioCtx.close(); audioCtx = null; }
        throw e;
      } finally {
        starting = false;
      }

      loadPreset(0, 0, false);
      (function render() { visualizer.render(); requestAnimationFrame(render); })();
      restartCycle();
    }

    global.addEventListener('resize', sizeCanvas);
    sizeCanvas();

    return {
      start: start,
      next: function () { loadPreset(stepIndex(1)); },
      prev: function () { loadPreset(stepIndex(-1)); },
      random: loadRandom,
      goto: function (i, announce) { loadPreset(i, undefined, announce); },
      toggleCycle: function () { cycleOn = !cycleOn; restartCycle(); return cycleOn; },
      toggleShuffle: function () { shuffleOn = !shuffleOn; return shuffleOn; },
      isShuffling: function () { return shuffleOn; },
      removeCurrentFromShuffle: removeCurrentFromShuffle,
      excludedList: function () { return Array.from(excluded); },
      setCycleSecs: function (s) {
        cycleSecs = Math.max(3, s | 0); restartCycle(); return cycleSecs;
      },
      getCycleSecs: function () { return cycleSecs; },
      isCycling: function () { return cycleOn; },
      nextDevice: function () { return useDevice(deviceIdx + 1); },
      useDevice: useDevice,
      useDeviceById: useDeviceById,
      getDevices: getDevices,
      listDevices: function () { return inputDevices.slice(); },
      keys: function () { return keys.slice(); },
      currentIndex: function () { return idx; },
      currentName: function () { return keys[idx] || ''; },
      isStarted: function () { return started; },
      resize: sizeCanvas
    };
  }

  global.BCViz = { create: create };
})(window);
