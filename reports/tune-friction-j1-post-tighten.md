# j1 friction tuning, post-tighten — 2026-09-25

Scope: `Ic`, `sig2`, breakaway current. `Is`, `stribeck_vel`, `sig0`, `sig1`
held fixed and not fit.

## Conditions

- Target `100.79.218.29`, j1 (vokcap), unloaded, cold at start (per user).
  OpenOCD and RTT server already running; `-r` not used.
- Gains read 0 at start; applied `gains/drive-gains.json` joint 1:
  `VEL_KP=8.0 VEL_KI=0.1 POS_KP=60 POS_KI=3.0 VEL_TQC_LIM=5.0 POS_VEL_LIM=π`.
  Readback matched (vel gains in raw counts domain).
- Live friction config (not changed): `FRIC_IC=1.4625 A`, `FRIC_IS=1.646 A`,
  `FRIC_SIGMA2=1.1095 A/(rad/s)`, `FRIC_VS=0.170 rad/s`, `FRIC_SRC=2`,
  `FRIC_LPF=1`, `SERVO_FLAGS=0`.
- Friction input: recorded `mvel_filt` (filtered motor velocity,
  sign-corrected, output-shaft rad/s; no gear-ratio conversion) and `iq_fbk` (A).
- Compensation off (no `-F`); `iq_fric` max |value| = 0 in every capture.
- Captures: `traces/friction/j1-post-tighten/`. No overflow or truncation
  (all record counts at the expected length).

## Steady-state map: Ic, sig2

26 velocity holds, ±{0.010 … 0.875} rad/s (13 magnitudes), 1000 ms, stride 12,
`run-step.sh vel`. Analyzed with `scripts/fit_stribeck.py` (300 ms settle).

Fixed inputs: `Is = 1.646 A`, `stribeck_vel = 0.170 rad/s` (live config).

| Fit | Ic (A) | sig2 (A/(rad/s)) | rms resid (A) |
|---|---|---|---|
| **Holds ≥0.338 rad/s (8 pts), fixed Is/vs** | **1.190 ± 0.014** | **1.144 ± 0.022** | 0.011 |
| — positive only | 1.207 ± 0.027 | 1.118 ± 0.041 | 0.012 |
| — negative only | 1.174 ± 0.014 | 1.170 ± 0.022 | 0.006 |
| All 26 holds, fixed Is/vs | 1.02 ± 0.24 | 1.33 ± 0.40 | 0.29 |

Uncertainties are 1σ from the least-squares covariance.

**Recommended: `Ic = 1.19 A`, `sig2 = 1.14 A/(rad/s)`** (the ≥0.338 rad/s
fit). In that speed range the fixed Stribeck term is <2% of `Is − Ic`, so the
result barely depends on the fixed `Is`/`stribeck_vel`.

Identification limit: the all-holds fit is not usable. Every hold below
0.15 rad/s measured 1.20–1.34 A, below the fixed `Is = 1.646 A`, and current
rises steadily from the lowest speed. There is no Stribeck peak or knee in
this data. With `Is`/`stribeck_vel` held fixed, the model misses the low-speed
holds by −0.3 to −0.45 A. That drags `Ic` down, leaves it loosely constrained,
and pushes `sig2` up. Including the 0.225 rad/s pair already shifts the
estimate (`Ic` 1.13, `sig2` 1.23). The free 4-parameter fit, shown only as a
cross-check and not adopted, gives `Ic 1.197, Is 1.237, vs 0.159, sig2 1.136`,
consistent with the high-speed estimate.

Directional agreement (retained `signed_w`/`signed_I` pairs, |I+| vs |I−|):

| |w| (rad/s) | 0.010 | 0.015 | 0.022 | 0.033 | 0.050 | 0.075 | 0.100 | 0.150 | 0.225 | 0.338 | 0.507 | 0.760 | 0.875 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I+ (A) | 1.204 | 1.205 | 1.251 | 1.333 | 1.343 | 1.302 | 1.338 | 1.426 | 1.473 | 1.580 | 1.791 | 2.055 | 2.176 |
| \|I−\| (A) | 1.252 | 1.335 | 1.291 | 1.211 | 1.223 | 1.338 | 1.319 | 1.366 | 1.423 | 1.573 | 1.769 | 2.069 | 2.186 |
| Δ | −3.9% | −10.3% | −3.1% | +9.5% | +9.4% | −2.7% | +1.4% | +4.3% | +3.5% | +0.4% | +1.3% | −0.7% | −0.5% |

Below 0.075 rad/s the directions disagree by up to ±10%, with no consistent
sign. At ≥0.338 rad/s they agree within 1.3%.

## Breakaway current

