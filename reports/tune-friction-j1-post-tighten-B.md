# j1 friction tuning, post-tighten repeat (B) — 2026-09-25

Scope: `Ic`, `sig2`, breakaway current. `Is`, `stribeck_vel`, `sig0`,
`sig1` held fixed and not fit. Same-day repeat of
[tune-friction-j1-post-tighten.md](tune-friction-j1-post-tighten.md).

## Conditions

- Target `100.79.218.29`, j1 (vokcap), unloaded. OpenOCD and RTT server
  already running; `-r` not used. Thermal state not recorded (the joint had
  run the morning session earlier the same day).
- Gains read 0 at start; applied `gains/drive-gains.json` joint 1:
  `VEL_KP=8.0 VEL_KI=0.1 POS_KP=60 POS_KI=3.0 VEL_TQC_LIM=5.0 POS_VEL_LIM=π`.
  Readback matched (vel gains in raw counts domain).
- Live friction config (not changed): `FRIC_IC=1.4625 A`, `FRIC_IS=1.646 A`,
  `FRIC_SIGMA2=1.1095 A/(rad/s)`, `FRIC_VS=0.170 rad/s`, `FRIC_SRC=2`,
  `FRIC_LPF=1`, `SERVO_FLAGS=0`.
- Friction input: recorded `mvel_filt` (filtered motor velocity,
  sign-corrected, output-shaft rad/s; no gear-ratio conversion) and `iq_fbk` (A).
- Compensation off (no `-F`); `iq_fric` max |value| = 0 in all 86 captures.
- Captures: `traces/friction/j1-post-tighten-B/`. No overflow or truncation;
  every record count is at the expected length.

## Steady-state map: Ic, sig2

26 velocity holds, ±{0.010 … 0.875} rad/s (13 magnitudes), 1000 ms, stride 12,
`run-step.sh vel`. Analyzed with `scripts/fit_stribeck.py` (300 ms settle).
`Ic` and `sig2` refit from its retained pairs with fixed `Is = 1.646 A`,
`stribeck_vel = 0.170 rad/s` (live config).

| Fit | Ic (A) | sig2 (A/(rad/s)) | rms resid (A) |
|---|---|---|---|
| **Holds ≥0.338 rad/s (8 pts), fixed Is/vs** | **1.242 ± 0.019** | **1.066 ± 0.029** | 0.014 |
| — positive only | 1.241 ± 0.019 | 1.084 ± 0.029 | 0.009 |
| — negative only | 1.242 ± 0.019 | 1.047 ± 0.029 | 0.008 |
| Holds ≥0.225 rad/s (10 pts) | 1.194 ± 0.026 | 1.130 ± 0.042 | 0.026 |
| All 26 holds, fixed Is/vs | 1.09 ± 0.25 | 1.23 ± 0.41 | 0.29 |

Uncertainties are 1σ from the least-squares covariance.

**Recommended: `Ic = 1.24 A`, `sig2 = 1.07 A/(rad/s)`** (the ≥0.338 rad/s
fit). The fixed Stribeck term is <2% of `Is − Ic` there, so the result
barely depends on the fixed `Is`/`stribeck_vel`.

Identification limit: as in the morning session, the data show no Stribeck
peak or knee. Every hold below 0.15 rad/s is 1.06–1.37 A, below the fixed
`Is`, and current rises steadily from the lowest speed. The free 4-parameter
fit, a cross-check only and not adopted, drives `Is` to 0 (`Ic 1.247,
sig2 1.062`). The all-holds fixed-Is fit is not usable, and adding the
0.225 rad/s pair already shifts the estimate.

Directional agreement (retained `signed_w`/`signed_I` pairs):

| \|w\| (rad/s) | 0.010 | 0.015 | 0.022 | 0.033 | 0.050 | 0.075 | 0.100 | 0.150 | 0.225 | 0.338 | 0.507 | 0.760 | 0.875 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I+ (A) | 1.241 | 1.317 | 1.300 | 1.326 | 1.341 | 1.347 | 1.371 | 1.441 | 1.505 | 1.606 | 1.802 | 2.068 | 2.181 |
| \|I−\| (A) | 1.062 | 1.127 | 1.193 | 1.267 | 1.305 | 1.289 | 1.316 | 1.400 | 1.475 | 1.593 | 1.785 | 2.037 | 2.150 |
| Δ | +15.6% | +15.5% | +8.6% | +4.5% | +2.7% | +4.4% | +4.1% | +2.9% | +2.0% | +0.8% | +1.0% | +1.5% | +1.4% |

Positive direction is consistently higher. The gap is ~15% at the lowest
speeds, 2–4% through 0.225 rad/s, and ≤1.5% at ≥0.338 rad/s. The measured
speed at the 0.010 rad/s command was 0.011 (+) and 0.0092 (−) rad/s.
This morning's low-speed disagreement had no consistent sign.

## Breakaway current

0→3 A current ramps at 1, 3.3, 10, 33, 100 A/s (3000/909/300/91/30 ms),
5 trials × 2 directions, stride 4, `run-ramp.sh torque`, directions
alternated with ≥4 s rest. Detected with `scripts/txf-breakaway.py`,
threshold 0.05 rad/s `mvel_filt`, 3 samples. Baseline max |`mvel_filt`|
was ≤0.0017 rad/s in every ramp, so every trial started at rest. The threshold
is ~30× above that noise. 50/50 ramps detected breakaway; none ended first.

