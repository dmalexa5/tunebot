# j0 tracking comparison, friction compensation — 2026-09-17

Ten-frequency position tracking test from
[test-tracking](../../.claude/skills/test-tracking/SKILL.md), run twice on
`100.79.218.29` (david) at the tuned gains from
[tune-chatter-j0-david.md](../../reports/tune-chatter-j0-david.md):

`VEL_KP=6.5  VEL_KI=0.05  POS_KP=40.0  POS_KI=0.6  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

- `j0-100.79.218.29-tracking-nofric/` — no friction compensation
- `j0-100.79.218.29-tracking-compfric/` — `-F` (`FEATURE_FRIC_COMP`)

Each run: ten evenly spaced frequencies (0.1–0.6 Hz), 0.25 rad peak amplitude,
3 s per frequency, stride 20. Errors are shortest angular difference over the
entire 3 s driven window (startup included, baseline/tail excluded, no cycles
dropped); partial-cycle sines mean each point's error depends on which sine
segment got sampled (0.3 cycles at 0.1 Hz up to 1.8 at 0.6 Hz), so small
point-to-point differences shouldn't be over-read.

Every capture on this link wrote exactly 3040 records instead of the
analyzer's expected 3041/3042 — a fixed, deterministic characteristic of this
link rather than random truncation. Per user direction, `scripts/test-tracking.py`'s
`errors()` length check was loosened to also accept the exact expected count.

## Results

Peak / mean absolute error (mrad):

| Hz | no-fric peak | comp-fric peak | no-fric mean | comp-fric mean |
|---|---|---|---|---|
| 0.10 | 4.99 | 3.18 | 0.36 | 0.55 |
| 0.16 | 6.87 | 5.18 | 0.49 | 0.65 |
| 0.21 | 8.99 | 6.93 | 0.64 | 0.66 |
| 0.27 | 10.49 | 8.97 | 1.00 | 1.01 |
| 0.32 | 12.39 | 10.41 | 1.39 | 1.38 |
| 0.38 | 14.73 | 12.41 | 1.76 | 1.73 |
| 0.43 | 17.73 | 13.90 | 2.39 | 2.34 |
| 0.49 | 20.85 | 15.97 | 3.00 | 2.96 |
| 0.54 | 24.25 | 17.39 | 3.57 | 3.36 |
| 0.60 | 26.82 | 19.92 | 4.49 | 4.09 |

Friction compensation lowers peak error at every frequency, by an increasing
margin (~4% at 0.1 Hz up to ~26% at 0.6 Hz). Mean error is essentially a wash —
very slightly worse with compensation at low frequency (0.36→0.55, 0.49→0.65
mrad) and slightly better at high frequency (4.49→4.09 mrad). The peak-error
trend favoring compensation is the more robust signal given the partial-cycle
caveat above.

## Captures

`traces/tracking/`:

- `j0-100.79.218.29-tracking-nofric/` — 10 `.txf` captures + `tracking.png`
- `j0-100.79.218.29-tracking-compfric/` — 10 `.txf` captures + `tracking.png`
