---
name: test-run-in
description: Run repeated 3 A torque holds and 0.5/1/2 Hz position sine captures on a joint, then plot sine metrics across repeats to check for run-in drift.
---

# Test run-in

Use for `/test-run-in`. Read `CLAUDE.md` and `cheatsheet.md` for setup.

1. Obtain missing target IP, new `traces/<session>/` directory, and RTT server
   state. Confirm OpenOCD is running; do not start it. Require `DEBUG=1`,
   `TRACE=MECH` firmware and non-zero servo gains -- if gains read 0, load the
   joint's default gains from `../cn-seamless/configs/tunables/`: bevel uses
   `drive-gains-bevel.json`; universal uses `drive-gains.json`. Set them
   through `scripts/set-gains.sh`. Do not change gains beyond loading this
   default, and do not touch sibling firmware.
2. Ensure `.venv` has `requirements.txt` installed. Run from the repository root:
   ```sh
   .venv/bin/python scripts/test-run-in.py -i IP traces/session
   ```
   Add `-r` only if the RTT server needs starting.
3. Keep this test fixed: 5 repeats, each a 20 s, 3 A torque hold in `0TQ` in
   the positive direction, then the negative, with no capture, followed by
   three POS-mode sine captures at 0.5, 1, and 2 Hz, 0.138 rad amplitude.
   Holds write raw `Jx_IDQ` current directly -- unclamped by `VEL_TQC_LIM`
   or the signal engine, limited only by `FOC_I_TRIP`. Sines use the
   `signal_chirp` equal-endpoint trick (3 s, stride 20) like
   `test-tracking.py`, giving a fixed duration across frequencies without
   `signal_sine`'s uint16 period limit.
4. The script zeros current, waits, holds +3 A then -3 A for 20 s each, zeros,
   then captures each frequency in turn, returning to zero current between
   and after every step. It stops on failed or truncated captures; retain raw
   captures and surface cleanup errors. Do not silently retry.
5. Return `traces/<session>/run-in.png` and the capture directory. The plot
   has gain, phase, RMS tracking error, and `iq_cmd` jitter versus repeat
   number, one line per frequency, from `txf-sine.py`'s per-capture metrics.
   Briefly state whether any metric trends across repeats (settling/wear-in)
   or looks flat. No separate report or CSV is needed. To replot without
   hardware:
   ```sh
   .venv/bin/python scripts/test-run-in.py --analyze traces/session
   ```
