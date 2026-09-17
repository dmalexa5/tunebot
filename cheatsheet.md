# Commands

Run from the repository root after `source env.zsh`.
Arguments use radians, radians/s, and amps; wrappers convert to firmware counts.
Use `set-gains.sh` for gain conversion too.

## Capture

```sh
run-step.sh  [-i IP] [-r] [-F] mode step hold_ms [base] [stride] [prefix]
run-ramp.sh  [-i IP] [-r] [-F] mode delta duration_ms [start] [stride] [prefix]
run-sine.sh  [-i IP] [-r] [-F] mode freq_hz amp [cycles] [stride] [prefix]
set-gains.sh [-i IP] vkp vki pkp pki [tqclim] [vellim]
clear-faults.sh [-i IP] [-r]
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
- Raw `rtttest` position/velocity amplitudes use counts/counts per second,
  not radians. For tests without wrappers (chirps), consult
  `../module-fwpp/cheatsheet.md` and manage control mode and stopping yourself.

## Analysis

```sh
scripts/txf-step.py capture.txf vel
scripts/txf-ramp.py capture.txf torque
scripts/txf-sine.py capture.txf 1.0 pos
scripts/txf-breakaway.py capture.txf 0.05 presliding.csv 3
scripts/txf-export-csv.py capture.txf ovel,iq_fbk output.csv
```

Sine analysis supports `pos`/`vel`. `iq_jitter` is RMS first-difference of `iq_cmd`;
compare it at the same stride and waveform. Prefer sine captures for chatter.
Set breakaway velocity thresholds above measured noise; defaults are 0.05 rad/s
and 3 consecutive samples. CSV export adds `t`; joint LuGre fits require headers `t,w,iq`.

```matlab
addpath('scripts');
result = fit_stribeck('traces/session/vhold.*.txf'); % skips first 300 ms
result = fit_lugre_joint({'presliding.csv'}, Ic, Is, stribeck_vel);
```
