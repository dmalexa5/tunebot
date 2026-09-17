# j0 friction identification — 2026-09-17 (100.106.65.65 session)

A concurrent session ran the same workflow against `100.79.218.29` in
parallel with this one and wrote its results to `reports/tune-friction-j0.md`
(directory `traces/friction/j0-david-09.17A-friction/`). This report covers
this session's independent run against `100.106.65.65` and does not modify
that file.

## Conditions

- Target: `100.106.65.65`, j0, no arm attached (bare joint bench setup).
- OpenOCD/RTT server already running (`-r` omitted on all calls). `GHASH`
  read back `194203904`.
- On connect, live gains were `VEL_KP≈3.0, VEL_KI≈0.075, POS_KP=20,
  POS_KI=0.15` — not the chatter session's tuned values, consistent with the
  volatile `Jx_CFG WRITE` gains having reset on a reboot/reconnect rather than
  a different physical board. Wrote and verified the `tune-chatter-j0.md`
  final gains: `VEL_KP=12.0 VEL_KI=0.3 POS_KP=60.0 POS_KI=0.15
  VEL_TQC_LIM=5.0 POS_VEL_LIM=π` (`Jx_CFG` reads matched exactly).
- Verified with one 1 Hz / 0.138 rad position-sine capture
  (`gainverify.0000.txf`): err rms 9.798 mrad (7.10%), jitter 125.8 mA/samp —
  consistent with the chatter report's 1 Hz result (9.747 mrad, 7.06%,
  153.7 mA), confirming the gains are controlling the loop as expected.
- Friction compensation confirmed disabled (`Jx_STATUS` flags carried only
  `WARN_OV`, a sticky bus-overvoltage warning cleared by the read — not a
  fault, no `FEATURE_FRIC_COMP` bit present); `-F` not used on any capture.
  `iq_fric` spot-checked as identically zero.
- Motor sensor source: `mvel_filt` (firmware-filtered motor-derived velocity,
  sign-corrected, output-shaft rad/s) and `iq_fbk` (A). No gear-ratio
  conversion applied (channel is already output-referred).
- Captures: `traces/friction/j0-dario-09.17A-friction/`.

## Steady-state map: Ic, Is, stribeck_vel, sig2

13 commanded speed magnitudes × 2 directions, 1000 ms holds, stride 12
(default), via `run-step.sh -i 100.106.65.65 vel <±step> 1000 0 12 vhold`:
0.010, 0.015, 0.022, 0.033, 0.050, 0.075, 0.100, 0.150, 0.225, 0.338,
0.507, 0.760, 0.875 rad/s. All 26 captures succeeded (no overflow/truncation).
Fit with `scripts/fit_stribeck.py` (300 ms settle skip; mean `mvel_filt`,
direction-aligned `iq_fbk`).

**Fit result:**

| Param | Value | Unit |
|---|---|---|
| Ic | 1.310 | A |
| Is | 1.470 | A |
| stribeck_vel | 0.151 | rad/s |
| sig2 | 1.101 | A/(rad/s) |

resnorm = 0.0776 A² over 26 points; residuals range −0.106 to +0.163 A,
comparable in size to the Ic/Is gap itself (0.160 A). **The Stribeck knee is
only weakly identified by this data** — treat `Is-Ic` and `stribeck_vel` as
poorly constrained rather than resolved; `sig2` (viscous slope, ~1.1 A per
rad/s from 0.01 to 0.875 rad/s) is the more solid number here. The
concurrent 100.79.218.29 session found similar values (Ic 1.62 A, Is 1.82 A,
sig2 1.12 A/(rad/s)) — close enough to be plausible session-to-session
variation rather than a contradiction, though not identical.

**Direction agreement** (matched-magnitude ± pairs, current magnitude only,
in capture order):

| \|w\| (rad/s) | I+ (A) | I− (A) | diff (A) | rel % |
|---|---|---|---|---|
| 0.0100 | 1.585 | 1.316 | +0.269 | +18.5% |
| 0.0149 | 1.488 | 1.522 | −0.034 | −2.2% |
| 0.0219 | 1.519 | 1.449 | +0.071 | +4.8% |
| **0.0329** | **1.592** | **1.440** | **+0.152** | **+10.0%** |
| **0.0500** | **1.603** | **1.429** | **+0.173** | **+11.4%** |
| 0.0749 | 1.551 | 1.449 | +0.102 | +6.8% |
| 0.1000 | 1.547 | 1.514 | +0.033 | +2.2% |
| 0.1500 | 1.505 | 1.558 | −0.053 | −3.4% |
| 0.2251 | 1.584 | 1.571 | +0.013 | +0.8% |
| 0.3379 | 1.698 | 1.669 | +0.029 | +1.7% |
| 0.5070 | 1.866 | 1.866 | +0.000 | +0.0% |
| 0.7600 | 2.146 | 2.140 | +0.006 | +0.3% |
| 0.8749 | 2.278 | 2.273 | +0.005 | +0.2% |

Largest disagreement at 0.01-0.05 rad/s (up to 18.5%, positive direction
reading higher), tapering to <2% above ~0.1 rad/s — reported here rather than
absorbed into the symmetric fit.

