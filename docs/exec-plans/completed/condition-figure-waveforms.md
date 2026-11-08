# Condition Figure waveforms

Status: Completed

Adapt the Condition Figure PNG to the supplied paper figure. Align stimulus
examples above the contrast-versus-time axis and mark the oddball slots on the
same axis. Omit image overlays. At the default cadence, show two oddballs and
the following two base slots. Use the configured condition rate and cadence
for the time labels and the base and oddball frequencies.

Carry the condition's presentation mode into the renderer. Show a square wave
for 50% blank, the smooth contrast envelope for sinusoidal modulation, and a
full-contrast trace with stimulus boundaries for continuous presentation. The
illustration uses authored timing and representative stimuli.

Non-Qt verification covers mode propagation, contrast curves, oddball
alignment, and 600-DPI PNG output. The Creatine export check used the five
configured conditions at 6 Hz with oddballs at 1.2 Hz. Two conditions use
continuous presentation and three use 50% blank. A separate 7.5 Hz sinusoidal
export checked the waveform and the derived 1.5 Hz oddball label.
