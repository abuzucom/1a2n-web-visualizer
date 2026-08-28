# Unattended operation

This page is for running the visualizer through a set you are not sitting in
front of: an OBS browser source, or a fullscreen window on a second monitor. It
covers the watchdog, the audio guard, and what to check before you walk away.

For why the page keeps rendering while hidden, see
[background-rendering.md](background-rendering.md).

## Run-book

1. Open the page with the overlay on: add `?diag=1` to the URL, or press
   <kbd>I</kbd> once it is loaded.
2. Start the visualizer and grant the microphone permission. Device labels are
   blank until permission is granted, and the watchdog needs labels to rank
   devices.
3. Confirm the overlay reads `Tick source: worklet` after you cover the window.
   If it reads `timeout`, you are on a `file://` origin. Serve the page over
   HTTP instead.
4. Let the opening dead air pass and drop the first track.
5. **Arm the audio guard.** Press <kbd>A</kbd> on `fullscreen.html` or
   `obs.html`, or tick the "Audio guard" checkbox on `obs.html`.
6. Confirm the overlay's top row reads `ARMED`, then walk away.

Step 5 is the one people forget. The guard starts disarmed on purpose, and a
disarmed guard will not reconnect a lost input.

If you are launching a source that is already mid-set, `?guard=1` arms the guard
at startup and skips steps 4 and 5. Do not use it on a page you open before the
music starts.

## What the watchdog does

A sweep runs every 2 seconds. The checks fall into two groups, split by whether
a check can disrupt a live set.

**Always on**, from the first frame, because neither check can change what is
being captured:

- A render loop with no tick for 5 seconds is restarted. Repeated restarts back
  off from 10 seconds up to 2 minutes, and after 3 consecutive restarts the
  watchdog escalates to a full visualizer recovery.
- An `AudioContext` in the `suspended` state is resumed. Chromium can suspend it
  while the page is hidden, and nothing else ever resumes it.

**Opt-in**, and disarmed at startup, because it can swap the capture device:

- A lost input is reconnected, after a 20 second grace window, preferring
  Voicemeeter.

## Why the guard starts disarmed

A stream opens with dead air before the first track drops. During that window an
armed guard has nothing to distinguish "the operator has not started yet" from
"the input died", and reconnecting then is the wrong move. So the guard does
nothing until you arm it.

While disarmed the watchdog still detects a lost input, reports it in the
overlay, and toasts once. It just takes no action, so you can fix it yourself or
arm the guard and let it recover.

Arming during an in-progress loss starts the 20 second countdown from the moment
you arm, not from when the loss began. A stream that opens on a dead input still
gets its full window.

## Silence is never a fault

The watchdog will not treat quiet audio as a lost input, at any volume, for any
duration. Intentional dead air is normal mid-set, and a quiet live track must
render a quiet scene.

Only hard signals count as loss:

- `track.readyState === 'ended'`
- `track.muted`
- the device disappearing from the device list at reconnect time

There is no RMS check, no FFT energy check, and no amplitude heuristic anywhere
in the loss path. This is deliberate. If you are tempted to add one, the comment
at the trigger site in `src/js/audio-watchdog.js` asks you not to.

## The 20 second grace window

A confirmed loss does not reconnect immediately. The watchdog starts a 20 second
countdown, shown in the overlay as `Reconnect in`, and re-checks at expiry. If
the signal comes back inside the window, the countdown cancels and no reconnect
happens.

That window exists for the flap case. A Voicemeeter restart, a driver reset, or
a device that briefly re-enumerates all look like a loss for a few seconds and
then resolve themselves. Reconnecting through one of those is more disruptive
than waiting it out.

The cost is that a genuine device loss takes about 20 seconds to recover. That
is the intended trade. The countdown is visible in the overlay the whole time,
so if you are watching, you can intervene before it fires.

## Device preference

When the guard does reconnect, candidates are ranked lowest-first:

| Rank | Match |
| --- | --- |
| 0 | the exact previous `deviceId` |
| 1 | a label containing "voicemeeter" |
| 2 | a label matching VB-Audio or VB-Cable |
| 3 | a label overlapping the previous device's label |
| 4 | the system default |
| never | anything else |

Label ranking sits above the previous label on purpose. A Voicemeeter restart
usually hands the device back under a **new** `deviceId` with the **same**
label, so matching on `deviceId` alone would miss it and fall through to
whatever else was on the list.

Anything unranked is never selected. If no candidate matches, the watchdog keeps
the current device, reports `no usable audio input found`, and toasts. It will
not fall back to a built-in microphone, because a visualizer that goes quiet is
recoverable and a stream that starts broadcasting the room is not.

## Exclusive-mode devices (Windows)

Some virtual and pro-audio devices, including Voicemeeter's outputs registered
as Windows recording devices, allow only one open client stream at a time when
Windows' "Allow applications to take exclusive control of this device" is
enabled on that device (a common recommendation for lower latency). If a
second stream tries to open the same device while one is already open, the
browser rejects it with `NotReadableError: Could not start audio source`.

This app always fully releases the current device, stopping its track, before
requesting a new one, specifically to avoid asking for a second stream on a
device it already has open itself. Switching back to the device already active
(guaranteed whenever there is only one input device) is a no-op rather than a
reopen. A single short retry also absorbs a driver that is briefly slow to free
the handle after release.

If you still see `Could not start audio source` when switching inputs, another
app or browser tab has that device open. Either uncheck exclusive mode for the
device in Windows Sound Control Panel -> the device -> Advanced tab, or close
whatever else is holding it, then try again.

## Reading repeated recoveries

The overlay's `Recoveries` counter is the health signal to check when you come
back.

| Symptom | Likely cause |
| --- | --- |
| Recoveries climbing steadily | The input device is flapping. Check the interface connection, or the Voicemeeter engine for repeated restarts. |
| `Recoveries: 0` but a dead scene | The input is live and silent. The watchdog is behaving correctly; the problem is upstream at the mixer. |
| `no usable audio input found` | The preferred device never came back. Reselect the input by hand. |
| "Could not start audio source" / `NotReadableError` | Another app or tab has the device open in exclusive mode. See [Exclusive-mode devices (Windows)](#exclusive-mode-devices-windows) above. |
| `NotAllowedError: Permission denied` | The page is not allowed to capture audio. In OBS, a **Local file** browser source; switch it to **URL** mode. See [obs-setup.md](obs-setup.md). |
| `NotAllowedError: Permission denied by system` | The OS is blocking microphone access for the app. Allow it in the system privacy settings. |
| Restarts climbing, recoveries at 0 | The render loop is stalling, not the audio. Check GPU load and see [background-rendering.md](background-rendering.md). |

A recovery count of 1 or 2 across a long set is unremarkable. A count in the
dozens means the underlying device is unstable and no amount of reconnecting
will fix it.
