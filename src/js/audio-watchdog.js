/* Unattended-operation watchdog.
 *
 * Two groups of checks, split by whether a check can disrupt a live set.
 *
 * Always on, because none of it can change what is being captured:
 *   - a stalled render loop is restarted, then escalated to a full visualizer
 *     recovery if restarts do not take
 *   - a suspended AudioContext is resumed
 *
 * Opt-in and disarmed at startup, because it can swap the capture device:
 *   - a lost input is reconnected, after a grace window, preferring Voicemeeter
 *
 * The guard starts disarmed because a stream opens with dead air before the
 * first track drops, and nothing should be second-guessing the input then. The
 * operator arms it once the set is running. While disarmed the loss is still
 * detected and reported, it just is not acted on.
 */
(function (global) {
  'use strict';

  const CHECK_INTERVAL_MS = 2000;
  const TRACK_LOSS_GRACE_MS = 20000;
  const STALL_MS = 5000;
  const RESTART_BACKOFF_BASE_MS = 10000;
  const RESTART_BACKOFF_MAX_MS = 120000;
  const ESCALATE_AFTER_RESTARTS = 3;
  const RECOVERY_RETRY_MS = 10000;

  const VOICEMEETER_PATTERN = /voicemeeter/i;
  const VB_AUDIO_PATTERN = /vb-?(audio|cable)/i;
  const DEFAULT_PATTERN = /^default\b/i;

  function labelsOverlap(left, right) {
    if (!left || !right) return false;
    const a = left.toLowerCase();
    const b = right.toLowerCase();
    return a.indexOf(b) >= 0 || b.indexOf(a) >= 0;
  }

  /* Lower rank wins. Anything unranked is never selected: after a device loss
   * the visualizer must go quiet rather than start capturing the room through
   * a built-in microphone. */
  function rankDevice(device, previous) {
    const label = device.label || '';
    if (previous.deviceId && device.deviceId === previous.deviceId) return 0;
    if (VOICEMEETER_PATTERN.test(label)) return 1;
    if (VB_AUDIO_PATTERN.test(label)) return 2;
    if (labelsOverlap(label, previous.label)) return 3;
    if (DEFAULT_PATTERN.test(label) || device.deviceId === 'default') return 4;
    return Infinity;
  }

  /* A Voicemeeter restart usually hands the device back under a new deviceId
   * with the same label, so label ranking recovers more shows than id match. */
  function selectInputDevice(devices, previous) {
    const list = Array.isArray(devices) ? devices : [];
    const prev = previous || {};
    let best = null;
    let bestRank = Infinity;
    list.forEach(function (device) {
      const rank = rankDevice(device, prev);
      if (rank < bestRank) {
        bestRank = rank;
        best = device;
      }
    });
    return bestRank === Infinity ? null : best;
  }

  /* Only hard signals count as loss. Silence is never one of them: intentional
   * dead air is normal mid-set, and a quiet live track must render a quiet
   * scene rather than trigger a device swap. Do not add an amplitude check. */
  function isTrackLost(track) {
    if (!track) return true;
    if (track.readyState === 'ended') return true;
    return Boolean(track.muted);
  }

  function checkStall(state) {
    const stats = state.getDriverStats() || {};
    const now = state.now();
    if (!stats.lastTickAt || now - stats.lastTickAt <= state.stallMs) {
      if (state.lastRestartAt && now - state.lastRestartAt >= state.restartBackoffMs) {
        state.restartBackoffMs = RESTART_BACKOFF_BASE_MS;
        state.consecutiveRestarts = 0;
      }
      return;
    }
    if (state.lastRestartAt && now - state.lastRestartAt < state.restartBackoffMs) return;
    state.lastRestartAt = now;
    state.restartBackoffMs = Math.min(state.restartBackoffMs * 2, RESTART_BACKOFF_MAX_MS);
    state.consecutiveRestarts += 1;
    state.restarts += 1;
    state.restartDriver();
    if (state.consecutiveRestarts >= ESCALATE_AFTER_RESTARTS) state.recoverVisualizer();
  }

  function checkContext(state) {
    const context = state.getAudioContext();
    if (!context || context.state !== 'suspended' || typeof context.resume !== 'function') return;
    const resumed = context.resume();
    if (resumed && typeof resumed.catch === 'function') {
      resumed.catch(function (error) {
        console.warn('Watchdog: could not resume the audio context', error);
      });
    }
  }

  function graceStart(state) {
    return Math.max(state.lossSince || 0, state.armedAt || 0);
  }

  function reconnectBest(state, devices) {
    const previous = { deviceId: state.getDeviceId(), label: state.getDeviceLabel() };
    const device = selectInputDevice(devices, previous);
    if (!device) {
      state.lastReason = 'no usable audio input found';
      state.onToast('⚠ no usable audio input found');
      return null;
    }
    state.recoveries += 1;
    state.lastReason = 'reconnected to ' + (device.label || device.deviceId);
    return state.reconnect(device.deviceId);
  }

  function recoverInput(state) {
    state.recovering = true;
    state.lastRecoveryAt = state.now();
    Promise.resolve(state.listDevices()).then(function (devices) {
      return reconnectBest(state, devices);
    }).catch(function (error) {
      state.lastReason = 'reconnect failed';
      console.warn('Watchdog: input recovery failed', error);
    }).then(function () {
      state.recovering = false;
    });
  }

  function noteLoss(state) {
    if (state.lossSince) return;
    state.lossSince = state.now();
    state.lastReason = 'audio input lost';
    state.onToast('⚠ audio input lost');
  }

  function checkInput(state) {
    if (!state.isMonitoring()) {
      state.lossSince = null;
      return;
    }
    if (!isTrackLost(state.getTrack())) {
      state.lossSince = null;
      return;
    }
    noteLoss(state);
    if (!state.armed || state.recovering) return;
    const now = state.now();
    if (now - graceStart(state) < state.graceMs) return;
    if (state.lastRecoveryAt && now - state.lastRecoveryAt < RECOVERY_RETRY_MS) return;
    recoverInput(state);
  }

  function sweep(state) {
    if (!state.started) return;
    checkStall(state);
    checkContext(state);
    checkInput(state);
  }

  function remainingSecs(state) {
    if (!state.armed || !state.lossSince) return 0;
    const remaining = state.graceMs - (state.now() - graceStart(state));
    return remaining > 0 ? Math.ceil(remaining / 1000) : 0;
  }

  function createState(opts) {
    const win = opts.window || global;
    const noop = function () {};
    return {
      win: win,
      now: typeof opts.now === 'function' ? opts.now : Date.now,
      graceMs: Number(opts.graceMs) > 0 ? Number(opts.graceMs) : TRACK_LOSS_GRACE_MS,
      stallMs: Number(opts.stallMs) > 0 ? Number(opts.stallMs) : STALL_MS,
      checkIntervalMs: Number(opts.checkIntervalMs) > 0 ? Number(opts.checkIntervalMs) : CHECK_INTERVAL_MS,
      getDriverStats: opts.getDriverStats || function () { return {}; },
      restartDriver: opts.restartDriver || noop,
      recoverVisualizer: opts.recoverVisualizer || noop,
      getAudioContext: opts.getAudioContext || function () { return null; },
      getTrack: opts.getTrack || function () { return null; },
      isMonitoring: opts.isMonitoring || function () { return true; },
      getDeviceId: opts.getDeviceId || function () { return ''; },
      getDeviceLabel: opts.getDeviceLabel || function () { return ''; },
      listDevices: opts.listDevices || function () { return Promise.resolve([]); },
      reconnect: opts.reconnect || function () { return Promise.resolve(); },
      onToast: opts.onToast || noop,
      started: false,
      armed: false,
      armedAt: 0,
      timer: null,
      lossSince: null,
      recovering: false,
      lastRecoveryAt: 0,
      lastRestartAt: 0,
      restartBackoffMs: RESTART_BACKOFF_BASE_MS,
      consecutiveRestarts: 0,
      restarts: 0,
      recoveries: 0,
      lastReason: '',
    };
  }

  function create(options) {
    const state = createState(options || {});
    return {
      start: function () {
        if (state.started) return;
        state.started = true;
        state.timer = state.win.setInterval(function () { sweep(state); }, state.checkIntervalMs);
      },
      stop: function () {
        state.started = false;
        if (state.timer !== null) {
          state.win.clearInterval(state.timer);
          state.timer = null;
        }
      },
      setArmed: function (armed) {
        const next = Boolean(armed);
        if (next === state.armed) return state.armed;
        state.armed = next;
        // Arming mid-loss starts the grace window now, not when the loss began,
        // so a stream that opens on a dead input still gets its full window.
        state.armedAt = next ? state.now() : 0;
        return state.armed;
      },
      isArmed: function () { return state.armed; },
      stats: function () {
        return {
          armed: state.armed,
          audioLost: Boolean(state.lossSince),
          recoverInSecs: remainingSecs(state),
          recoveries: state.recoveries,
          restarts: state.restarts,
          reason: state.lastReason,
        };
      },
    };
  }

  global.BCWatchdog = { create: create, selectInputDevice: selectInputDevice };
}(window));
