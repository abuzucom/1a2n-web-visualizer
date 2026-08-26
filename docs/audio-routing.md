# Audio routing

The visualizer reads from an **audio input device**. To make it react to music
(or any system/app audio) rather than your microphone, route that audio into a
virtual input device and select it in the visualizer.

Select the device by pressing <kbd>D</kbd> in the fullscreen build, or via the
dropdown in the OBS panel build.

If you only want to see the visualizer working, none of this is needed:
`demo.html` generates its own track inside the page. Come back here when you
want the presets reacting to real audio.

## Windows

- **VB-Cable** (free): set your music player's / system output to "CABLE Input",
  then select **CABLE Output** in the visualizer.
- **VoiceMeeter** (free): more flexible routing if you also want to keep hearing
  the audio yourself; route a bus to a virtual input and select it.

To keep hearing the audio while it is routed to the cable, use VoiceMeeter, or
set the cable as default playback and monitor it back to your speakers.

## macOS

- **BlackHole** (free, 2ch): create a **Multi-Output Device** in Audio MIDI
  Setup that includes both your speakers/headphones and BlackHole, set it as the
  system output, then select **BlackHole** in the visualizer. This lets you hear
  the audio and visualize it at the same time.

## Linux (PipeWire / PulseAudio)

- Most desktops expose a **monitor** source for each output sink
  (e.g. "Monitor of Built-in Audio"). Select that monitor source in the
  visualizer to capture whatever is playing.
- With `pavucontrol`, open the **Recording** tab while the page is running and
  set its input to the monitor of the relevant sink.
- For finer control, create a loopback:
  `pactl load-module module-loopback`.

## Troubleshooting

- **Empty device list / permission error:** serve the page over `http://localhost`
  instead of opening the file directly (`npm start`), since some browsers only
  allow audio capture in a secure context.
- **Device labels are blank:** labels only appear after you grant audio
  permission for the first time; start once, then re-open the picker.
- **No reaction:** confirm audio is actually playing to the selected device
  (check your OS mixer / `pavucontrol` recording tab).
- **Still no reaction:** open `demo.html`. If the presets react there, the
  visualizer and your GPU are fine and the problem is the routing, which
  narrows the search considerably.
