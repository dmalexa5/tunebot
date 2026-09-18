---
name: tune-chatter
description: Tune a robot joint's velocity and position PI gains to minimize chatter while maximizing tracking accuracy.
---

# Tune chatter

Read `CLAUDE.md` and `cheatsheet.md` for setup, units, and capture limits.
Obtain missing session details together: joint, arm type (bevel/universal/none),
capture directory, target IP, and RTT server state.

1. Read baseline joint gains from `../cn-seamless/configs/tunables/`: bevel uses `drive-gains-bevel.json`; universal uses `drive-gains.json`. Record `VEL_KP`, `VEL_KI`, `POS_KP`, `POS_KI`, and the torque/velocity limits. With no arm, do not update tunables. Set gains through `scripts/set-gains.sh`.
2. Capture baseline position sines at 0.138 rad amplitude. Tune at 1 Hz and 0.5 Hz. Tune `VEL_KP` and `VEL_KI`, then `POS_KP` and `POS_KI`, varying one gain at a time while holding the others at their best tested values. Do not hold position gains fixed or impose a fixed KP:KI ratio. Bracket promising ranges and bisect for gain candidates; jitter need not be monotonic. Recheck velocity gains after position tuning and repeat if the best settings shift. Apply the full candidate with `scripts/set-gains.sh -i IP vkp vki pkp pki tqclim vellim`, keeping limits consistent across comparisons. No friction compensation.
3. Compare `scripts/txf-sine.py` results: minimize `iq_jitter` while preserving tracking error. Verify actual command amplitude and reject truncated captures.
4. Verify final gains at 0.5, 0.75, and 1 Hz (1, 2, and 3 cycles respectively). Move captures to the session directory.
5. Update the designated joint's arm tunables when applicable. Write a shortreport with baseline/final values for all four PI gains, baseline/final jitter and tracking error by frequency, test conditions, and capture paths.
