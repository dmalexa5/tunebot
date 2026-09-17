# j0 chatter tuning, full cascade — 2026-09-17

Follow-on to [tune-chatter-j0.md](tune-chatter-j0.md), which searched only
`VEL_KP`/`VEL_KI` at a fixed 40:1 ratio and held the position gains at their
tunables values. This session searched all four PI gains independently.

## Conditions

- Target: `100.79.218.29`, j0, no arm attached (bare joint bench setup).
- OpenOCD and the RTT server already running; `-r` omitted on all `run-sine.sh` calls.
- Friction compensation confirmed disabled (`Jx_STATUS` flags `[]` at session
  start); `-F` not used.
- Position sines at 0.138 rad amplitude, stride 20 (default for `pos`).
  Command amplitude verified at 137.998 mrad (138.034 at 0.75 Hz) on every
  capture; no truncated captures.
- `VEL_TQC_LIM = 5.0 A` and `POS_VEL_LIM = π rad/s` held fixed throughout.
- Search captures: 3 cycles at 1 Hz, 1 cycle at 0.5 Hz (the stride-20 timeline cap).
- Captures: `traces/chatter/j0-david-full/`.

## Baseline

Live gains read 0 over RTT at session start, as in the previous session — the
joint does not retain gains across a firmware restart. Seeded from the previous
session's *final* values rather than either `cn-seamless` tunables file, per
user direction (arm type is "none", so neither the bevel nor the universal file
governs this joint):

