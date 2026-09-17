---
name: tune-friction
description: Identify an unloaded joint's Stribeck and LuGre friction parameters from RTT captures using MATLAB.
---

# Tune friction

Read `CLAUDE.md` and `cheatsheet.md` for setup, units, and capture limits.
Obtain missing session details together: unloaded joint, capture directory,
target IP, and RTT server state. Verify gains and MATLAB availability.

## Steady-state map: Ic, Is, stribeck_vel, sig2

Capture 1000 ms velocity holds with `scripts/run-step.sh`, default stride 12:
0.010, 0.015, 0.022, 0.033, 0.050, 0.075, 0.100, 0.150, 0.225, 0.338,
0.507, 0.760, 0.875 rad/s. Fit with `scripts/fit_stribeck.m` (300 ms settle skip).
Do not claim a resolved Stribeck knee if the data does not show one.

## Presliding: sig0

Capture 0-to-3 A current ramps at 1, 3.3, 10, 33, and 100 A/s,
5 trials per rate in both directions, plus a 0-to-2 A step.
Use `scripts/run-ramp.sh` / `scripts/run-step.sh`; verify rest between trials.
A 2 A step may not exceed breakaway; record failures rather than forcing a fit.
Rates 0.1 and 0.33 A/s exceed the current capture limit; report their omission.

Detect breakaway with `scripts/txf-breakaway.py`, using a threshold above measured
noise. Reject overflowed captures and trials that end before breakaway.
Fit presliding traces with the LuGre model in `scripts/lugre_predict.m`, holding
steady-state parameters fixed. Prefer unwrapped motor position referred through
a measured gear ratio when velocity feedback cannot resolve presliding motion.
`fit_lugre_joint.m` fits sig2 jointly; do not trust it to identify viscous damping
from presliding data alone. Report sig0/sig1 as unidentified when unsupported.

Move captures to the session directory. Report parameters with units, uncertainty
or identification limits, test conditions, and capture paths.