0→3 A current ramps at 1, 3.3, 10, 33, 100 A/s (3000/909/300/91/30 ms),
5 trials × 2 directions, stride 4, `run-ramp.sh torque`, directions
alternated with ≥4 s rest. Detected with `scripts/txf-breakaway.py`,
threshold 0.05 rad/s `mvel_filt`, 3 samples. Baseline noise: max
|`mvel_filt`| 0.0016 rad/s (worst σ 0.0004) across all 60 captures, so every
trial started at rest and the threshold is ~30× above noise. 50/50 ramps
detected breakaway; none ended first.

|breakaway| (A), mean ± σ (min–max):

| rate (A/s) | +dir | −dir | both |
|---|---|---|---|
| 1   | 1.293 ± 0.108 (1.148–1.430) | 1.310 ± 0.325 (0.829–1.611) | 1.301 ± 0.228 |
| 3.3 | 1.276 ± 0.140 (1.122–1.412) | 1.243 ± 0.235 (1.035–1.586) | 1.260 ± 0.183 |
| 10  | 1.139 ± 0.217 (0.927–1.383) | 1.203 ± 0.132 (0.979–1.309) | 1.171 ± 0.173 |
| 33  | 1.214 ± 0.188 (0.902–1.380) | 1.204 ± 0.149 (1.053–1.421) | 1.209 ± 0.160 |
| 100 | 1.499 ± 0.092 (1.380–1.625) | 1.509 ± 0.139 (1.385–1.690) | 1.504 ± 0.111 |
| all | 1.284 ± 0.188 | 1.294 ± 0.224 | — |

Individual trials (A, t1–t5):

| rate | +dir | −dir |
|---|---|---|
| 1   | 1.274 1.364 1.148 1.250 1.430 | 1.583 1.163 0.829 1.363 1.612 |
| 3.3 | 1.122 1.412 1.324 1.393 1.132 | 1.063 1.382 1.586 1.035 1.149 |
| 10  | 1.348 1.383 0.939 0.927 1.101 | 1.283 1.247 1.200 1.309 0.979 |
| 33  | 1.309 1.380 0.902 1.297 1.180 | 1.053 1.096 1.167 1.284 1.421 |
| 100 | 1.515 1.530 1.445 1.625 1.380 | 1.410 1.385 1.625 1.690 1.435 |

**Breakaway current ≈ 1.29 A** (both directions, 1–100 A/s). Across
1–33 A/s it is 1.17–1.30 A. There is no directional difference (0.01 A);
trial-to-trial scatter (σ 0.1–0.3 A) exceeds any rate trend there.

At 100 A/s the value rises to ~1.50 A. That rise is most likely detection
latency, not a real rate effect. At 100 A/s the command climbs ~0.1 A per ms
while the rotor accelerates to 0.05 rad/s. With a 0.02 rad/s threshold the
100 A/s mean drops to 0.99 A, in line with the other rates (0.79–0.98 A).

Identification limit: the detected value depends strongly on the threshold.
At 0.02 rad/s the overall mean is ~0.92 A versus 1.29 A at 0.05. Onset is
gradual creep rather than a sharp release, so breakaway current is defined
only relative to the 0.05 rad/s threshold. The 0.05 rad/s value is the one
comparable with earlier j1 reports.

**2 A step** (5 per direction, 1000 ms hold): 10/10 broke away, detected
3.6–4.0 ms after the step. 2 A exceeds breakaway in both directions; no
failures to record.

**Omitted:** 0.1 and 0.33 A/s ramps. A 0→3 A ramp takes 30 s and 9.1 s,
beyond the ~3.27 s signal-engine timeline limit.

## Comparison with the earlier vokcap j1 sessions (2026-09-21/22)

This is context only; the earlier `Ic` values came from free 4-parameter
fits. The free-fit `Ic` fell from 1.53–1.54 A to 1.20 A. `sig2` (1.14) sits
between the earlier 1.09 and 1.33. Mean breakaway at 0.05 rad/s dropped from
1.36 A to 1.29 A, using a different rate set (1–80 A/s before). Hardware
metadata (cap/housing/rotor/…) was not recorded for this session.

## Summary

| Parameter | Value | Status |
|---|---|---|
| Ic | 1.19 ± 0.01 A | tuned (holds ≥0.338 rad/s) |
| sig2 | 1.14 ± 0.02 A/(rad/s) | tuned (holds ≥0.338 rad/s) |
| breakaway | 1.29 ± 0.21 A (σ of trials) | at 0.05 rad/s threshold; threshold-dependent |
| Is | 1.646 A | fixed input, not fit |
| stribeck_vel | 0.170 rad/s | fixed input, not fit |

Parameters are not written to the joint.

## Captures

`traces/friction/j1-post-tighten/`:
- `vhold.{pos,neg}_<speed>.0000.txf` — 26 velocity holds
- `tramp.r<rate>.{pos,neg}.t<1-5>.0000.txf` — 50 current ramps
- `tstep.2a.{pos,neg}.t<1-5>.0000.txf` — 10 current steps
