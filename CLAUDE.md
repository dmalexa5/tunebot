# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Host-side harness for tuning CNS drive joints (STM32G431 FOC drives). It has no
build step and ships no firmware: it drives the firmware's built-in tests over
RTT, captures traces, and analyzes/fits them. Three layers, in order of a
typical session:

1. **`scripts/run-*.sh`** — thin zsh wrappers over `rtttest` that command a
   servo test and write a `.txf` capture to the **current directory**.
2. **`scripts/txf-*.py`** — stdlib-only Python that reads a `.txf` and prints
   numeric metrics (tracking error, overshoot, chatter, breakaway) or exports CSV.
3. **`scripts/*.m`** — MATLAB nonlinear fits (Stribeck curve, LuGre ODE) over
   the CSVs the Python layer exports.

Workflows are encoded as skills in `.claude/skills/` (`tune-chatter`,
`tune-friction`); results go to `reports/`, captures to `traces/<session>/`.

## External dependencies (sibling repos, not vendored)

- **`../module-fwpp`** — the firmware and the `rttcmd`/`rtttask`/`rtttest`
  tools. The shell scripts hardcode `../../module-fwpp/tools/rttcmd/rtttest`
  and `../../module-fwpp/output/drive/none/drive-none.tables.json` relative to
  `scripts/`. `../module-fwpp/cheatsheet.md` is the authority on the rtttest
  JSON protocol; `../module-fwpp/src/servo.c` is the cascaded PID under test.
- **`../cn-seamless/configs/tunables/*.json`** — where final gains are written
  (`drive-gains.json` for the universal arm, `drive-gains-bevel.json` for bevel).

## Preconditions before any capture

Every script talks to a live board; none of them will work without:

- `openocd` running with RTT servers up. Confirm with the user — do not start it.
- `DEBUG=1` firmware built with `TRACE=MECH` (`make drive-debug-no-bl TRACE=MECH`).
  Without MECH there are no `pos_cmd`/`vel_cmd`/`opos`/`ovel` traces and the
  pos/vel analyzers have nothing to read.
- `-r` on the *first* rttcmd invocation only, if the RTT server hasn't been started.
- Non-zero servo gains. They ship as 0.0 and the joint will not move under a
  velocity or position command — check before trusting any capture
  (see `reports/tune-friction-j1.md`, where this cost a whole test round).

## Commands

```sh
source env.zsh                      # puts scripts/ on PATH for this shell

# capture (writes <prefix>.NNNN.txf in CWD; -i IP, -r start-rtt-server)
run-step.sh  -i 100.79.218.29 vel 0.2 500          # mode step hold_ms [base] [stride] [prefix]
run-ramp.sh  -i 100.79.218.29 torque 0.1 1000 0 3  # mode delta duration_ms [start] [stride] [prefix]
run-sine.sh  -i 100.79.218.29 pos 1 0.05 5         # mode freq_hz amp [cycles] [stride] [prefix]
set-gains.sh -i 100.79.218.29 vkp vki pkp pki [tqclim] [vellim]
clear-faults.sh -i 100.79.218.29                   # clears latched FOC faults

# analyze
scripts/txf-step.py  vstep.0000.txf vel
scripts/txf-ramp.py  tramp.0000.txf torque
scripts/txf-sine.py  psine.0000.txf 1.0 pos        # freq is required (DFT bin)
scripts/txf-breakaway.py tramp.0000.txf 0.05 presliding.csv 3
scripts/txf-export-csv.py tsine.0000.txf t,ovel,iq_fbk dither.csv

# MATLAB (run startup.m first; it loads the Simulink agentic toolkit MCP server)
fit_stribeck('traces/j1-friction-tune/vstep.*.txf')
fit_lugre_joint({'presliding.csv','dither.csv'}, Ic, Is, stribeck_vel)
```

`cheatsheet.md` has the full invocation set including chirps, which have no
wrapper script and call `rtttest` directly.

No test suite, no linter, no package manifest. The Python is stdlib-only —
`.venv/` exists but nothing here needs it.

## The unit boundary (the single most important invariant)

The servo loop speaks **output-shaft counts** (2^32/rev) and counts/s;
"radians appear nowhere" (`module-fwpp src/servo.h`). Everything in this repo
above the wrapper scripts — arguments, skills, reports, tunables, analyzer
output — is in **rad, rad/s, and amps**.

