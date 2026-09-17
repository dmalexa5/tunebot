---
name: tune-chatter
description: Retune a designated robot joint's drive gains to minimize velocity chatter while maintaining tracking error, using rtttest sine sweeps and scope captures. Use when asked to tune out chatter/oscillation in a joint.
---

# Minimize chatter in a designated joint

Retune the designated joint with the goal of minimizing velocity chatter while maintaining the best possible tracking error.

**First**, ask the user which joint is being tuned.

**Second**, ask the user whether there is a bevel arm, universal arm, or no arm attached.
- If bevel arm, set these variables
  - `export AMPLITUDE=0.138`
  - `export TUNABLE=drive-gains-bevel.json`
- If universal arm, set these variables
  - `export AMPLITUDE=0.138`
  - `export TUNABLE=drive-gains.json`
- If no arm, set these variables
  - `export AMPLITUDE=0.138`
  - Do not update any tunables

**Third**, ask the user for the location where scope captures should live for this tuning session. Move all scope captures to this location after capture.

**Fourth**, check `rttcmd` settings.
- Ask if there is an IP to target for openocd. If there is, add a `-i IP` flag to the `rtttest` command
- Ask if `-r` has already been used to start the rtt server. If not, your first rttcmd will need to include this flag.
- Require openocd running already (ask for confirmation). If it is not, notify the user and exit this task.

**Next**, run the test.

These tests should be run at an amplitude dependant on arm type. **The
firmware's waveform engine counts its timeline in 20 kHz servo ticks in a
`uint16`, so a whole run — pads included — cannot exceed ~3.27 s.** That puts
a floor of ~0.31 Hz on a single-cycle sine and rules out the 0.1 Hz and
0.25 Hz points this skill used to tune at. Work the range the engine can
actually reach: tune at 1 Hz and 0.5 Hz until you have a final gains
candidate, then verify with a sweep of 0.5 -> 0.75 -> 1.0 Hz. `run-sine.sh`
refuses anything out of range and prints the realized frequency — pass that
number to `scripts/txf-sine.py`, not the requested one.

Cycle counts are capped by the same budget: at stride 20, 3 cycles at 1 Hz,
2 at 0.75 Hz, 1 at 0.5 Hz.

Set the baseline gains first using `scripts/set-gains.sh`. Use this script to set all gains. When testing for ideal gains, use a bisecting/binary search to quickly converge on final candidates.

Use this command, with only frequency being adjusted:
```
scripts/run-sine.sh pos 1.0 $AMPLITUDE 2
```

`run-sine.sh` selects `MODE_POS` itself and returns the joint to `0TQ`
afterwards; the waveform engine does neither. If the friction compensator is
meant to stay on across a capture, add `-F` — writing a mode otherwise
rebuilds the whole ctrl word and clears `FEATURE_FRIC_COMP`.

Go through the scripts rather than calling `rtttest` directly: the servo loop
takes output-shaft counts (2^32/rev), not radians, and the scripts are where
the amplitude above gets converted. A raw
`{"test":"signal_sine","signal":"pos","amplitude":0.138}` commands 0.138
*counts* and moves nothing. The scripts also select and clear the control
mode, size the capture pads, and resolve `$TABLES` and the `rtttest` path
themselves.

Check `../cn-seamless/configs/tunables/$TUNABLE` for the untuned baseline gains, at the specified joint. Check @../module-fwpp/, specifically @../module-fwpp/src/servo.c, for the cascaded pid control structure.

**Finally**, write the final report

- Update `$TUNABLE` with the new joint gains
- Write a summary in `reports/`, using `reports/tune-chatter-example.md` as a template. Keep the summary concise and to-the-point. Remove all markdown comments after filling in the relevant information.
