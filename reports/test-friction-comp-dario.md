# j0 tracking comparison, friction compensation — 2026-09-17

Ten-frequency position tracking test from
[test-tracking](../../.claude/skills/test-tracking/SKILL.md), run twice on
`100.106.65.65` (dario) at the tuned gains from
[tune-chatter-j0-dario.md](../../reports/tune-chatter-j0-dario.md):

`VEL_KP=8.0  VEL_KI=0.05  POS_KP=60.0  POS_KI=0.6  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

- `j0-100.106.65.65-tracking-nofric/` — no friction compensation
- `j0-100.106.65.65-tracking-compfric/` — `-F` (`FEATURE_FRIC_COMP`)

Gains and firmware (`GHASH=194203904`) were already loaded from the chatter
tuning session; no gain writes were needed. Each run: ten evenly spaced
frequencies (0.1–0.6 Hz), 0.25 rad peak amplitude, 3 s per frequency, stride
20. Errors are shortest angular difference over the entire 3 s driven window
(startup included, baseline/tail excluded, no cycles dropped); partial-cycle
sines mean each point's error depends on which sine segment got sampled (0.3
cycles at 0.1 Hz up to 1.8 at 0.6 Hz), so small point-to-point differences
shouldn't be over-read.

All 20 captures completed without truncation.

## Results

Peak / mean absolute error (mrad):

| Hz | no-fric peak | comp-fric peak | no-fric mean | comp-fric mean |
|---|---|---|---|---|
| 0.10 | 3.75 | 3.31 | 0.26 | 0.85 |
| 0.16 | 4.96 | 4.23 | 0.41 | 0.86 |
| 0.21 | 7.28 | 5.58 | 0.58 | 0.74 |
| 0.27 | 8.49 | 6.71 | 0.93 | 0.94 |
| 0.32 | 9.93 | 8.37 | 1.31 | 1.31 |
| 0.38 | 11.44 | 9.54 | 1.61 | 1.60 |
| 0.43 | 13.84 | 11.27 | 2.16 | 2.14 |
| 0.49 | 16.83 | 12.99 | 2.76 | 2.72 |
| 0.54 | 20.71 | 14.78 | 3.24 | 3.12 |
| 0.60 | 24.42 | 16.99 | 4.08 | 3.81 |

Friction compensation lowers peak error at every frequency, by an increasing
margin (~12% at 0.1 Hz up to ~30% at 0.6 Hz). Mean error is essentially a wash
above ~0.27 Hz, and slightly worse with compensation at the three lowest
frequencies (0.26→0.85, 0.41→0.86, 0.58→0.74 mrad). The peak-error trend
favoring compensation is the more robust signal given the partial-cycle
caveat above.

## Captures

`traces/tracking/`:

- `j0-100.106.65.65-tracking-nofric/` — 10 `.txf` captures + `tracking.png`
- `j0-100.106.65.65-tracking-compfric/` — 10 `.txf` captures + `tracking.png`
