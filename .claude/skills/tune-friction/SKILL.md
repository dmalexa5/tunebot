---
name: tune-friction
description: Tune only Ic, sig2, and breakaway friction for an unloaded joint from RTT captures.
---

# Tune friction

Read `CLAUDE.md` and `cheatsheet.md` for setup, units, and capture limits.
Obtain missing session details together: unloaded joint, capture directory,
target IP, and RTT server state. Verify gains and the Python environment. Tune
only `Ic`, `sig2`, and breakaway friction. Keep `Is`, `stribeck_vel`, `sig0`,
and `sig1` fixed; do not fit or recommend changes to them. Treat values for
those parameters from a full-model fit as fixed inputs, not tuning results.

Use captures with recorded `mvel_filt`: the firmware's filtered motor velocity,
sign-corrected and scaled into output-shaft rad/s. This is the friction input
for `FRIC_SRC=2` with `FRIC_LPF=1` (no additional smoothing). Require updated
`TRACE=MECH` firmware and capture tables exposing that channel. Reject captures
missing it; never substitute `ovel`, `vel_fbk`, raw `mvel`, or position-derived
velocity. Do not apply another gear-ratio conversion. Identify with compensation
disabled (omit `-F`); confirm `iq_fric` is zero when recorded.

## Steady-state map: Ic and sig2

Capture positive and negative 1000 ms velocity holds with `scripts/run-step.sh`,
default stride 12:
0.010, 0.015, 0.022, 0.033, 0.050, 0.075, 0.100, 0.150, 0.225, 0.338,
0.507, 0.760, 0.875 rad/s (output-coordinate command magnitudes).
Use `.venv/bin/python scripts/fit_stribeck.py 'traces/session/vhold.*.txf'`
(300 ms settle skip) to analyze the data. The fit uses mean `mvel_filt` and
`iq_fbk`, speed magnitude and direction-aligned current. Use configured/fixed
`Is` and `stribeck_vel` when deriving `Ic` and `sig2`; do not adopt their fitted
values. Compare retained `signed_w`/`signed_I` pairs between directions and
report disagreement. Do not claim a resolved Stribeck knee if the data does
not show one.

## Breakaway friction

Capture 0-to-3 A current ramps at 1, 3.3, 10, 33, and 100 A/s,
5 trials per rate in both directions, plus a 0-to-2 A step.
Use `scripts/run-ramp.sh` / `scripts/run-step.sh`; verify rest between trials.
A 2 A step may not exceed breakaway; record failures rather than forcing a
result. Rates 0.1 and 0.33 A/s exceed the current capture limit; report their
omission. Treat detected breakaway current as the breakaway-friction value;
report individual trials and directional/rate variation rather than fitting
additional friction parameters.

Detect breakaway with `scripts/txf-breakaway.py`, using a threshold above measured
`mvel_filt` baseline noise. Reject overflowed captures and trials that end
before breakaway.
Do not fit presliding traces or use `scripts/fit_lugre_joint.m`; those workflows
estimate parameters outside the requested tuning scope.

Move captures to the session directory. Report parameters with units, uncertainty
or identification limits, test conditions, and capture paths. State the motor
sensor source and output-referred units: `Ic` in A, `sig2` in A/(rad/s),
breakaway current in A, and fixed `Is` in A and `stribeck_vel` in rad/s.
