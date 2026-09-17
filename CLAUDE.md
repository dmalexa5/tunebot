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

# capture (writes <prefix>.NNNN.txf in CWD; -i IP, -r start-rtt-server,
# -F keep FEATURE_FRIC_COMP). base/start must be 0; see the mode note below.
run-step.sh  -i 100.79.218.29 vel 0.2 500          # mode step hold_ms [base] [stride] [prefix]
run-ramp.sh  -i 100.79.218.29 torque 0.1 1000 0 3  # mode delta duration_ms [start] [stride] [prefix]
run-sine.sh  -i 100.79.218.29 pos 1 0.05 3         # mode freq_hz amp [cycles] [stride] [prefix]
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

## The signal engine, and what the wrappers add

Since `module-fwpp` 0b9351e the firmware has exactly one waveform engine —
`signal_step` / `signal_ramp` / `signal_sine` / `signal_chirp`, routed to
`iq` / `id` / `vel` / `pos` by a `"signal"` field. The `servo_step`,
`ramp_servo`, `servo_sine`, `foc_step` and `ramp_foc` tests the wrappers used
to drive are **gone** (check `drive-none.tables.json` if in doubt: it is the
authority on what the build actually exposes).

The engine only *superimposes a per-tick delta* on its target. It does not
select a control mode, and it does not stop the joint when it finishes. Each
`run-*.sh` therefore brackets the capture: write the FOC mode with
`Jx_STATUS` (`pos`->`POS`, `vel`->`VEL`, `torque`->`0TQ` with the waveform on
`iq`), run the waveform, then write `mode:0TQ` again on every exit path —
Ctrl-C and a failed capture included. That last step is not cosmetic: a ramp
ends *holding its target*, so an unbracketed `vel` ramp leaves the joint
turning.

Three things fall out of that and are easy to trip over:

- **No `base`/`start`.** The waveform rides whatever the mode change leaves
  behind (0 A in `0TQ`, `vel_cmd` 0 on a VEL enable, `pos_cmd = pos_fbk` on a
  POS enable). The wrappers reject a non-zero value rather than pretend.
- **`torque` is a raw `iq` command with the cascade off**, so `VEL_TQC_LIM`
  no longer clamps it and friction compensation does not apply (that needs
  `SERVO_LOOP_VEL`). Only `FOC_I_TRIP` bounds it.
- **Writing a mode rebuilds the whole ctrl word**, clearing
  `FEATURE_FRIC_COMP`. Pass `-F` to keep it set.

### The uint16 tick timeline

`start_pad + duration + end_pad` is counted in raw 20 kHz servo ticks and must
stay under 65535 — **~3.27 s per capture**, pads included. The firmware
truncates a `period` past `uint16` silently (0.1 Hz would come back as
~5.9 Hz), so the wrappers range-check and refuse instead. Practical caps:
3.25 s of hold/ramp; sines at >= 0.31 Hz, 3 cycles at 1 Hz, 1 cycle at 0.5 Hz.
`run-sine.sh` prints the realized frequency (the engine takes a whole-tick
period) — pass *that* to `txf-sine.py`, which uses it as the DFT bin.

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
`{"test":"signal_sine","signal":"pos","amplitude":0.138}` commands 0.138
*counts* and moves nothing. Torque is amps on both sides and passes through
unscaled.

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
  available too. Analyzers only use the `*_cmd`/`*_fbk` pairing. An alias
  never overwrites a trace the firmware already publishes under that name:
  `mech_trace` now carries its own `vel_fbk` — the velocity the loop actually
  closes on, which is the *rotor* side through a 500 Hz biquad when
  `SERVO_FLAGS` selects `VEL_SRC_MENC` and only equals `ovel` in the default
  output-encoder configuration. Older captures have no `vel_fbk` and still
  fall back to `ovel`.
- **Unwrap `pos_cmd`/`pos_fbk`/`pos_rx`** from the firmware's `[-pi, pi)` wrap,
  so a rest position near the boundary doesn't read as a spurious ~2π step.

`txf-step.py` and `txf-ramp.py` re-derive `dt` from `hscale` and assume
`EDGE = 20`. That is now a *host-side* convention, not a firmware one: the
`run-*.sh` wrappers ask for `start_pad = end_pad = 20 * stride` servo ticks,
which comes back as exactly 20 pushed samples of baseline before the waveform
and 20 of tail after, whatever the stride — so edges sit at fixed indices and
are never detected from the data. Change a pad in a wrapper and `EDGE` has to
move with it. `txf-sine.py` relies on the same convention (detecting edges
would lose a cycle in velocity mode, where the sine starts and ends at zero).

## Metrics worth knowing

- **`iq_jitter`** — rms first-difference of `iq_cmd`, reported by every analyzer.
  This is the chatter detector: `iq_cmd` is the velocity loop's own output, so
  its sample-to-sample jitter is loop activity with no measurement noise mixed in.
  Minimizing it is the objective of `tune-chatter`.
- **`err_fund` vs `err_resid_rms`** (`txf-sine.py`) — the tracking error split
  into its component at the drive frequency (linear lag/gain) and everything
  else (stiction, nonlinearity, noise).
- **Stride defaults per mode** (torque 1, vel 12, pos 20) — the RTT link can't
  sustain the full 20 kHz rate; raise stride further for long runs. Stride
  also sets the pads (`20 * stride` ticks), so it eats into the ~3.27 s
  tick budget.
- **`vel_fbk` vs `ovel`** — `vel_fbk` is what the velocity PID sees;
  `ovel` is the raw output encoder. They differ once `SERVO_FLAGS` selects
  `VEL_SRC_MENC` (rotor-side `mvel`, 500 Hz biquad, 10 kHz loop). Tune the
  loop against `vel_fbk`; judge load-side motion with `ovel`.

## Gotchas

- Captures land in the **CWD**, not `traces/`. Running a script from `scripts/`
  litters it with `*.txf/` dirs (several are there now). `traces/`, `*.txf/`,
  and `*.bin` are gitignored, so captures are never committed — reports
  reference them by path only.
- `txf-breakaway.py`'s velocity threshold must sit above the joint's actual
  `vel_fbk` noise floor (~3 mrad/s std with ~14 mrad/s spikes on j1), hence the
  50 mrad/s default plus a 3-consecutive-sample sustain requirement.
- Velocity-loop transients are slow (~300 ms on j1). Steady-state extraction
  skips a fixed settle window rather than trusting the last fraction of a hold.
- The velocity stage runs at **10 kHz** as of `module-fwpp` 0b9351e (was
  5 kHz); the MENC gains were retuned for that rate and do not carry back.
- `signal_*` applies its delta *after* the trace record is pushed, so a
  capture shows each command one tick before the injection lands, and
  `pos_cmd += (int32_t)d` truncates the sub-count remainder the old
  `servo_sine` carried. Both are far below the noise floor at the amplitudes
  used here, but they are why a `pos` capture is not bit-identical to an old
  one.

## Reports

`reports/tune-chatter-example.md` and `reports/tune-friction-example.md` are
templates — fill them in, strip the HTML comments, keep it concise.
`reports/tune-friction-j1.md` is the worked example, including negative results
(which params the data did *not* identify, and why). Record those the same way.
