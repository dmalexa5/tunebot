# j0 friction identification — 2026-09-17

## Conditions

- Target: `100.79.218.29`, j0, no arm attached (bare joint bench setup).
- OpenOCD/RTT server already running (`-r` omitted on all calls). GHASH read
  back `194203904`; `Jx_CFG` reads matched the chatter session's final gains
  exactly (`VEL_KP=12.0, VEL_KI=0.3, POS_KP=60, POS_KI=0.15, VEL_TQC_LIM=5.0,
  POS_VEL_LIM=π`) — see `reports/tune-chatter-j0.md`.
- Friction compensation confirmed disabled (`Jx_STATUS` flags: `[]`); `-F` not
  used on any capture. `iq_fric` spot-checked as identically zero in
  `vhold.0000.txf` and `vhold.0024.txf`.
- Motor sensor source: `mvel_filt` (firmware-filtered motor-derived velocity,
  sign-corrected, output-shaft rad/s) and `iq_fbk` (A). No gear-ratio
  conversion applied (channel is already output-referred).
- Captures: `traces/friction/j0-2026-09-17/`.

## Steady-state map: Ic, Is, stribeck_vel, sig2

13 commanded speed magnitudes × 2 directions, 1000 ms holds, stride 12
(default), via `run-step.sh -i 100.79.218.29 vel <±step> 1000 0 12 vhold`:
0.010, 0.015, 0.022, 0.033, 0.050, 0.075, 0.100, 0.150, 0.225, 0.338,
0.507, 0.760, 0.875 rad/s. All 26 captures succeeded (no overflow/truncation).
Fit with `scripts/fit_stribeck.py` (300 ms settle skip; mean `mvel_filt`,
direction-aligned `iq_fbk`).

**Fit result:**

| Param | Value | Unit |
|---|---|---|
| Ic | 1.615 | A |
| Is | 1.822 | A |
| stribeck_vel | 0.189 | rad/s |
| sig2 | 1.118 | A/(rad/s) |

resnorm (sum of squared residuals) = 0.159 A² over 26 points; residuals
range ±0.25 A, comparable in size to the Ic/Is gap itself (0.21 A). **The
Stribeck knee is only weakly identified by this data** — treat `Is-Ic` and
`stribeck_vel` as poorly constrained rather than resolved; `sig2` (viscous
slope, ~1.1 A per rad/s of speed increase from 0.01 to 0.875 rad/s) is the
more solid number here.

**Direction agreement** (matched-magnitude ± pairs, current magnitude only):

| \|w\| (rad/s) | I+ (A) | I− (A) | diff (A) | rel % |
|---|---|---|---|---|
| 0.0100 | 1.705 | 1.725 | −0.019 | −1.1% |
| 0.0148 | 1.748 | 1.836 | −0.089 | −5.0% |
| 0.0217 | 1.941 | 1.831 | 0.111 | 5.9% |
| **0.0329** | **2.098** | **1.800** | **0.298** | **15.3%** |
| **0.0501** | **2.024** | **1.802** | **0.222** | **11.6%** |
| 0.0751 | 1.865 | 1.856 | 0.009 | 0.5% |
| 0.0999 | 1.904 | 1.854 | 0.050 | 2.7% |
| 0.1500 | 1.942 | 1.839 | 0.103 | 5.5% |
| 0.2252 | 1.934 | 1.870 | 0.064 | 3.4% |
| 0.3380 | 2.044 | 2.007 | 0.037 | 1.8% |
| 0.5070 | 2.192 | 2.153 | 0.039 | 1.8% |
| 0.7599 | 2.505 | 2.423 | 0.082 | 3.3% |
| 0.8750 | 2.642 | 2.544 | 0.098 | 3.8% |

Most pairs agree within ~1-6%, but 0.033 and 0.050 rad/s show 12-15%
disagreement (positive direction reading higher) — reported here rather than
absorbed silently into the symmetric fit. No other systematic asymmetry
pattern is evident (sign flips above and below that pair).

## Captures

`traces/friction/j0-2026-09-17/`: `vhold.0000.txf`-`vhold.0025.txf`
(velocity magnitude/sign order: 0.010+, 0.010−, 0.015+, 0.015−, ... 0.875+,
0.875−).

## Presliding (sig0)

