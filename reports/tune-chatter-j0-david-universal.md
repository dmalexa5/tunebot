# j0 chatter tuning, universal arm attached — 2026-09-18

Follow-on to [tune-chatter-j0-david.md](tune-chatter-j0-david.md), which tuned
j0 bare (no arm) and left it at `VEL_KP=6.5 VEL_KI=0.05 POS_KP=40.0
POS_KI=0.6`. This session attaches the universal arm and re-tunes the full
cascade against that report's final gains as the seed, per user direction.

## Conditions

- Target: `100.79.218.29`, j0, **universal arm attached**.
- OpenOCD and the RTT server (`rttlog -r`) already running; `-r` omitted on
  all `run-sine.sh`/`set-gains.sh` calls.
- Friction compensation confirmed disabled (`Jx_STATUS` flags `[]` at session
  start); `-F` not used anywhere.
- Position sines at 0.138 rad amplitude, stride 20 (default for `pos`).
  Command amplitude verified at 137.998 mrad (138.034 at 0.75 Hz) on every
  capture; no truncated captures.
- `VEL_TQC_LIM = 5.0 A` and `POS_VEL_LIM = π rad/s` held fixed throughout.
- Search captures: 3 cycles at 1 Hz, 1 cycle at 0.5 Hz (the stride-20 timeline
  cap).
- Captures: `traces/chatter/j0-david-universal/`.

## Baseline

Live gains read 0 over RTT at session start (RAM-only, expected — no
persistence across firmware restart). `VEL_TQC_LIM` read back `12` and
`POS_VEL_LIM` was stale before the baseline write.

Seeded from the bare-joint report's *final* gains, per explicit user
direction (`reports/tune-chatter-j0-david.md`), **not** from either the bare
report's methodology output being assumed valid here, and not from
`cn-seamless/configs/tunables/drive-gains.json`'s untuned universal defaults
(`VEL_KP=24, VEL_KI=0.6, POS_KP=60, POS_KI=0.15` — same limits, different PI
values):

