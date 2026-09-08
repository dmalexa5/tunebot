---
name: tune-friction
description: Tune a LuGre friction model of an unloaded joint, using rtttest torque and velocity ramps for data collection and MATLAB for fitting data to the non-linear LuGre model.
---

# Tune friction model

This task calibrates a modified LuGre friction equation. Assuming the current to torque ratio is linear and time-invariant for the targeted joints, the target equation is:

$$I_f = \sigma_0z + \sigma_1\dot{z} + \sigma_2\omega$$

Where $I_f$ is the current due to friction effects and z is:

$$\dot{z} = \omega - \sigma_0 \frac{|\omega|}{I_c + (I_s - I_c) e^{-(\omega/\omega_s)^2}}$$

## Pre-test information

**First**, ask the user which joint is being tuned.

**Second**, ask the user for the location where scope captures should live for this tuning session. Move all scope captures to this location after capture.

**Third**, check `rttcmd` settings.
- Ask if there is an IP to target for openocd. If there is, add a `-i IP` flag to the `rtttest` command
- Ask if `-r` has already been used to start the rtt server. If not, your first rttcmd will need to include this flag.
- Require openocd running already (ask for confirmation). If it is not, notify the user and exit this task.
- Check the current gains configured on the system. Make sure they are non-zero.
- Examine `scripts/`, it contains tooling for the tests.

**Fourth**, ensure MATLAB is running
- If not, launch it
- Use `startup.m` to launch the MCP server

## Test 1 - steady-state friction-velocoity map

This targets these params:
- `Ic`, current due to couloumb friction
- `Is`, maximum static friction current
- `stribeck_vel` ($\omega_s$), stribeck velocity
- `sig2` ($\sigma_2$)

**First**, capture a series of velocity holds 
- Log-spaced, denser near the stribeck knee
- Go from 0.01 to 0.875 rad/s with a fixed ratio of 1.5x per step
  - 0.010, 0.015, 0.022, 0.033, 0.050, 0.075, 0.100, 0.150, 0.225, 0.338, 0.507, 0.760, 0.875 rad/s
- Use the velocity step function in `scripts/run-step.sh`

**Second**, fit the stribeck function to this data with a simple nonlinear least-squares regression
- 

## Test 2 - breakaway vs. loading rate

This targets the `sig0` ($\sigma_0$) param

**First**, capture a series of current ramps
- Initial current is 0.5 A, final current is 2 A
- 0.1, 0.33, 1, 3.3, 10, 33, 100 A/s
  - use `scripts/run-ramp.sh`
- literal current step 0 to 2.0 A
  - use `scripts/run-step.sh`

## Test 3 - pre-sliding damping

This targets the `sig1` ($\sigma_1$) param. `sig0` is not fit anywhere in Test 2 as written, so it is folded into this test's joint fit instead (see Second, below).

**First**, with the joint at rest, apply a small sinusoidal current dither sweep
- Log-spaced frequencies: 1, 2, 5, 10, 20, 50, 100 Hz
- Amplitude well below the breakaway current found in Test 2 (e.g. 0.15 A against a ~1.1-2.0 A breakaway band)
- 20 cycles per frequency, using `scripts/run-sine.sh` in torque mode
- Scale stride to the RTT link's throughput ceiling for the longer/low-frequency captures 
  - See `module-fwpp/cheatsheet.md`'s "Trace Throughput" section

**Second**, fit `sig0`, `sig1` and `sig2` by simulating the actual LuGre ODE (20 kHz fixed-step) inside `lsqnonlin`/`fmincon`
- Use `scripts/txf-breakaway.py` to find each Test 2 ramp/step capture's breakaway point and export the pre-breakaway "presliding" segment (t, w, iq) to CSV; use `scripts/txf-export-csv.py` to export each Test 3 dither capture the same way
- Fit with `scripts/fit_lugre_joint.m` (`lsqnonlin`): hold `Ic`/`Is`/`stribeck_vel` fixed from Test 1, solve for `sig0`, `sig1`, `sig2` together by simulating `scripts/lugre_predict.m`'s LuGre ODE (velocity interpolated onto a fixed 20 kHz grid, Euler-integrated, predicted current resampled back to the measurement times) against every presliding + dither trial's measured current
- Check that `vel_fbk`'s std/max in each trial clearly exceeds the joint's noise floor; if it doesn't, `sig0`/`sig1` are not identifiable this way and should be reported as such rather than written into the final values.

This only works if `vel_fbk` carries real presliding-deflection signal above the encoder noise floor

**Finally**, write the final values to a report, using `reports/tune-friction-example.md` as the template.