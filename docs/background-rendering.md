# Background rendering

The visualizer keeps rendering when its window is not focused, is covered by
another window, is minimized, or sits in a background tab. This page explains
what the browser does to a hidden page, what the app does about it, and the
handful of settings that page JavaScript cannot reach.

## What the browser does

Chromium does not slow `requestAnimationFrame` down for a hidden document. It
stops delivering it altogether. Worse, "hidden" is broader than most people
expect: Chromium tracks native window occlusion, so a window that is fully
covered by another window, or minimized, reports `visibilityState: hidden`
exactly like a background tab does. An unfocused visualizer on a second monitor
is fine as long as you can still see it; the moment something covers it
completely, the render loop stops.

Timers get throttled rather than stopped. A hidden page's `setTimeout` and
`setInterval` are held to roughly one call per second, and after five minutes
Chromium applies "intensive throttling" and drops that to about one per minute.
Pages that are playing audio, and pages holding a live microphone capture, are
exempt from parts of this.

Opera is Chromium underneath, so all of the above applies, plus its own tab
snoozing and battery saver on top.

## What the app does

Five layers, most important first.

**1. The render driver** (`src/js/render-driver.js`) owns frame scheduling and
swaps its clock based on visibility:

| Page state | Frame clock | Rate |
| --- | --- | --- |
| Visible | `requestAnimationFrame` | display refresh |
| Hidden | AudioWorklet port messages | near display refresh |
| Hidden, no worklet available | `setTimeout` | about 1 fps, or full rate if the tab counts as audible |

The AudioWorklet path is the one that matters. `src/js/render-tick-processor.js`
runs on the audio thread, which visibility throttling does not touch, and posts a
message every frame interval. A port message reaches the main thread as a task
rather than a timer, so hidden-page timer throttling does not apply to it either.

Exactly one clock is ever live. A generation counter invalidates callbacks
already queued against a superseded clock, so a stale frame cannot double-render.

**2. The audible keepalive** (`src/js/audible-keepalive.js`) emits a tone far
below audibility on its own `AudioContext`, which marks the tab audible and
exempts it from timer throttling and from tab discarding. See the feedback guard
below, because this layer disables itself more often than not.

**3. The screen wake lock**, requested by the render driver, stops the display
sleeping under a visible but unfocused visualizer. Chromium releases it
automatically when the page hides and refuses to grant a new one until the page
is visible again, so the driver re-requests it on the way back.

**4. The watchdog** (`src/js/audio-watchdog.js`) restarts a stalled render loop,
resumes a suspended `AudioContext`, and optionally recovers a lost input. See
[unattended-operation.md](unattended-operation.md).

**5. The diagnostics overlay** shows you whether all of the above is working.

## The feedback guard

The keepalive outputs audio. Most setups here capture a loopback or monitor
device, which means anything the page outputs can be captured straight back into
its own analysis input, where it would show up in the FFT the presets react to.

So the keepalive inspects the selected input label and stays silent when it looks
like a loopback: Voicemeeter, VB-Audio, VB-Cable, CABLE Output, Stereo Mix,
"Monitor of ...", BlackHole, Loopback, Soundflower, "What U Hear". An
unidentified input, which is what an ungranted device reports, is treated the
same way. It re-evaluates every time the device changes.

If you route through Voicemeeter, expect the overlay to read
`suppressed: loopback input`. That is correct. You lose the timer-throttling
exemption and keep the AudioWorklet tick, which is the layer doing the real work.

If switching inputs ever reports `Could not start audio source`, see
[Exclusive-mode devices (Windows)](unattended-operation.md#exclusive-mode-devices-windows).

## Reading the overlay

Add `?diag=1` to any page URL, or press <kbd>I</kbd> on `fullscreen.html` and
`obs.html`.

| Row | What it means |
| --- | --- |
| Audio guard | `ARMED` or `DISARMED`. See [unattended-operation.md](unattended-operation.md). |
| Reconnect in | Only while a reconnect countdown is running. |
| FPS | Frames per second, measured over a rolling one-second window. |
| Tick source | `raf`, `worklet`, or `timeout`. |
| Page | `visible` or `hidden`. |
| Wake lock | `held` or `none`. |
| Keepalive | `active`, or why it is not. |
| Input | The capture device label. |
| Track | `live`, `muted`, `ended`, or `none`. |
| Recoveries | How many times the watchdog reconnected the input. |

The check that matters: cover the window completely, wait, then uncover it. Tick
source should read `worklet` and the frame count should have climbed while it was
hidden.

## What the app cannot do for you

**Opera.** Turn off "Snooze inactive tabs" in Settings, and turn off battery
saver. Neither is reachable from a page. A minimized window is treated worse than
a merely covered one, so prefer covering over minimizing.

**Chromium launch flags.** For a dedicated always-on visualizer window, these
remove the throttling at the source:

```
--disable-background-timer-throttling
--disable-backgrounding-occluded-windows
--disable-renderer-backgrounding
```

**OBS browser source.** Uncheck "Shutdown source when not visible" and "Refresh
browser when scene becomes active". Otherwise OBS tears the page down on a scene
change and none of this matters.

**`file://` origins** are opaque, so `audioWorklet.addModule` is rejected and the
wake lock throws. The page still works and still renders while hidden, but on the
`setTimeout` clock at about 1 fps. Serve over `http://` or `https://` to get the
full behavior; see the README "Quick Start".

## Calibrating the keepalive

`KEEPALIVE_GAIN` in `src/js/audible-keepalive.js` is about -56 dBFS. Chromium
decides a tab is audible using a power threshold that is not specified anywhere,
so the value is empirical and needs a real browser to confirm.

1. Select a normal, non-loopback input and start the visualizer.
2. Check that Chromium shows the audio indicator on the tab. That is the proof
   the tab is marked audible.
3. Check that nothing is audible on the output at your normal listening level.
4. If the indicator does not appear, raise `KEEPALIVE_GAIN` one step and repeat
   both checks. Record the final value and the evidence in the constant's
   comment.

Both conditions have to hold. A value that is audible is a bug, whatever it does
for throttling.