The conversion exists in exactly two places: the `to_cmd`/`RAD_TO_CNT` block in
each `run-*.sh`, and the `vel_gain`/`rad_to_cnt` helpers in `set-gains.sh`
(which mirror the firmware's `SERVO_RAD_TO_CNT`, `SERVO_VEL_GAIN_FROM_RAD`,
`SERVO_POS_GAIN_FROM_RAD` macros — position gains are 1/s either way and pass
through unchanged).

**Never call `rtttest` directly with a rad-valued amplitude.** A raw
`{"test":"servo_sine","amp":0.138}` commands 0.138 *counts* and moves nothing.
Torque is amps on both sides and passes through unscaled.

## .txf capture format and the shared loader

A `.txf` is a **directory**: `metadata.json` lists traces (`dtype`, `vscale`,
`voffset`, `unit`, `hscale`, `file`), each backed by a `traceN.bin` of raw
little-endian samples. `hscale` is the sample period.

The `DT` / `DEG_UNITS` / `FBK_ALIASES` / `unwrap` / `load` block at the top of
every `txf-*.py` is **duplicated verbatim** across all five scripts and mirrored
in `scripts/txf_load.m`. This is deliberate — each script stays runnable on its
own — so a format change means editing all six. Its three jobs:

- **Degrees → rad**, keyed off the metadata `unit` field (`°`, `°/s`), not a
  name list; the firmware traces angles in degrees.
- **Alias `opos`/`ovel` → `pos_fbk`/`vel_fbk`.** Depending on the trace set, the
  firmware names feedback after the encoders it reads; the firmware names stay
  available too. Analyzers only use the `*_cmd`/`*_fbk` pairing.
- **Unwrap `pos_cmd`/`pos_fbk`/`pos_rx`** from the firmware's `[-pi, pi)` wrap,
  so a rest position near the boundary doesn't read as a spurious ~2π step.

`txf-step.py` and `txf-ramp.py` re-derive `dt` from `hscale` and assume
`EDGE = 20`: `TEST_SERVO_STEP_EDGE_SAMPLES` in `board-drive.c` guarantees
exactly 20 *pushed* samples of baseline before the waveform and 20 of tail
after, whatever the stride — so edges sit at fixed indices and are never
detected from the data. `txf-sine.py` relies on the same convention (detecting
edges would lose a cycle in velocity mode, where the sine starts and ends at zero).

## Metrics worth knowing

- **`iq_jitter`** — rms first-difference of `iq_cmd`, reported by every analyzer.
  This is the chatter detector: `iq_cmd` is the velocity loop's own output, so
  its sample-to-sample jitter is loop activity with no measurement noise mixed in.
  Minimizing it is the objective of `tune-chatter`.
- **`err_fund` vs `err_resid_rms`** (`txf-sine.py`) — the tracking error split
  into its component at the drive frequency (linear lag/gain) and everything
  else (stiction, nonlinearity, noise).
- **Stride defaults per mode** (torque 1, vel 12, pos 20) — the RTT link can't
  sustain the full 20 kHz rate; raise stride further for long runs.

## Gotchas

- Captures land in the **CWD**, not `traces/`. Running a script from `scripts/`
  litters it with `*.txf/` dirs (several are there now). `traces/`, `*.txf/`,
  and `*.bin` are gitignored, so captures are never committed — reports
  reference them by path only.
- `set-gains.sh` is the odd one out: it sources a hardcoded
  `/Users/dmalexa/tmp/j0-fullarm-retune/_tools/env.sh` for `$RT` instead of
  resolving `rtttask` relative to its own directory like the other scripts.
- `txf-breakaway.py`'s velocity threshold must sit above the joint's actual
  `vel_fbk` noise floor (~3 mrad/s std with ~14 mrad/s spikes on j1), hence the
  50 mrad/s default plus a 3-consecutive-sample sustain requirement.
- Velocity-loop transients are slow (~300 ms on j1). Steady-state extraction
  skips a fixed settle window rather than trusting the last fraction of a hold.

## Reports

`reports/tune-chatter-example.md` and `reports/tune-friction-example.md` are
templates — fill them in, strip the HTML comments, keep it concise.
`reports/tune-friction-j1.md` is the worked example, including negative results
(which params the data did *not* identify, and why). Record those the same way.