|breakaway| (A), mean ± σ (min–max):

| rate (A/s) | +dir | −dir | both |
|---|---|---|---|
| 1   | 1.336 ± 0.143 (1.253–1.590) | 1.314 ± 0.179 (1.126–1.586) | 1.325 ± 0.153 |
| 3.3 | 1.366 ± 0.240 (0.948–1.541) | 1.509 ± 0.245 (1.229–1.794) | 1.437 ± 0.241 |
| 10  | 1.474 ± 0.229 (1.110–1.653) | 1.543 ± 0.207 (1.240–1.786) | 1.509 ± 0.209 |
| 33  | 1.318 ± 0.157 (1.162–1.533) | 1.312 ± 0.197 (1.096–1.516) | 1.315 ± 0.168 |
| 100 | 1.730 ± 0.080 (1.655–1.855) | 1.614 ± 0.103 (1.510–1.760) | 1.672 ± 0.106 |
| all | 1.445 ± 0.226 | 1.458 ± 0.216 | 1.452 ± 0.219 |

Individual trials (A, t1–t5):

| rate | +dir | −dir |
|---|---|---|
| 1   | 1.253 1.590 1.297 1.273 1.265 | 1.379 1.285 1.586 1.194 1.126 |
| 3.3 | 0.948 1.386 1.541 1.473 1.480 | 1.229 1.418 1.368 1.794 1.736 |
| 10  | 1.653 1.110 1.385 1.629 1.592 | 1.786 1.542 1.240 1.672 1.478 |
| 33  | 1.429 1.533 1.213 1.251 1.162 | 1.273 1.096 1.516 1.157 1.516 |
| 100 | 1.740 1.655 1.855 1.665 1.735 | 1.610 1.510 1.525 1.760 1.665 |

**Breakaway current ≈ 1.40 A** (both directions, 1–33 A/s, σ 0.21 A).
The mean over all rates is 1.45 A. The mean directional difference is 0.01 A.
Across 1–33 A/s, trial scatter (σ 0.15–0.25 A) exceeds any consistent rate
trend.

At 100 A/s the value rises to ~1.67 A. As in the morning session, this is
most likely detection latency. At a 0.02 rad/s threshold, 100 A/s gives
1.09 A, within the 0.92–1.17 A spread of the other rates.

Identification limit: the result is threshold-sensitive. The overall mean is
1.05 A at 0.02 rad/s versus 1.45 A at 0.05 rad/s. Onset is gradual creep, so
breakaway current is defined only relative to the 0.05 rad/s threshold,
which matches earlier j1 reports.

**2 A step** (5 per direction, 1000 ms hold, stride 4): 10/10 broke away,
detected 3.6–4.0 ms after the step. 2 A exceeds breakaway in both directions;
no failures to record. Stride 4 was used because a stride-1 1000 ms capture
exceeds the RTT link's throughput.

**Omitted:** 0.1 and 0.33 A/s ramps. A 0→3 A ramp takes 30 s and 9.1 s,
beyond the ~3.27 s signal-engine timeline limit.

## Comparison with the morning run (same day, same joint)

| Parameter | morning | B | Δ |
|---|---|---|---|
| Ic (≥0.338 rad/s) | 1.190 ± 0.014 A | 1.242 ± 0.019 A | +0.052 |
| sig2 (≥0.338 rad/s) | 1.144 ± 0.022 | 1.066 ± 0.029 | −0.078 |
| breakaway, all rates @0.05 | 1.29 A | 1.45 A | +0.16 |
| breakaway, 1–33 A/s @0.05 | 1.17–1.30 A per rate | 1.32–1.51 A per rate | ~+0.15 |

The Ic and sig2 shifts exceed their fit uncertainties but largely offset in
the fitted range. Predicted current differs by ≤0.03 A over 0.34–0.88 rad/s,
comparable to the residuals. Breakaway rose by about 0.15 A in both
directions. The cause is not identified; thermal state was not recorded for
either run, and the 2026-09-22 j1 dual run-in showed that friction on
this joint is temperature-sensitive.

## Summary

| Parameter | Value | Status |
|---|---|---|
| Ic | 1.24 ± 0.02 A | tuned (holds ≥0.338 rad/s) |
| sig2 | 1.07 ± 0.03 A/(rad/s) | tuned (holds ≥0.338 rad/s) |
| breakaway | 1.40 ± 0.21 A (σ of trials, 1–33 A/s) | at 0.05 rad/s threshold; threshold-dependent |
| Is | 1.646 A | fixed input, not fit |
| stribeck_vel | 0.170 rad/s | fixed input, not fit |

Parameters are not written to the joint.

## Captures

`traces/friction/j1-post-tighten-B/`:
- `vhold.{pos,neg}_<speed>.0000.txf` — 26 velocity holds
- `tramp.r<rate>.{pos,neg}.t<1-5>.0000.txf` — 50 current ramps
- `tstep.2a.{pos,neg}.t<1-5>.0000.txf` — 10 current steps
