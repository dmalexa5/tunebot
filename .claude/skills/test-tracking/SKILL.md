---
name: test-tracking
description: Run ten fixed-frequency position tracking tests from 0.1 to 0.6 Hz and plot peak and average absolute error on one Matplotlib graph.
---

# Test tracking

Use for `/test-tracking`. Read `CLAUDE.md` and `cheatsheet.md` for setup.

1. Obtain missing target IP, new `traces/<session>/` directory, RTT server state,
   and whether friction compensation should be enabled. Confirm OpenOCD is
   running; do not start it. Require `DEBUG=1`, `TRACE=MECH` firmware and non-zero
   servo gains. Do not change gains or sibling firmware.
2. Ensure `.venv` has `requirements.txt` installed. Run from the repository root:
   ```sh
   .venv/bin/python scripts/test-tracking.py -i IP traces/session
   ```
   Add `-r` only if the RTT server needs starting; add `-F` if compensation should
   be enabled. Each mode write sets compensation according to this flag.
3. Keep this test fixed: ten evenly spaced frequencies including 0.1 and 0.6 Hz,
   0.25 rad peak amplitude, 3 seconds per frequency, stride 20. The existing
   `signal_chirp` command with equal start/end frequencies generates each sine;
   `log=false` and `taper=false`. This avoids the sine command's period limit.
   Partial cycles are intentional: 0.3 cycles at 0.1 Hz through 1.8 at 0.6 Hz.
4. The script zeros current, waits one second, selects POS, captures, and returns
   to zero current for each test. It stops on failed or truncated captures;
   retain raw captures and surface cleanup errors. Do not silently retry.
5. Return `traces/<session>/tracking.png` and the capture directory. The single
   graph has peak and mean absolute `pos_cmd - pos_fbk` error in mrad versus Hz.
   Errors use shortest angular difference over all 3 seconds of driven samples;
   baseline and tail are excluded, startup is included, and no cycles are dropped.
   Briefly state that partial-cycle errors depend on the sampled sine segment.
   No separate report or CSV is needed. To replot without hardware:
   ```sh
   .venv/bin/python scripts/test-tracking.py --analyze traces/session
   ```
