/* device-errors.js - shared wording for getUserMedia failures.
 *
 * Turns a getUserMedia error into a short, actionable hint keyed on name, so
 * "Could not start audio source" points at the fix instead of just the
 * symptom. Loaded as a classic script by obs.html and fullscreen.html, which
 * both report device errors through a single line of status text.
 *
 * Exposes a single global: window.BCDeviceErrors.
 */
(function (global) {
  'use strict';

  /* Chromium reports an operating-system privacy block and a site or embedder
   * block under the same NotAllowedError name, separated only by this suffix.
   * The two need different fixes, so the hint has to read the message. */
  const SYSTEM_DENIAL_PATTERN = /by system/i;

  const LOCKED_HINT = ' (device may be exclusively locked by another app)';
  const MISSING_HINT = ' (device appears to be unplugged or disabled)';
  const STALE_ID_HINT = ' (device id no longer valid; re-select an input)';
  const SYSTEM_DENIED_HINT = ' (the OS is blocking mic access for this app; allow it in system privacy settings)';
  const PAGE_DENIED_HINT = ' (audio capture was blocked; in OBS use a localhost or https URL source, not a local file)';
  const INSECURE_HINT = ' (audio capture needs a secure origin; serve over http://localhost or https)';

  function hintFor(name, message) {
    if (name === 'NotReadableError' || name === 'AbortError') return LOCKED_HINT;
    if (name === 'NotFoundError') return MISSING_HINT;
    if (name === 'OverconstrainedError') return STALE_ID_HINT;
    if (name === 'SecurityError') return INSECURE_HINT;
    if (name !== 'NotAllowedError') return '';
    return SYSTEM_DENIAL_PATTERN.test(message) ? SYSTEM_DENIED_HINT : PAGE_DENIED_HINT;
  }

  /**
   * Return a one-line description of a getUserMedia failure, with a hint at
   * the fix where the error name identifies one.
   */
  function describe(error) {
    const name = error && error.name;
    const message = (error && error.message) || String(error);
    return (name ? name + ': ' : '') + message + hintFor(name, message);
  }

  global.BCDeviceErrors = { describe: describe };
}(window));
