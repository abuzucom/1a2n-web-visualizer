/* Visibility-resilient frame scheduler.
 *
 * Chromium does not throttle requestAnimationFrame for a hidden document, it
 * stops delivering it. Native window-occlusion tracking marks a fully covered
 * or minimized window hidden too, so an unfocused visualizer window freezes.
 * This driver keeps frames coming by switching tick sources:
 *
 *   visible -> requestAnimationFrame
 *   hidden  -> AudioWorklet port messages (audio thread, not timer-throttled)
 *   hidden, no worklet -> setTimeout (throttled to about 1 fps, but not frozen)
 *
 * Exactly one source is ever live. A generation counter invalidates callbacks
 * already queued against a superseded source, so a stale frame or timer can
 * never double-render.
 */
(function (global) {
  'use strict';

  const FALLBACK_TICK_MS = 16;
  const TICK_HZ = 60;
  const FPS_WINDOW_MS = 1000;
  const DEFAULT_WORKLET_URL = 'js/render-tick-processor.js';

  function logOnce(state, key, error) {
    if (state.logged[key]) return;
    state.logged[key] = true;
    console.warn('Render driver: ' + key, error);
  }

  function isHidden(state) {
    const doc = state.doc;
    if (!doc) return false;
    if (typeof doc.visibilityState === 'string') return doc.visibilityState === 'hidden';
    return Boolean(doc.hidden);
  }

  function recordTick(state) {
    const now = Date.now();
    const elapsed = now - state.fpsWindowStart;
    if (elapsed >= FPS_WINDOW_MS) {
      state.fps = Math.round((state.fpsWindowFrames * 1000) / elapsed);
      state.fpsWindowStart = now;
      state.fpsWindowFrames = 0;
    }
    state.fpsWindowFrames += 1;
    state.frames += 1;
    state.lastTickAt = now;
    state.onTick();
  }

  /** Retire the active tick source. Queued callbacks fail the generation check. */
  function stopTickSources(state) {
    state.generation += 1;
    if (state.frameHandle !== null) {
      state.win.cancelAnimationFrame(state.frameHandle);
      state.frameHandle = null;
    }
    if (state.timeoutHandle !== null) {
      state.win.clearTimeout(state.timeoutHandle);
      state.timeoutHandle = null;
    }
    state.source = 'idle';
  }

  function startRaf(state) {
    state.source = 'raf';
    state.generation += 1;
    const generation = state.generation;
    function frame() {
      if (!state.running || generation !== state.generation) return;
      recordTick(state);
      state.frameHandle = state.win.requestAnimationFrame(frame);
    }
    state.frameHandle = state.win.requestAnimationFrame(frame);
  }

  function startTimeoutTicks(state) {
    state.source = 'timeout';
    state.generation += 1;
    const generation = state.generation;
    function tick() {
      if (!state.running || generation !== state.generation) return;
      recordTick(state);
      state.timeoutHandle = state.win.setTimeout(tick, FALLBACK_TICK_MS);
    }
    state.timeoutHandle = state.win.setTimeout(tick, FALLBACK_TICK_MS);
  }

  function startWorklet(state, node) {
    if (state.timeoutHandle !== null) {
      state.win.clearTimeout(state.timeoutHandle);
      state.timeoutHandle = null;
    }
    state.source = 'worklet';
    state.generation += 1;
    const generation = state.generation;
    node.port.onmessage = function () {
      if (!state.running || generation !== state.generation) return;
      recordTick(state);
    };
  }

  function buildWorkletNode(state, ctx) {
    const NodeCtor = state.win.AudioWorkletNode;
    const node = new NodeCtor(ctx, 'bc-render-tick', {
      numberOfInputs: 0,
      outputChannelCount: [1],
      processorOptions: { tickHz: TICK_HZ },
    });
    node.connect(ctx.destination);
    state.workletNode = node;
    return node;
  }

  /** Resolve the worklet tick node, or null when this environment cannot host
   * one (opaque file:// origin, missing AudioWorklet, blocked module fetch). */
  function ensureWorklet(state) {
    const ctx = state.audioCtx;
    if (!ctx || state.workletFailed) return Promise.resolve(null);
    if (state.workletContext !== ctx) {
      state.workletContext = ctx;
      state.workletNode = null;
      state.workletPending = null;
    }
    if (state.workletNode) return Promise.resolve(state.workletNode);
    if (state.workletPending) return state.workletPending;
    const hasWorklet = ctx.audioWorklet && typeof ctx.audioWorklet.addModule === 'function';
    if (!hasWorklet || typeof state.win.AudioWorkletNode !== 'function') {
      state.workletFailed = true;
      return Promise.resolve(null);
    }
    state.workletPending = ctx.audioWorklet.addModule(state.workletUrl).then(function () {
      return buildWorkletNode(state, ctx);
    }).catch(function (error) {
      state.workletFailed = true;
      logOnce(state, 'audio worklet tick unavailable, falling back to timers', error);
      return null;
    });
    return state.workletPending;
  }

  /* Bridge on timers immediately so hiding never leaves a gap, then upgrade to
   * the worklet once its module has loaded. */
  function startFallback(state) {
    startTimeoutTicks(state);
    ensureWorklet(state).then(function (node) {
      if (!node || !state.running || !state.hidden) return;
      startWorklet(state, node);
    });
  }

  function acquireWakeLock(state) {
    const nav = state.nav;
    const held = state.wakeLock && !state.wakeLock.released;
    if (held || !nav || !nav.wakeLock || typeof nav.wakeLock.request !== 'function') return;
    nav.wakeLock.request('screen').then(function (lock) {
      state.wakeLock = lock;
      if (!state.running) releaseWakeLock(state);
    }).catch(function (error) {
      // Insecure contexts (file://) and some embedded builds reject outright.
      // Rendering must continue without a lock.
      logOnce(state, 'screen wake lock unavailable', error);
    });
  }

  function releaseWakeLock(state) {
    const lock = state.wakeLock;
    state.wakeLock = null;
    if (!lock || typeof lock.release !== 'function') return;
    try {
      const released = lock.release();
      if (released && typeof released.catch === 'function') {
        released.catch(function (error) { logOnce(state, 'wake lock release failed', error); });
      }
    } catch (error) {
      logOnce(state, 'wake lock release threw', error);
    }
  }

  function handleVisibilityChange(state) {
    state.hidden = isHidden(state);
    if (!state.running) return;
    stopTickSources(state);
    if (state.hidden) {
      startFallback(state);
      return;
    }
    // Chromium auto-releases a screen lock on hide and refuses a new one until
    // the document is visible again, so re-request on the way back.
    acquireWakeLock(state);
    startRaf(state);
  }

  function createState(opts) {
    const win = opts.window || global;
    return {
      win: win,
      doc: opts.document || win.document,
      nav: opts.navigator || win.navigator,
      onTick: typeof opts.onTick === 'function' ? opts.onTick : function () {},
      workletUrl: opts.workletUrl || DEFAULT_WORKLET_URL,
      running: false,
      hidden: false,
      source: 'idle',
      generation: 0,
      frames: 0,
      fps: 0,
      fpsWindowStart: Date.now(),
      fpsWindowFrames: 0,
      lastTickAt: 0,
      audioCtx: null,
      frameHandle: null,
      timeoutHandle: null,
      workletNode: null,
      workletContext: null,
      workletPending: null,
      workletFailed: false,
      wakeLock: null,
      logged: {},
    };
  }

  /* Drop the cached node along with disconnecting it. A disconnected node is
   * no longer pulled by the graph, so its process() never runs and it posts no
   * ticks. Keeping it cached would make a later start() hand that dead node
   * back out of ensureWorklet and leave the hidden page with no tick source. */
  function releaseWorkletNode(state) {
    const node = state.workletNode;
    state.workletNode = null;
    state.workletPending = null;
    state.workletContext = null;
    if (!node) return;
    if (node.port) node.port.onmessage = null;
    try {
      node.disconnect();
    } catch (error) {
      logOnce(state, 'worklet node disconnect failed', error);
    }
  }

  function create(options) {
    const state = createState(options || {});
    if (state.doc && typeof state.doc.addEventListener === 'function') {
      state.doc.addEventListener('visibilitychange', function () { handleVisibilityChange(state); });
    }
    return {
      start: function (audioCtx) {
        if (audioCtx) state.audioCtx = audioCtx;
        if (state.running) return;
        state.running = true;
        state.hidden = isHidden(state);
        acquireWakeLock(state);
        if (state.hidden) startFallback(state);
        else startRaf(state);
      },
      stop: function () {
        state.running = false;
        stopTickSources(state);
        releaseWorkletNode(state);
        releaseWakeLock(state);
      },
      isRunning: function () { return state.running; },
      stats: function () {
        return {
          tickSource: state.source,
          fps: state.fps,
          hidden: state.hidden,
          frames: state.frames,
          lastTickAt: state.lastTickAt,
          wakeLock: Boolean(state.wakeLock && !state.wakeLock.released),
        };
      },
    };
  }

  global.BCRenderDriver = { create: create };
}(window));