## Presliding (sig0, sig1)

0-to-3 A current ramps at 1, 3.3, 10, 33, 100 A/s, 5 trials per rate in both
directions (50 captures total), via `run-ramp.sh -i 100.106.65.65 torque
<±3> <duration_ms> 0 4 cramp_<rate>` — **stride 4**, not the torque default
of 1, per this project's throughput limit (stride 2 truncates the `TRACE=MECH`
stream on this link). All 50 captures completed with no overflow/truncation.
Rates 0.1 and 0.33 A/s were omitted: at 3 A they would need 30 s / 9.1 s
ramps, exceeding the 65534-tick (~3.27 s) signal-engine timeline.

Also captured a 0-to-2 A torque step in both directions
(`cstep.0000/0001.txf`) as a coarse breakaway check: both directions broke
away almost immediately (6-7 ms in), i.e. 2 A is well above breakaway —
consistent with the steady-state `Ic≈1.31 A`, not itself a presliding data
point (the step transitions through the presliding regime too fast to
resolve it; that's why the main test uses slow current ramps).

Breakaway detected via `scripts/txf-breakaway.py` (threshold 0.05 rad/s,
3-sample sustain — baseline `mvel_filt` noise measured at ~0.0002 rad/s, well
below threshold) on every one of the 50 ramp captures; pre-breakaway segments
exported to `traces/friction/j0-dario-09.17A-friction/presliding/*.csv`.

**Breakaway current by loading rate** (mean ± population std, n=10/rate):

| Rate (A/s) | Breakaway I (A) | Breakaway t (ms) |
|---|---|---|
| 1.00 | 1.517 ± 0.086 | 1517 |
| 3.30 | 1.621 ± 0.093 | 491 |
| 9.99 | 1.593 ± 0.171 | 159 |
| 32.90 | 1.731 ± 0.140 | 52 |
| 99.34 | 2.078 ± 0.060 | 21 |

Breakaway current rises with loading rate (1.52 A at 1 A/s to 2.08 A at
~100 A/s) — qualitatively the expected LuGre/presliding-stiffness signature
(faster loading gives less time for bristle deflection to reach the
Stribeck-limited steady value, so it takes more current to trigger
breakaway). The concurrent 100.79.218.29 session saw the same rising trend
at somewhat higher absolute currents (~2.1 A to ~2.5 A).

**LuGre fit — sig0/sig1 unidentified.** Fit `scripts/lugre_predict.m` against
all 50 presliding segments via `lsqnonlin`, holding `Ic/Is/stribeck_vel/sig2`
fixed at the steady-state values above (per skill guidance, not using
`fit_lugre_joint.m`'s joint sig2 refit — see `fit_sig0sig1.m`/
`fit_sig0sig1_scan.m`/`fit_sig0sig1_perrate.m` in this session's scratchpad).
The global fit across all rates converges robustly to the same point from six
different starting values (`sig0≈632.6 A/rad, sig1≈65.0 A/(rad/s)`), but with
a large residual (resnorm 32876 over 112081 samples, rms 0.54 A — 25-40% of
the breakaway currents being fit). Refitting **per rate group separately**
shows why: fitted `sig0` is not rate-invariant — it swings more than an
order of magnitude with loading rate instead of holding constant:

| Rate | sig0 (A/rad) | sig1 (A/(rad/s)) | fit rms (A) |
|---|---|---|---|
| 1 A/s | 521 | 99.4 | 0.586 |
| 3.3 A/s | 1745 | 96.3 | 0.357 |
| 10 A/s | 5137 | 69.5 | 0.247 |
| 33 A/s | 7897 | 54.5 | 0.179 |
| 100 A/s | 8587 | 72.5 | 0.205 |

A single-state LuGre model with these fixed steady-state parameters cannot
reconcile all five rates with one `sig0`/`sig1` pair. **Report sig0 and sig1
as unidentified** — the rate-dependent breakaway-current trend above is real
and worth keeping, but no single presliding-stiffness/damping value from this
fit should be treated as the joint's `sig0`/`sig1`. (The concurrent
100.79.218.29 session reached the same "unidentified" conclusion via a
different argument: a single monotonic ramp can't separate sig0 from sig1
without reversal/dither excitation.)

## Captures

`traces/friction/j0-dario-09.17A-friction/`:
- `gainverify.0000.txf` — 1 Hz / 0.138 rad position-sine gain check
- `vhold.0000.txf`-`vhold.0025.txf` — steady-state velocity holds (magnitude/
  sign order: 0.010+, 0.010−, 0.015+, 0.015−, ... 0.875+, 0.875−)
- `cstep.0000.txf`/`cstep.0001.txf` — 0-to-2 A torque step, +/−
- `cramp_r01.0000-0009.txf`, `cramp_r03p3.0000-0009.txf`,
  `cramp_r10.0000-0009.txf`, `cramp_r33.0000-0009.txf`,
  `cramp_r100.0000-0009.txf` — presliding current ramps, 5 trials alternating
  +/− per rate
- `presliding/cramp_*.csv` — exported pre-breakaway (t, w, iq) segments used
  for the LuGre fit
