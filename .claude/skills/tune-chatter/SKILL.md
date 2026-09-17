---
name: tune-chatter
description: Tune a robot joint's drive gains to reduce chatter while preserving tracking accuracy.
---

# Tune chatter

Read `CLAUDE.md` and `cheatsheet.md` for setup, units, and capture limits.
Obtain missing session details together: joint, arm type (bevel/universal/none),
capture directory, target IP, and RTT server state.

1. Read baseline joint gains from `../cn-seamless/configs/tunables/`:
   bevel uses `drive-gains-bevel.json`; universal uses `drive-gains.json`.
   With no arm, do not update tunables. Set gains through `scripts/set-gains.sh`.
2. Capture baseline position sines at 0.138 rad amplitude. Tune at 1 Hz and
   0.5 Hz, using binary search for gain candidates. Keep friction compensation
   consistent across comparisons (`-F` if enabled).
3. Compare `scripts/txf-sine.py` results: minimize `iq_jitter` while preserving
   tracking error. Verify actual command amplitude and reject truncated captures.
4. Verify final gains at 0.5, 0.75, and 1 Hz (1, 2, and 3 cycles respectively).
   Move captures to the session directory.
5. Update the designated joint's arm tunables when applicable. Write a short
   report with final gains, baseline/final jitter and tracking error by frequency,
   test conditions, and capture paths.
