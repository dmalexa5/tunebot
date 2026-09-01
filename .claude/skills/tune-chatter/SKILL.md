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

These tests should be run at an amplitude dependant on arm type, with the highest frequency being 1 Hz and lowest frequency being 0.1 Hz. Tune at 1 Hz and 0.1 Hz until you have reached a final gains candidate, then verify with a quick frequency sweep from 0.1 -> 0.25 -> 0.5 -> 0.75 -> 1.0

Set the baseline gains first using `scripts/setgains.sh`. Use this script to set all gains. When testing for ideal gains, use a bisecting/binary search to quickly converge on final candidates.

Use this command, with only frequency being adjusted (single-cycle sine wave test):
```
rtttest -n -s $TABLES -o psine '{"test":"servo_sine","mode":2,"freq_hz":1.0,"amp":0.138,"cycles":2}'
```

Source $TABLES at this location:
```
export TABLES=../module-fwpp/output/drive/none/drive-none.tables.json
```

Check `../cn-seamless/configs/tunables/$TUNABLE` for the untuned baseline gains, at the specified joint. Check @../module-fwpp/, specifically @../module-fwpp/src/servo.c, for the cascaded pid control structure.

**Finally**, write the final report

- Update `$TUNABLE` with the new joint gains
- Write a summary in `reports/`, using `reports/tune-chatter-example.md` as a template. Keep the summary concise and to-the-point. Remove all markdown comments after filling in the relevant information.
