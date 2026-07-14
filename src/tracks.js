/*
 * tracks.js — DJ set playlist for the visualizer.
 *
 * This is a JS file (not a plain .json) on purpose: fetch() of local JSON
 * is blocked under file:// (see AGENTS.md "Gotchas"), the same reason
 * src/presets-extra/ ships as injected <script> chunks instead of fetched
 * JSON. Assigning to window.BCTracks here keeps track config editable by
 * hand while working identically from file://, a local dev server, and
 * the hosted Cloudflare Pages deployment.
 *
 * Each entry:
 *   { "title": "Human-readable set name", "url": "https://media.1a2n.net/..." }
 *
 * The CDN origin serving these URLs MUST send CORS headers
 * (Access-Control-Allow-Origin) — see docs/audio-routing.md — or the
 * visualizer will play the audio silently without ever reacting to it.
 */
window.BCTracks = [
  // { "title": "Example Set", "url": "https://media.1a2n.net/sets/example.mp3" }
];
