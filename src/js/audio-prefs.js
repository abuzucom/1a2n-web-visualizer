/* audio-prefs.js - remembers the operator's chosen audio input.
 *
 * An OBS browser source is torn down and rebuilt on a scene refresh, and
 * without this the page falls back to the OS default input every time. The
 * label is stored alongside the id because a Voicemeeter restart hands the
 * same device back under a new deviceId.
 *
 * Exposes a single global: window.BCAudioPrefs.
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'bcviz.audioInput.v1';

  /* Reading localStorage throws outright on some file:// and privacy-mode
   * configurations rather than returning null, and losing the saved input is
   * never a reason to fail startup. Every accessor absorbs that. */
  function storage() {
    try {
      return global.localStorage || null;
    } catch (error) {
      console.warn('Audio preferences unavailable; the chosen input will not persist:', error);
      return null;
    }
  }

  function parse(raw) {
    if (!raw) return null;
    let saved;
    try {
      saved = JSON.parse(raw);
    } catch (error) {
      console.warn('Discarding an unreadable saved audio input:', error);
      return null;
    }
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return null;
    if (!saved.deviceId && !saved.label) return null;
    return { deviceId: String(saved.deviceId || ''), label: String(saved.label || '') };
  }

  /**
   * Return the saved audio input as {deviceId, label}, or null when there is
   * none, storage is unavailable, or the stored value is unreadable.
   */
  function read() {
    const store = storage();
    if (!store) return null;
    try {
      return parse(store.getItem(STORAGE_KEY));
    } catch (error) {
      console.warn('Could not read the saved audio input:', error);
      return null;
    }
  }

  /**
   * Persist the chosen audio input. Returns whether it was actually stored.
   */
  function write(deviceId, label) {
    const store = storage();
    if (!store) return false;
    try {
      store.setItem(STORAGE_KEY, JSON.stringify({ deviceId: deviceId || '', label: label || '' }));
      return true;
    } catch (error) {
      console.warn('Could not save the chosen audio input:', error);
      return false;
    }
  }

  /** Forget the saved audio input. */
  function clear() {
    const store = storage();
    if (!store) return;
    try {
      store.removeItem(STORAGE_KEY);
    } catch (error) {
      console.warn('Could not clear the saved audio input:', error);
    }
  }

  function findById(devices, deviceId) {
    if (!deviceId) return null;
    return devices.find(function (device) { return device.deviceId === deviceId; }) || null;
  }

  /* Labels are blank for every device until audio permission is granted, so a
   * blank saved label would otherwise match the first unlabeled entry. */
  function findByLabel(devices, label) {
    if (!label) return null;
    return devices.find(function (device) { return device.label === label; }) || null;
  }

  /**
   * Return the deviceId to request for a saved preference, or an empty string
   * to leave the choice to the operating system default.
   */
  function resolve(devices, saved) {
    const list = Array.isArray(devices) ? devices : [];
    if (!saved) return '';
    const match = findById(list, saved.deviceId) || findByLabel(list, saved.label);
    return match ? match.deviceId : '';
  }

  global.BCAudioPrefs = { read: read, write: write, clear: clear, resolve: resolve };
}(window));
