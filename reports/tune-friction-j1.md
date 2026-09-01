# tune-friction report: j1

### Final parameters:

- `IC = 1.1738 A`
- `IS = 1.0675 A`
- `STRIBECK_VEL = 0.0159 rad/s`
- `SIG0 = not identifiable (see Notes)`
- `SIG1 = not identifiable (see Notes)`
- `SIG2 = 0.5872 A/(rad/s)`

### Notes

Target: `100.79.218.29`, RTT server already running. Before Test 1, `Jx_CTRL_STATUS`
showed `VEL_KP`/`VEL_KI` both 0 (velocity loop unconfigured) -- the joint could
not move under a velocity command. Gains were set externally
(`VEL_KP=24`, `VEL_KI=0.6`) and verified before any capture was trusted.

**Test 1** (steady-state friction-velocity map): 13 log-spaced velocity holds,
0.01-0.875 rad/s (`run-step.sh vel`, 1000 ms hold, stride 12). At the first
attempt (300 ms hold) the tail window used to extract steady-state current was
too short: a 100 mrad/s probe showed 51% overshoot and a ~300 ms decay, so the
last-1/5-of-hold trim caught mid-decay samples, not steady state. Hold was
increased to 1000 ms and extraction changed to skip a fixed 300 ms settle
period, then average the rest (`fit_stribeck.m`). The resulting fit
(`lsqcurvefit`, MATLAB) converged cleanly (resnorm 0.00196 over 13 points),
but the data itself showed no visible Stribeck knee across the sampled
range -- current rose monotonically from 1.11 A at 0.01 rad/s to 1.67 A at
0.875 rad/s, with no static-friction peak at low velocity. As a result `IS`
came back below `IC`, and `STRIBECK_VEL` sits right at the low edge of the
sampled range -- both are only weakly constrained by this dataset. `SIG2`
is the most reliable Test 1 output.

**Test 2** (breakaway vs. loading rate): current ramps at 0.1, 0.33, 1, 3.3,
10, 33, 100 A/s (0.5->2.0 A, `run-ramp.sh torque`) plus a literal 0->2.0 A
step (`run-step.sh torque`). The breakaway detector's default velocity
threshold (10 mrad/s) sat inside `vel_fbk`'s actual noise floor on this joint
(~3 mrad/s std, spikes to ~14 mrad/s) and produced false triggers within the
first ~10 ms of several ramps. Fixed by raising the threshold to 20 mrad/s
and requiring 3 consecutive samples above it (`txf-breakaway.py`), verified
against raw samples on the fastest ramp. Breakaway current across rates:
1.10-1.68 A, without a clean monotonic trend from 0.1-33 A/s but rising
clearly by 100 A/s. Per plan, this was not fit to a closed-form
breakaway-rate relation; presliding segments were instead handed to the
Test 3 joint fit as the mechanism for estimating `SIG0`.

**Test 3** (pre-sliding damping): current dither sweep at 1, 2, 5, 10, 20,
50, 100 Hz, 0.15 A amplitude, 20 cycles, stride 20 (`run-sine.sh torque`) --
well clear of the 1.1-2.0 A breakaway band, and confirmed no sliding occurred
(vel_fbk stayed within the established noise floor throughout). The joint
LuGre-ODE fit (`fit_lugre_joint.m`, `lsqnonlin`, all 8 Test 2 presliding
segments + 7 dither captures, `IC`/`IS`/`STRIBECK_VEL` fixed from Test 1)
degenerated to non-physical values (`sig0~=0`, `sig1~=93`, `sig2~=-116`).
Diagnosis: `vel_fbk` in every one of the 15 trials was statistically
indistinguishable from the noise floor characterized in Test 2 (std
2-8 mrad/s, means near zero) -- true pre-sliding elastic-deflection velocity
is apparently far below what a differentiated encoder signal can resolve on
this joint at this dither amplitude. Since the ODE's `z` state is driven
directly by this velocity, the fit was effectively fitting noise.
**`SIG0` and `SIG1` are not identified by this test.** Suggested next steps
if revisited: a larger dither amplitude (still below the breakaway band), or
deriving a lower-noise velocity estimate from filtered `pos_fbk` instead of
`vel_fbk`, before repeating the joint ODE fit.

### Captures

- `traces/j1-friction-tune/vstep.0000.txf` (Test 1, velocity hold)
- `traces/j1-friction-tune/tramp.0000.txf` (Test 2, current ramp)
- `traces/j1-friction-tune/tstep.0000.txf` (Test 2, literal current step)
- `traces/j1-friction-tune/tsine.0000.txf` (Test 3, current dither)
