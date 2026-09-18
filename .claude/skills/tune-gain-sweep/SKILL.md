---
name: tune-gain-sweep
description: Tune gains across a set of velocity holds, minimizing chatter while maximizing tracking accuracy. 
---

# Tune gain sweep

Read `CLAUDE.md` and `cheatsheet.md` for setup, units, and capture limits.
Obtain missing session details together: joint, arm type (bevel/universal/none),
capture directory, target IP, and RTT server state.

1. Read baseline joint gains from `../cn-seamless/configs/tunables/`: bevel uses `drive-gains-bevel.json`; universal uses `drive-gains.json`. Record `VEL_KP`, `VEL_KI`, `POS_KP`, `POS_KI`, and the torque/velocity limits. With no arm, do not update tunables. Set gains through `scripts/set-gains.sh`.
2. 