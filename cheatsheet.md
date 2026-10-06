# Commands

Run from the repository root after `source env.zsh`.
Arguments use radians, radians/s, and amps; wrappers convert to firmware counts.
Use `set-gains.sh` for gain conversion too.

## Capture

```sh
run-step.sh  [-i IP] [-r] [-F] mode step hold_ms [base] [stride] [prefix]
run-ramp.sh  [-i IP] [-r] [-F] mode delta duration_ms [start] [stride] [prefix]
run-sine.sh  [-i IP] [-r] [-F] mode freq_hz amp [cycles] [stride] [prefix]
run-trace.sh [-i IP] [-r] {pos|vel|torque} [stride] [prefix]
run-chirp.sh [-i IP] [-r] [--delay SEC] [--rest-threshold RAD_S] amplitude_A f0_hz f1_hz duration_ms repeats stride session_dir
set-gains.sh [-i IP] vkp vki pkp pki [tqclim] [vellim]
clear-faults.sh [-i IP] [-r]
.venv/bin/python scripts/test-tracking.py [-i IP] [-r] [-F] traces/session
```

- `mode`: `pos`, `vel`, or `torque`. Default IP: `127.0.0.1`.
  Use `-r` only on the first invocation if the RTT server needs starting.
- `base`/`start` must be zero. Default stride: torque 1, vel 12, pos 20.
  Raise stride if captures overflow or truncate.
- Wrappers select the control mode and attempt to return to `0TQ` on exit.
  Torque commands raw `iq`; only `FOC_I_TRIP` limits it, not `VEL_TQC_LIM`.
- Mode writes clear friction compensation; `-F` preserves it during capture.
- Total timeline, including pads, is limited to 65534 ticks at 20 kHz (~3.27 s).
  At stride 20: 3 cycles at 1 Hz, 2 at 0.75 Hz, 1 at 0.5 Hz.
  Pass the sine wrapper's printed realized frequency to the analyzer.
- `run-trace.sh` captures three seconds with zero added command, using the
  existing control mode (pos/vel/torque) to select a compatible trace trigger.
  It does not select or change the mode; the selected mode must already match
  the live drive mode. Default stride is 20 (1 kHz); output is
  `<prefix>.NNNN.txf` in the current directory.
- Raw `rtttest` position/velocity amplitudes use counts/counts per second,
  not radians. For tests without wrappers, consult
  `../module-fwpp/cheatsheet.md` and manage control mode and stopping yourself.

## Analysis

Tracking tests capture ten evenly spaced fixed frequencies from 0.1 to 0.6 Hz
at 0.25 rad peak amplitude, each for 3 seconds at stride 20. They use equal
`signal_chirp` endpoints to allow partial-cycle sines below the `signal_sine`
period limit. One `tracking.png` plots peak and mean absolute position error
over the entire driven window, including startup, in mrad versus Hz. Replot with
`.venv/bin/python scripts/test-tracking.py --analyze traces/session`.

Chirp tests use `.venv/bin/python` with `requirements.txt` installed. Use a new
`traces/<session>/` directory and at least two repeats. The wrapper captures
identical zero-DC, constant-amplitude logarithmic `iq` chirps in `0TQ`, checks
baseline rest, and stops on invalid captures. Keep `f1_hz` below one-quarter of
`20000 / stride`; pads and chirp must fit 65534 ticks. Stride 2 truncates the
`TRACE=MECH` stream; use 4 or more, which caps `f1_hz` near 1250 Hz. It saves
raw captures and one `chirp-*.0000.png` per capture: magnitude and coherence for `iq_fbk`, `mvel`,
`ovel`, `mpos`, and `opos` relative to `iq_cmd`, using signed motor/output
ratio -509.7, with no averaging between captures. Coherence is a Welch
estimate from 50%-overlap Hann segments within each capture.
Default sweep: 10–1000 Hz, stride 4, 3268 ms. This is the longest integer-ms
duration fitting the timeline: `3268 * 20 + 2 * 20 * 4 = 65520` ticks;
3269 ms would exceed 65534. The slower sweep gives more cycles per frequency
interval, but does not guarantee settling or remove position endpoint leakage.

```sh
run-chirp.sh 0.3 10 1000 3268 5 4 traces/session
```

To reanalyze captures:

```sh
.venv/bin/python scripts/txf-chirp.py traces/session/chirp-*.txf --amplitude 0.3 --f0 10 --f1 1000 --duration-ms 3268 --repeats 5 --stride 4
```

```sh
scripts/txf-step.py capture.txf vel
scripts/txf-ramp.py capture.txf torque
scripts/txf-sine.py capture.txf 1.0 pos
scripts/txf-breakaway.py capture.txf 0.05 presliding.csv 3
scripts/txf-export-csv.py capture.txf mvel_filt,iq_fbk output.csv
```

Sine analysis supports `pos`/`vel`. `iq_jitter` is RMS first-difference of `iq_cmd`;
compare it at the same stride and waveform. Prefer sine captures for chatter.
Set breakaway velocity thresholds above measured `mvel_filt` baseline noise;
defaults are 0.05 rad/s and 3 consecutive samples. Friction tools require recorded `mvel_filt` from
updated `TRACE=MECH` firmware/tables; missing channels require new captures.
This filtered motor-derived signal is already sign-corrected output-shaft rad/s;
do not divide by a gear ratio or substitute other velocity signals. Identify
with compensation disabled (omit `-F`). Use both signs of velocity holds.
CSV export adds `t`; joint LuGre fits require headers `t,w,iq`.
For exported CSVs, rename `mvel_filt` to `w` and `iq_fbk` to `iq`, keeping values
unchanged; breakaway exports already use these headers.

```sh
.venv/bin/python scripts/fit_stribeck.py 'traces/session/vhold.*.txf' # skips first 300 ms
```

```matlab
addpath('scripts');
result = fit_lugre_joint({'presliding.csv'}, Ic, Is, stribeck_vel);
```
