---
name: test-chirp
description: Capture repeated identical current chirps and plot each capture's frequency-response magnitude and phase against iq_cmd.
---

# Test chirp

Use when asked to run a chirp test or create per-capture frequency-response plots.
Read `CLAUDE.md` and `cheatsheet.md` for hardware setup and capture limits.

1. Obtain missing settings together: amplitude (A), start/end frequency (Hz),
   duration (integer ms), repeat count (at least 2), stride, target IP, a new
   `traces/<session>/` directory, and RTT server state. Confirm OpenOCD is running;
   do not start it. Require `DEBUG=1`, `TRACE=MECH` firmware. Do not change gains.
   Default to 10–1000 Hz, stride 4, and 3268 ms (the longest integer-ms sweep
   fitting the timeline with stride-4 pads); stride 2 truncates the capture stream.
2. Ensure `.venv` has `requirements.txt` installed. Run from the repository root:
   ```sh
   scripts/run-chirp.sh -i IP amplitude_A f0_hz f1_hz duration_ms repeats stride traces/session
   ```
   Use `-r` only if the RTT server needs starting. All repeats use the same
   zero-DC logarithmic current chirp, without taper, in `0TQ` mode.
3. The wrapper zeros current and waits 1 second before each capture, checks
   baseline `ovel` RMS below 0.05 rad/s, and does not reposition. Override only
   when requested with `--delay SEC` and `--rest-threshold RAD_S` before the
   positional arguments. It stops on invalid captures; retain them and explain
   the failure instead of silently retrying or changing chirp settings.
4. Analysis mean-subtracts each capture's traces and computes its FFTs separately,
   then plots the complex response ratio `Y / iq_cmd` without averaging captures.
   It plots `iq_fbk`, `mvel`, `ovel`, `mpos`, and `opos` against `iq_cmd`, using
   radians and signed motor/output ratio -509.7. The whole chirp is analyzed
   without windowing or smoothing; baseline, tail, and closing samples are excluded.
   Position is unwrapped before scaling, but net displacement still causes
   endpoint leakage; separate plots and a slower sweep do not remove it.
5. Return `traces/<session>/chirp-*.0000.png` and the capture paths with a short
   settings summary. Each PNG uses its capture's stem and has magnitude and
   wrapped phase panels. Do not plot single-record coherence, which would be
   trivially one without spectral averaging. No CSV export or separate report
   is needed. Surface cleanup errors to the user.