`VEL_KP=6.5  VEL_KI=0.05  POS_KP=40.0  POS_KI=0.6  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

This baseline was captured fresh against the loaded joint, not copied from the
bare-joint report — the arm's added inertia changes the dynamics enough that
the old numbers cannot be assumed to transfer:

| freq | jitter | err rms |
|---|---|---|
| 0.5 Hz | 133.5 mA | 43.478 mrad (31.51%) |
| 0.75 Hz | 128.0 mA | 49.934 mrad (36.17%) |
| 1 Hz | 100.0 mA | 118.306 mrad (85.73%), gain +4.67 dB |

**This baseline is not a functioning control loop.** Feedback amplitude
*exceeds* command amplitude at all three frequencies (gain > 1, i.e.
amplification rather than tracking), and 1 Hz error is 86% of command
amplitude. The bare-joint gains are far too soft for the arm's added inertia
— this session is primarily a stability recovery, not a jitter-vs-accuracy
trade against a working baseline. Jitter numbers from this baseline are not
meaningful comparators for that reason: a loop that isn't tracking chatters
less because it isn't doing much work.

## Search

Jitter in mA/samp, error as rms mrad (% of command amplitude). One gain
varied at a time, others held at their best tested values.

### 1. `VEL_KP`, with `VEL_KI=0.05`, `POS=(40, 0.6)`

| VEL_KP | 1 Hz jit | 1 Hz err | 0.5 Hz jit | 0.5 Hz err |
|---|---|---|---|---|
| 6.5 (baseline) | 100.0 | 85.73% | 133.5 | 31.51% |
| 10 | 105.1 | 49.19% | 151.9 | 10.28% |
| 15 | 142.8 | 23.87% | 177.4 | 3.26% |
| **20** | **197.6** | **9.61%** | **212.3** | **4.13%** |
| 24 | 216.9 | 7.69% | 248.0 | 3.32% |
| 30 | 281.3 | 7.02% | 302.2 | 3.26% |
| 36 | 330.7 | 6.06% | 366.9 | 3.27% |

No interior minimum — `VEL_KP` alone trades jitter against tracking error,
monotonically in both directions, with diminishing error returns above ~24
and a roughly linear jitter cost throughout. Unlike the bare-joint session,
raising `VEL_KP` from the seed value is what recovers a working loop at all;
6.5 was never a candidate to keep.

### 2. `VEL_KI`, with `VEL_KP=20`, `POS=(40, 0.6)`

| VEL_KI | 1 Hz jit | 1 Hz err | 0.5 Hz jit | 0.5 Hz err |
|---|---|---|---|---|
| 0.0 | 242.6 | 7.33% | 258.7 | 3.44% |
| 0.02 | 236.1 | 6.69% | 266.5 | 3.97% |
| 0.03 | 261.5 | 7.56% | 267.4 | 3.56% |
| **0.05** | **197.6** | **9.61%** | **212.3** | **4.13%** |
| 0.1 | 157.7 | 26.62% | 208.1 | 15.62% |
| 0.2 | 145.9 | 40.68% | 184.4 | 28.14% |
| 0.3 | 165.7 | 40.85% | 201.5 | 29.27% |
| 0.6 | 163.8 | 51.38% | 242.3 | 30.37% |

At `POS_KP=40` (below the position-loop cliff found in step 4), raising
`VEL_KI` above 0.05 collapses tracking badly — this is instability onset, not
a normal jitter/accuracy trade. 0.05 sits at a local jitter minimum among the
low values tested here; the true picture only clarifies after `POS_KP` moves
past the cliff (step 6 recheck).

### 3. `POS_KP`, with `VEL=(20, 0.05)`, `POS_KI=0.6`

| POS_KP | 1 Hz jit | 1 Hz err | 0.5 Hz jit | 0.5 Hz err |
|---|---|---|---|---|
| 30 | 152.8 | 48.38% | 251.5 | 4.48% |
| 35 | 177.1 | 22.00% | — | — |
| **40** | **197.6** | **9.61%** | **212.3** | **4.13%** |
| 50 | 251.9 | 6.53% | 275.2 | 3.22% |
| 60 | 264.0 | 5.23% | 276.5 | 3.59% |
| 80 | 263.8 | 5.20% | 280.2 | 3.17% |

A sharp cliff between `POS_KP=35` and `40` at 1 Hz — reproduced on retest
(30 → 47.34%/65.33 mrad both times) — below which the loop is marginal at
1 Hz specifically (0.5 Hz stays fine down to 30). This is a stability
boundary from the arm's inertia, not measurement noise. Above the cliff,
`POS_KP` alone trades jitter for error monotonically with no interior
optimum, same shape as the bare-joint session's finding — `POS_KI` is again
the lever expected to break the trade.

### 4. `POS_KI`, with `VEL=(20, 0.05)`, `POS_KP=60`

| POS_KI | 1 Hz jit | 1 Hz err | 0.5 Hz jit | 0.5 Hz err |
|---|---|---|---|---|
| 0.15 | 273.2 | 7.71% | 274.4 | 3.82% |
| 0.3 | 274.1 | 6.70% | 283.5 | 3.26% |
| 0.6 | 264.0 | 5.23% | 276.5 | 3.59% |
| 0.8 | 257.4 | 6.98% | 277.7 | 3.24% |
| **1.0** | **275.0** | **3.06%** | **281.1** | **3.37%** |
| 1.2 | 240.0 | 6.91% | 278.1 | 4.32% |
| 1.5 | 246.6 | 6.50% | 271.6 | 3.93% |
| 2.0 | 205.0 | 17.51% | 215.0 | 11.03% |

Jitter is flat (~240–285) from 0.15 to 1.5 — no meaningful jitter cost to
raising `POS_KI` in this range — while 1 Hz error bottoms sharply at 1.0
(3.06–3.74% across two repeat captures, plus 1.60% at a direct 0.75 Hz check)
before degrading again at 1.2/1.5 and collapsing at 2.0. Unlike the bare-joint
session's smoother `POS_KI` curve, this dip is narrow, so it was verified at
0.75 Hz and re-captured at 1 Hz to rule out a frequency-specific null — both
held up, confirming it generalizes rather than being an artifact of one test
frequency.

### 5. `POS_KP` recheck, with `VEL=(20, 0.05)`, `POS_KI=1.0`

| POS_KP | 1 Hz jit | 1 Hz err | 0.5 Hz jit | 0.5 Hz err |
|---|---|---|---|---|
| 40 | 170.1 | 21.25% | 266.8 | 4.40% |
| 50 | 257.4 | 6.46% | 286.8 | 3.29% |
| **60** | **270–275** | **3.06–3.74%** | **275–281** | **3.29–3.37%** |
| 80 | 271.7 | 3.54% | 301.4 | 2.91% |

The same cliff persists below ~50 at 1 Hz. 60 stays the corner: 80 buys
negligible error improvement for a jitter cost. `POS_KP` did not need to move
from step 3's value.

### 6. Velocity recheck, with `POS=(60, 1.0)`

| VEL_KP | 1 Hz jit | 1 Hz err | 0.5 Hz jit | 0.5 Hz err |
|---|---|---|---|---|
| 15 | 191.4 | 9.78% | 235.4 | 5.90% |
| 18 | 246.6 | 5.10% | 259.7 | 3.91% |
| **20** | **270–275** | **3.06–3.74%** | **275–281** | **3.29–3.37%** |
| 24 | 328.1 | 3.85% | 336.4 | 3.06% |

`VEL_KP=20` still gives the best error-for-jitter tradeoff; 18 buys ~9% lower
jitter at 1 Hz for a meaningfully worse error (5.10% vs. 3.06–3.74%) — not
preserved within the "don't regress tracking" constraint, so not taken. 24
raises jitter ~20% for negligible further error gain.

| VEL_KI @ `VEL_KP=20` | 1 Hz jit | 1 Hz err | 0.5 Hz jit | 0.5 Hz err |
|---|---|---|---|---|
| 0.0 | 267.0 | 4.42% | 292.9 | 2.96% |
| **0.02** | **252.0** | **3.85%** | **265.1** | **3.16%** |
| 0.03 | 270.7 | 4.10% | 279.5 | 3.51% |
| 0.05 | 270–275 | 3.06–3.74% | 275–281 | 3.29–3.37% |
| 0.08 | 257.0 | 6.66% | 284.6 | 3.51% |
| 0.12 | 209.4 | 14.69% | 295.7 | 3.52% |

Unlike the earlier `VEL_KI` sweep at `POS_KP=40` (step 2), which was
confounded by sitting below the position-loop cliff, this recheck past the
cliff shows a genuine U-shaped jitter minimum at `VEL_KI=0.02` — lower jitter
*and* comparable-or-better error than 0.05 on both frequencies. Took 0.02 as
final.

## Final gains

`VEL_KP=20.0  VEL_KI=0.02  POS_KP=60.0  POS_KI=1.0  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