0-to-3 A current ramps (torque mode, `-F` not used) at 1, 3.3, 10, 33, and
100 A/s, 5 trials per rate per direction (50 captures total), via
`run-ramp.sh -i 100.79.218.29 torque <±3> <duration_ms> 0 4 tramp_<rate>_<dir>`.
**Stride 4 used explicitly** (not the script's torque default of 1) — a
prior session on this same link measured stride-2 truncation of the 11-field
mech trace; see memory `rtt-capture-throughput-limit`. All 50 captures
completed with no truncation/overflow.

Rates 0.1 and 0.33 A/s (which would extend the log-spaced sweep downward)
**were not captured** — a 0-to-3 A ramp at those rates takes 30 s / 9.1 s,
far beyond the signal engine's ~3.27 s (65534-tick) timeline limit.

Breakaway detected with `scripts/txf-breakaway.py` at the default 0.05 rad/s
threshold (baseline `mvel_filt` noise measured from the steady-state
captures: std ≈ 0.0002 rad/s, max ≈ 0.0014 rad/s — comfortably below
threshold), sustain 3 samples. Every ramp trial cleanly showed breakaway
(no rejected/overflowed trials).

**Breakaway current vs. loading rate** (mean ± std over 5 trials/direction):

| rate (A/s) | +dir (A) | −dir (A) |
|---|---|---|
| 1 | 2.088 ± 0.086 | −2.107 ± 0.120 |
| 3.3 | 1.907 ± 0.109 | −1.980 ± 0.086 |
| 10 | 2.011 ± 0.134 | −2.047 ± 0.269 |
| 33 | 2.249 ± 0.279 | −2.291 ± 0.230 |
| 100 | 2.520 ± 0.287 | −2.522 ± 0.199 |

Breakaway current rises with loading rate (~2.1 A at 1 A/s to ~2.5 A at
100 A/s) with roughly symmetric magnitude between directions and growing
trial-to-trial spread at faster rates — a real rate-dependent effect, not
noise, but reported qualitatively rather than folded into a specific
parameter.

**2 A step check:** `run-step.sh -i 100.79.218.29 torque ±2 200 0 4 tstep_{p,n}`.
Both directions broke away almost immediately (within 6-7 ms of the step,
`iq`≈±2.0 A at breakaway) — **the 2 A step exceeds breakaway** on this joint
(consistent with the ~2.0-2.1 A breakaway current measured at slow ramp
rates above). Recorded as a failure per the skill's instruction rather than
treated as valid static presliding data; not used in any fit.

**sig0/sig1 fit — unidentified.** Fit `lugre_predict.m` (not
`fit_lugre_joint.m`, which refits sig2 — the skill says not to trust that
for viscous damping from presliding data alone) against the pre-breakaway
segments from all 50 ramp captures (149201 samples total), holding
Ic/Is/stribeck_vel/sig2 fixed at the steady-state values above:

- sig0 alone (sig1 fixed at 0): sig0 = 523 A/rad, resnorm = 1.71e5
- sig0 + sig1 jointly: sig0 = 267 A/rad, sig1 = 85.0 A/(rad/s), resnorm = 1.34e5

Both resnorms are large relative to signal: RMS residual ≈ 0.95-1.07 A
against `iq` with std 1.20 A, i.e. the model explains only ~20-40% of the
variance versus predicting zero (baseline resnorm 2.16e5) or `sig2*w` alone
(2.14e5, essentially no better than zero since `w` stays under 0.05 rad/s
throughout every pre-breakaway window by construction). Adding sig1 shifts
the sig0 point estimate by ~2× — a single monotonic current ramp to
breakaway, with no reversal, does not constrain sig0 independently of sig1
in this fit. **Reporting sig0 and sig1 as unidentified** from this
presliding data; the numbers above are the fit's unstable point estimates,
not physical parameter values. Identifying them would need reversing/dither
excitation within the presliding regime (the "Test 3 dither" referenced in
`fit_lugre_joint.m`'s docstring), which this session did not capture.

## Captures

`traces/friction/j0-david-09.17A-friction/`:
- `vhold.0000.txf`-`vhold.0025.txf` — steady-state velocity holds
- `tramp_{r01,r03p3,r10,r33,r100}_{p,n}.000{0-4}.txf` — presliding ramps (50)
- `tstep_{p,n}.0000.txf` — 2 A breakaway check
- `presliding_csv/*.csv` — pre-breakaway (t, w, iq) segments used in the sig0/sig1 fit attempt
- `fit_sig0.m` — the fitting script used above
