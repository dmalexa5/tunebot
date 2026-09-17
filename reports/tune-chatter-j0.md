# j0 chatter tuning — 2026-09-17

## Conditions

- Target: `100.79.218.29`, j0, no arm attached (bare joint bench setup).
- OpenOCD and `rttlog -r` already running; RTT server not restarted (`-r` omitted
  on all `run-sine.sh` calls).
- Friction compensation confirmed disabled (`Jx_STATUS` flags: `[]`); `-F` not used.
- Position sines at 0.138 rad amplitude, stride 20 (default for `pos`).
- Captures: `traces/chatter/j0-david-baseline/`.

## Starting-gains gate

j0's live `VEL_KP`/`VEL_KI`/`POS_KP`/`POS_KI` all read 0 over RTT before any
capture — the joint had never been tuned. Per user direction, seeded gains
from `cn-seamless/configs/tunables/drive-gains.json` j0 entry
(`VEL_KP=24, VEL_KI=0.6, POS_KP=60, POS_KI=0.15, VEL_TQC_LIM=5, POS_VEL_LIM=π`)
before starting the binary search. `POS_KP`/`POS_KI`/`VEL_TQC_LIM`/`POS_VEL_LIM`
held fixed throughout; only `VEL_KP`/`VEL_KI` (kept at a fixed 40:1 ratio) were
searched, since chatter is driven by velocity-loop stiffness.

## Search

`iq_jitter` (mA/samp) vs. `VEL_KP` (`VEL_KI = VEL_KP/40`), tracking error
essentially flat across the whole range (dominated by loop phase lag, not gain):

| VEL_KP | jitter @1Hz | jitter @0.5Hz | err rms @1Hz | err rms @0.5Hz |
|---|---|---|---|---|
| 24 (baseline) | 268.5 mA | 137.7 mA | 9.753 mrad (7.07%) | 4.143 mrad (3.00%) |
| 15 | 171.1 mA | 94.9 mA | 9.748 mrad | 4.144 mrad |
| 13 | 148.6 mA | 86.5 mA | 9.748 mrad | 4.144 mrad |
| **12 (final)** | **146.3 mA** | **88.2 mA** | 9.756 mrad | 4.150 mrad |
| 11 | 143.0 mA | 88.0 mA | 9.748 mrad | 4.148 mrad |
| 9 | 167.5 mA | 123.5 mA | 9.757 mrad | 4.155 mrad |
| 6 | 250.3 mA | 223.8 mA | 9.941 mrad (7.20%) | 4.361 mrad (3.16%) |

Jitter is U-shaped in `VEL_KP`, not monotonic: it falls from 24 down to a flat
minimum around 11–13, then rises again below ~9 (under-damped velocity loop —
`err residual` and `vel pk` also increase there, consistent with the low-VEL_KP
limit-cycling behavior noted in `module-fwpp/cheatsheet.md`). Picked the
midpoint of the flat minimum, `VEL_KP=12`, `VEL_KI=0.3`, rather than either edge.

## Final gains

`VEL_KP=12.0  VEL_KI=0.3  POS_KP=60.0  POS_KI=0.15  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

Verified at 0.5, 0.75, and 1 Hz (1, 2, 3 cycles respectively; realized 0.75 Hz
was 0.749991 Hz per the wrapper's printed frequency):

| freq | jitter | err rms | vs. baseline jitter |
|---|---|---|---|
| 0.5 Hz | 84.1 mA | 4.147 mrad (3.00%) | −39% (was 137.7 mA) |
| 0.75 Hz | 109.7 mA | 6.947 mrad (5.03%) | no baseline captured |
| 1 Hz | 153.7 mA | 9.747 mrad (7.06%) | −43% (was 268.5 mA) |

Tracking error unchanged from baseline at every frequency (within noise);
jitter reduced ~40% at both baseline frequencies.

No arm attached, so `cn-seamless` tunables were **not** updated. j0 was left
at the final gains above.

## Captures

`traces/chatter/j0-david-baseline/`:
- `baseline-{1hz,0p5hz}-vkp24.0000.txf` — pre-search baseline (VEL_KP=24)
- `vkp{12,13,15,11,9,6}-{1hz,0p5hz}.0000.txf` — search candidates
- `final-{0p5hz,0p75hz,1hz}.0000.txf` — final-gain verification