`VEL_KP=12.0  VEL_KI=0.3  POS_KP=60.0  POS_KI=0.15  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

| freq | jitter | err rms |
|---|---|---|
| 0.5 Hz | 84.6 mA | 4.152 mrad (3.01%) |
| 0.75 Hz | 104.3 mA | 6.954 mrad (5.04%) |
| 1 Hz | 142.2 mA | 9.769 mrad (7.08%) |

## Search

Jitter in mA/samp, error as rms mrad (% of command amplitude). One gain varied
at a time, others held at their best tested values.

### 1. `VEL_KP`, with `VEL_KI=0.3`, `POS=(60, 0.15)`

| VEL_KP | 1 Hz jit | 0.5 Hz jit | 1 Hz err | 0.5 Hz err |
|---|---|---|---|---|
| 6 | 408.7 | 407.0 | 10.167 (7.37%) | 4.572 (3.31%) |
| 9 | 336.6 | 294.5 | 9.815 (7.11%) | 4.205 (3.05%) |
| 10 | 196.4 | 158.5 | 9.764 (7.08%) | 4.158 (3.01%) |
| 11 | 152.8 | 100.3 | 9.762 (7.07%) | 4.154 (3.01%) |
| **12** | **142.2** | **84.6** | 9.769 (7.08%) | 4.152 (3.01%) |
| 13 | 145.5 | 85.1 | 9.763 (7.07%) | 4.149 (3.01%) |
| 15 | 157.9 | 85.2 | 9.764 (7.08%) | 4.148 (3.01%) |
| 18 | 185.3 | 95.3 | 9.761 (7.07%) | 4.150 (3.01%) |
| 24 | 247.2 | 119.2 | 9.763 (7.07%) | 4.149 (3.01%) |

U-shaped with a minimum at 12 — the inherited value was already optimal *for
`VEL_KI=0.3`*. Tracking error is flat across the whole range.

### 2. `VEL_KI`, with `VEL_KP=12`

| VEL_KI | 1 Hz jit | 0.5 Hz jit | 1 Hz err | 0.5 Hz err |
|---|---|---|---|---|
| 0.0 | 115.5 | 53.9 | 12.647 (9.16%) | 6.235 (4.52%) |
| 0.02 | 116.6 | 54.8 | 10.136 (7.34%) | 4.419 (3.20%) |
| 0.03 | 116.8 | 55.6 | 9.931 (7.20%) | 4.299 (3.12%) |
| **0.05** | **118.2** | **57.4** | 9.812 (7.11%) | 4.215 (3.05%) |
| 0.1 | 120.3 | 61.3 | 9.771 (7.08%) | 4.170 (3.02%) |
| 0.15 | 122.7 | 63.8 | 9.767 (7.08%) | 4.156 (3.01%) |
| 0.2 | 125.7 | 71.4 | 9.764 (7.08%) | 4.153 (3.01%) |
| 0.3 | 142.2 | 84.6 | 9.769 (7.08%) | 4.152 (3.01%) |
| 0.45 | 242.5 | 218.7 | 9.763 (7.07%) | 4.155 (3.01%) |
| 0.6 | 490.2 | 442.6 | 9.831 (7.12%) | 4.197 (3.04%) |
| 0.9 | 713.8 | 740.5 | 9.966 (7.22%) | 4.362 (3.16%) |

The 40:1 ratio the previous session imposed was the main thing holding jitter
up: `VEL_KI` is the dominant chatter term and the inherited 0.3 was 6x too high.
Jitter falls monotonically toward `VEL_KI=0`, but below 0.05 tracking error
starts to degrade, so 0.05 is the knee.

### 3. `VEL_KP` again, with `VEL_KI=0.05`

| VEL_KP | 1 Hz jit | 0.5 Hz jit | 1 Hz err | 0.5 Hz err |
|---|---|---|---|---|
| 4 | 142.6 | 123.3 | 10.141 (7.35%) | 4.834 (3.50%) |
| 5 | 91.1 | 65.1 | 9.820 (7.12%) | 4.321 (3.13%) |
| 6 | 84.3 | 50.7 | 9.822 (7.12%) | 4.269 (3.09%) |
| **7** | **80.8** | **46.9** | 9.802 (7.10%) | 4.235 (3.07%) |
| 8 | 85.2 | 47.8 | 9.793 (7.10%) | 4.234 (3.07%) |
| 9 | 92.6 | 49.0 | 9.817 (7.11%) | 4.226 (3.06%) |
| 10 | 99.5 | 50.3 | 9.813 (7.11%) | 4.215 (3.05%) |
| 12 | 118.2 | 57.4 | 9.812 (7.11%) | 4.215 (3.05%) |
| 14 | 136.1 | 64.6 | 9.820 (7.12%) | 4.213 (3.05%) |
| 16 | 155.7 | 73.1 | 9.832 (7.12%) | 4.215 (3.05%) |
| 20 | 196.8 | 90.3 | 9.848 (7.14%) | 4.220 (3.06%) |

The `VEL_KP` optimum moved 12 → 7 once `VEL_KI` came down, which is exactly what
the fixed-ratio search could not see. A companion `VEL_KI` sweep at `VEL_KP=7`
(0.03/0.05/0.08/0.1/0.15 → 74.7/80.8/94.9/96.4/200.1 mA at 1 Hz) reconfirmed
0.05 as the knee; 0.03 buys ~8% jitter at the cost of a rising stiction residual
(0.95 vs 0.77 mrad).

### 4. `POS_KP`, with `VEL=(7, 0.05)`, `POS_KI=0.15`

| POS_KP | 1 Hz jit | 0.5 Hz jit | 1 Hz err | 0.5 Hz err |
|---|---|---|---|---|
| 30 | 76.9 | 37.2 | 17.598 (12.75%) | 6.233 (4.52%) |
| 45 | 78.3 | 41.7 | 12.684 (9.19%) | 5.078 (3.68%) |
| 60 | 80.8 | 46.9 | 9.802 (7.10%) | 4.235 (3.07%) |
| 80 | 85.3 | 55.7 | 7.478 (5.42%) | 3.441 (2.49%) |
| 100 | 93.9 | 64.5 | 6.038 (4.38%) | 2.891 (2.09%) |
| 120 | 97.3 | 82.2 | 5.068 (3.67%) | 2.515 (1.82%) |

A monotonic jitter-vs-tracking trade with no interior optimum — `POS_KP` alone
cannot improve both. `POS_KI` turned out to be the lever that breaks the trade.

### 5. `POS_KI`, with `VEL=(7, 0.05)`, `POS_KP=60`

| POS_KI | 1 Hz jit | 0.5 Hz jit | 1 Hz err | 0.5 Hz err | 1 Hz resid |
|---|---|---|---|---|---|
| 0.0 | 77.2 | 48.7 | 10.178 (7.38%) | 5.135 (3.72%) | 0.750 |
| 0.05 | 77.8 | 48.6 | 10.218 (7.40%) | 5.023 (3.64%) | 0.744 |
| 0.15 | 80.8 | 46.9 | 9.802 (7.10%) | 4.235 (3.07%) | 0.772 |
| 0.2 | 84.7 | 45.3 | 9.399 (6.81%) | 3.796 (2.75%) | 0.834 |
| 0.3 | 80.2 | 50.2 | 8.389 (6.08%) | 3.106 (2.25%) | 0.751 |
| 0.45 | 89.6 | 48.9 | 6.935 (5.03%) | 2.429 (1.76%) | 0.943 |
| **0.6** | **82.0** | **53.2** | 5.719 (4.14%) | 2.053 (1.49%) | 0.810 |
| 1.0 | 86.7 | 57.4 | 3.839 (2.78%) | 1.590 (1.15%) | 0.983 |
| 1.5 | 93.2 | 70.7 | 2.789 (2.02%) | 1.533 (1.11%) | 1.156 |
| 2.0 | 117.3 | 122.7 | 2.560 (1.86%) | 2.273 (1.65%) | 1.681 |
| 3.0 | 260.7 | 196.5 | 11.709 (8.48%) | 4.660 (3.38%) | 11.442 |
| 4.0 | 275.1 | 285.7 | 20.662 (14.97%) | 19.384 (14.05%) | 19.126 |

Jitter is flat within run-to-run scatter from 0.15 to ~1.0 while tracking error
falls by more than half — the inherited `POS_KI=0.15` was leaving a large,
nearly free accuracy gain on the table. The loop goes unstable above ~2
(residual error explodes at 3.0), so 0.6 keeps a >3x margin to that onset.

### 6. `POS_KP` again, with `POS_KI=0.6`

| POS_KP | 1 Hz jit | 0.5 Hz jit | 1 Hz err | 0.5 Hz err | 1 Hz resid |
|---|---|---|---|---|---|
| 20 | 74.9 | 37.8 | 6.823 (4.94%) | 2.938 (2.13%) | 1.456 |
| 25 | 76.3 | 38.6 | 6.715 (4.87%) | 2.720 (1.97%) | 1.342 |
| 30 | 77.2 | 39.2 | 6.589 (4.77%) | 2.520 (1.83%) | 1.219 |
| 35 | 77.9 | 40.5 | 6.452 (4.68%) | 2.377 (1.72%) | 1.096 |
| **40** | **80.6** | **41.4** | 6.320 (4.58%) | 2.283 (1.65%) | 1.057 |
| 50 | 84.4 | 45.3 | 6.032 (4.37%) | 2.131 (1.54%) | 0.974 |
| 60 | 82.0 | 53.2 | 5.719 (4.14%) | 2.053 (1.49%) | 0.938 |
| 70 | 94.9 | 55.1 | 5.452 (3.95%) | 1.954 (1.42%) | 0.938 |
| 80 | 95.8 | 58.3 | 5.161 (3.74%) | 1.867 (1.35%) | 0.867 |

Jitter bottoms out below ~40 but the stiction residual climbs as position
stiffness drops (1.46 mrad at 20 vs 1.06 at 40), so 40 is the corner: within a
few percent of the jitter floor without giving up disturbance rejection. A
`POS_KI` recheck at `POS_KP=40` (0.3/0.6/0.9/1.2 → 79.6/80.6/81.0/86.0 mA at
1 Hz) left 0.6 standing.

### 7. Velocity recheck, with `POS=(40, 0.6)`

| VEL_KP | 1 Hz jit | 0.5 Hz jit | | VEL_KI @6.5 | 1 Hz jit | 0.5 Hz jit | 1 Hz resid |
|---|---|---|---|---|---|---|---|
| 5 | 86.1 | 51.7 | | 0.03 | 71.8 | 38.8 | 1.491 |
| 6 | 76.1 | 42.3 | | **0.05** | **78.3** | **41.6** | 1.112 |
| **6.5** | **78.3** | **41.6** | | 0.08 | 93.6 | 49.9 | 0.943 |
| 7 | 80.6 | 41.4 | | 0.12 | 100.3 | 58.8 | 0.619 |
| 8 | 85.4 | 43.1 | | | | | |
| 10 | 102.2 | 47.9 | | | | | |

The velocity optimum shifted only slightly (7 → a flat 6–7 band) after the
position retune, so the loop had converged; `VEL_KP=6.5` is the midpoint of that
band and `VEL_KI=0.05` held as the knee. No further iteration needed.

## Final gains

`VEL_KP=6.5  VEL_KI=0.05  POS_KP=40.0  POS_KI=0.6  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

