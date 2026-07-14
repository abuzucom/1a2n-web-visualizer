# Audio routing

This fork intentionally diverges from upstream `1a2n-web-visualizer`: instead
of visualizing a **live input device** (microphone, or music routed through a
virtual cable like VB-Cable/VoiceMeeter/BlackHole), it plays a **DJ set
playlist streamed directly from a Cloudflare CDN** and visualizes that stream.
No virtual audio cable, mixer routing, or OS-level loopback is needed or used
— that entire workflow has been removed from this fork.

## Configuring the playlist

Tracks are listed in `src/tracks.js`, a small JS file that assigns
`window.BCTracks` (a `.js` file rather than plain JSON so it also works from
`file://` — see AGENTS.md's "Gotchas"). Each entry is:

```js
{ "title": "Human-readable set name", "url": "https://media.1a2n.net/sets/example.mp3" }
```

Upload your DJ sets to your Cloudflare-backed origin (e.g. an R2 bucket
fronted by Cloudflare, or Cloudflare Stream), then add one entry per track
here with its public URL.

## Required: CORS headers on the CDN origin

The `<audio>` element loads tracks with `crossOrigin="anonymous"` so the
visualizer's analyser node can read audio samples from a cross-origin URL.
Per the Web Audio API spec, if the response is missing a matching
`Access-Control-Allow-Origin` header, the audio graph is marked **tainted**:
playback still works and is audible, but the visualizer receives silent
(zero) sample data and never reacts to the music.

Configure your Cloudflare origin (R2 custom domain, Cloudflare Stream, Pages,
Worker, etc.) to send:

```
Access-Control-Allow-Origin: https://visualizer.1a2n.net
```

(or `*` if the audio files are not sensitive) on responses for the audio
files referenced in `src/tracks.js`.

## Controls

Playback is controlled entirely from the fullscreen keyboard UI:

| Key | Action |
| --- | --- |
| <kbd>A</kbd> | Previous track |
| <kbd>D</kbd> | Next track |
| <kbd>K</kbd> | Play / pause the current track |

Tracks advance automatically to the next playlist entry when one finishes.

## Troubleshooting

- **Visualizer stays flat/reactionless even though audio plays:** the CDN
  origin is missing the CORS header above — the audio graph is tainted.
- **"playback blocked" toast:** browsers require a user gesture (a click or
  keypress) before audio can play; this fires automatically from the
  fullscreen build's start-on-first-interaction behavior.
- **"no tracks configured" toast:** `src/tracks.js` has an empty
  `window.BCTracks` array — add at least one track entry.