Verified at 0.5, 0.75, and 1 Hz (1, 2, and 3 cycles; realized 0.75 Hz was
0.749991 Hz):

| freq | jitter | vs. this-session baseline | err rms | vs. this-session baseline |
|---|---|---|---|---|
| 0.5 Hz | 259.3 mA | +94.2% (was 133.5) | 4.646 mrad (3.37%) | −89.3% (was 43.478) |
| 0.75 Hz | 272.4 mA | +112.8% (was 128.0) | 2.214 mrad (1.60%) | −95.6% (was 49.934) |
| 1 Hz | 232.7 mA | +132.7% (was 100.0) | 5.949 mrad (4.31%) | −95.0% (was 118.306) |

Jitter is higher than the (non-functional) baseline at every frequency —
expected, since the baseline gains were too soft to actually resist the arm's
inertia rather than genuinely quiet. Tracking error dropped by ~89–96% at
every frequency and the loop now behaves as a proper closed loop (unity-ish
gain, sub-degree phase lag) instead of amplifying the command. Within the
stable operating region found in the search (`POS_KP` above the ~40–50
cliff), jitter bottomed out around 230–280 mA regardless of which stable
combination was tried — this appears to be the jitter floor for this loaded
joint, not an artifact of the particular final point chosen.

`Jx_STATUS` read `WARN_OV`/`WARN_OV_CLAMP` at the end of the session (same as
the bare-joint session) — live bus-voltage warnings from regen during the
unstable-region probes (`POS_KP<=35`, `VEL_KI>=0.1` at `POS_KP=40`,
`POS_KI=2.0`), not latched faults. Flags were `[]` at session start.

Universal arm was attached, so `../cn-seamless/configs/tunables/drive-gains.json`
joint 0 was updated: `VEL_KP` 24.0→20.0, `VEL_KI` 0.6→0.02, `POS_KP` unchanged
at 60.0, `POS_KI` 0.15→1.0. `VEL_TQC_LIM`/`POS_VEL_LIM` left unchanged (already
5.0/π). j0 was left at the final gains above.

## Captures

`traces/chatter/j0-david-universal/` (`-1hz` and `-0p5hz` per gain set unless
noted):

- `baseline-{1hz,0p5hz,0p75hz}` — seed gains (`VEL=6.5/0.05`, `POS=40/0.6`) on
  the loaded joint
- `vkp{10,15,17,20,24,30,36}` — `VEL_KP` sweep at `VEL_KI=0.05`, `POS=(40,0.6)`
- `vkp20-vki{0.0,0.02,0.03,0.1,0.2,0.3,0.6}` — `VEL_KI` sweep at `VEL_KP=20`,
  `POS=(40,0.6)`
- `pkp{30,35,50,60,80}`, `pkp30-retest` — `POS_KP` sweep at `VEL=(20,0.05)`,
  `POS_KI=0.6`
- `pki{0.15,0.3,0.6,0.8,1.0,1.2,1.5,2.0}`, `pki1.0-retest-1hz`, `pki1.0-0p75hz`
  — `POS_KI` sweep and generalization check at `VEL=(20,0.05)`, `POS_KP=60`
- `pkp{40,50,80}-pki1.0` — `POS_KP` recheck at `POS_KI=1.0`
- `re-vkp{15,18,24}` — `VEL_KP` recheck at `POS=(60,1.0)`
- `re-vkp20-vki{0.0,0.02,0.03,0.08,0.12}` — `VEL_KI` recheck at `VEL_KP=20`,
  `POS=(60,1.0)`
- `fin-pkp{50,70}` — final `POS_KP` recheck at `VEL=(20,0.02)`, `POS_KI=1.0`
- `final-{0p5hz,0p75hz,1hz}` — final-gain verification
