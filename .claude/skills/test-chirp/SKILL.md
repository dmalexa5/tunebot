# Test chirp

Use when asked to run a chirp test or create per-capture frequency-response plots.
Read `CLAUDE.md` and `cheatsheet.md` for hardware setup and capture limits.

1. Obtain missing settings together: amplitude (A), start/end frequency (Hz),
   duration (integer ms), repeat count (at least 2), stride, target IP, a new
   `traces/<session>/` directory, and RTT server state. Confirm OpenOCD is running;
   do not start it. Require `DEBUG=1`, `TRACE=MECH` firmware. Do not change gains.
   Default to 10–1000 Hz, stride 4, and 3268 ms (the longest integer-ms sweep
   fitting the timeline with stride-4 pads); stride 2 truncates the capture stream.
   Optionally accept `--taper FRACTION` (a Tukey taper applied only to the
   analysis window, default off) if edge leakage is still too strong after
   detrending — separate from, and does not affect, the chirp waveform itself,
   which stays without taper.
2. Ensure `.venv` has `requirements.txt` installed. Run from the repository root:
```sh
   scripts/run-chirp.sh -i IP amplitude_A f0_hz f1_hz duration_ms repeats stride traces/session
```
   Use `-r` only if the RTT server needs starting. All repeats use the same
   zero-DC logarithmic current chirp, without taper, in `0TQ` mode.
3. The wrapper zeros current and waits 1 second before each capture, checks
   baseline `ovel` RMS below 0.05 rad/s, and does not reposition. Override only
   when requested with `--delay SEC` and `--rest-threshold RAD_S` before the
   positional arguments. 
4. Analysis excludes baseline, tail, and closing samples first, then linearly
   detrends each trace (removes the best-fit line, not just the mean) over
   that analysis window only, per capture, before computing FFTs separately
   per capture. Detrending — not plain mean removal — is what actually
   addresses the net-displacement ramp in `mpos`/`opos` (and any residual
   drift in `mvel`/`ovel`); it meaningfully reduces low-frequency leakage in
   the unwindowed FFT, especially near the 10 Hz end of the sweep. It does not
   eliminate endpoint leakage from non-periodic net displacement — that's
   inherent to a non-returning chirp and isn't fixed by detrending,
   windowing, or a slower sweep.
   Computes the complex response ratio `Y / iq_cmd` from this single
   detrended, unwindowed, full-length FFT per capture — full frequency
   resolution, no averaging across captures — and plots `iq_fbk`, `mvel`,
   `ovel`, `mpos`, and `opos` against `iq_cmd`, using radians and signed
   motor/output ratio -509.7. Position is unwrapped before scaling.
   Separately, for a non-trivial coherence estimate, compute a
   Welch/`mscohere`-style estimate within the same capture: split the
   analysis window into overlapping (50%) Hann-windowed segments, average
   `Pxx`, `Pyy`, `Pxy` across segments, then `coherence = |Pxy|^2 / (Pxx *
   Pyy)`. This stays within one capture — no averaging across captures or
   repeats — trading frequency resolution for a valid quality metric; use
   enough segments (~6–8) for the estimate to mean something without losing
   too much resolution over 10–1000 Hz. Treat it as a practical SNR/quality
   indicator, not a stationary-process-grade coherence — the chirp's
   instantaneous frequency isn't constant within a segment.
5. Return `traces/<session>/chirp-*.0000.png` and the capture paths with a short
   settings summary. Each PNG uses its capture's stem and has two
   panels: magnitude and coherence (with a dashed reference
   line at 0.9 marking where the magnitude above should be treated as
   unreliable). No CSV export or separate report is needed. Surface cleanup
   errors to the user.

**Note:** if a "truncated/unexpected length" occurs, i.e. 
`truncated/unexpected length 16380; expected 16381..16382`
ignore the issue and continue all captures. This is a known issue and will not affect the correctness of the chirp results or analysis.