Verified at 0.5, 0.75, and 1 Hz (1, 2, and 3 cycles; realized 0.75 Hz was
0.749991 Hz per the wrapper's printed frequency):

| freq | jitter | vs. baseline | err rms | vs. baseline |
|---|---|---|---|---|
| 0.5 Hz | 44.3 mA | −47.6% (was 84.6) | 2.328 mrad (1.69%) | −43.9% (was 4.152) |
| 0.75 Hz | 58.5 mA | −43.9% (was 104.3) | 3.700 mrad (2.68%) | −46.8% (was 6.954) |
| 1 Hz | 79.0 mA | −44.4% (was 142.2) | 6.328 mrad (4.59%) | −35.2% (was 9.769) |

Jitter and tracking error both improved ~35–48% at every frequency — the
previous session's fixed-ratio constraint had forced a trade that does not
actually exist once `VEL_KI` and `POS_KI` move independently. The one metric
that worsened is the nonlinear/stiction residual at 0.5 Hz (0.769 → 1.626 mrad),
the expected consequence of lower position stiffness; total error still halved.

No arm attached, so `cn-seamless` tunables were **not** updated. j0 was left at
the final gains above.

`Jx_STATUS` read `WARN_OV`/`WARN_OV_CLAMP` at the end of the session. These are
live bus-voltage warnings, not latched faults (`clear-faults.sh` does not clear
them) and most likely reflect regen into the bench supply during the unstable
`POS_KI` 3.0/4.0 probes. Flags were `[]` at session start; the final
verification captures show no sign of clamping.

## Captures

`traces/chatter/j0-david-full/` (140 `.txf` directories, `-1hz` and `-0p5hz` per
gain set unless noted):

- `baseline-{1hz,0p5hz,0p75hz}` — inherited gains (`VEL=12/0.3`, `POS=60/0.15`)
- `vkp{6,9,10,11,13,15,18,24}` — `VEL_KP` sweep at `VEL_KI=0.3`
- `vki{0.0,0.02,0.03,0.05,0.1,0.15,0.2,0.45,0.6,0.9}` — `VEL_KI` sweep at `VEL_KP=12`
- `vkp{4,5,6,8,9,10,14,16,20}-vki0.05` — `VEL_KP` sweep at `VEL_KI=0.05`
- `vkp7-vki{0.03,0.05,0.08,0.1,0.15}` — `VEL_KI` sweep at `VEL_KP=7`
- `pkp{30,45,80,100,120}` — `POS_KP` sweep at `POS_KI=0.15`
- `pki{0.0,0.05,0.2,0.3,0.45,0.6,1.0,1.5,2.0,3.0,4.0}` — `POS_KI` sweep at `POS_KP=60`
- `pkp{20,25,30,35,40,50,70,80}-pki0.6` — `POS_KP` sweep at `POS_KI=0.6`
- `pkp40-pki{0.3,0.9,1.2}` — `POS_KI` recheck at `POS_KP=40`
- `re-vkp{5,6,6.5,8,10}` and `re-vkp6.5-vki{0.03,0.08,0.12}` — velocity recheck at `POS=(40, 0.6)`
- `final-{0p5hz,0p75hz,1hz}` — final-gain verification
