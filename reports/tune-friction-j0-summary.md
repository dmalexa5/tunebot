# tune-friction report: j0 (48 V)

### Final parameters:

- `IC = 1.7063 A`
- `IS = 2.1286 A`
- `STRIBECK_VEL = 0.1246 rad/s`
- `SIG0 = 16174 A/rad` (output-referred, +/-20%)
- `SIG1 = not identifiable`
- `SIG2 = 1.1957 A/(rad/s)`

### Notes

Target `100.79.218.29`, 48 V bus, `TRACE=MECH`, continuous-rotation joint.

**Test 1** -- 13 log-spaced velocity holds, 0.010-0.875 rad/s, 1000 ms,
stride 12 (`fit_stribeck.m`). Genuine Stribeck knee (`IS > IC`), unlike j1;
parameters stable against point removal. `STRIBECK_VEL` is weakly supported
(95% CI [0.005, 0.245]) -- few points sample the knee. `SIG2` is corroborated
independently: Test 2 ramps coast to 1.126 rad/s at 3 A vs 1.08 predicted.

**Test 2** -- 0->3 A ramps at 0.1/0.33/1/3.3/10/33/100 A/s, 5 trials per rate
per direction, plus a literal 2.0 A step. Breakaway rises monotonically with
loading rate, 2.08 -> 2.78 A. `SIG0` fit from the presliding `mpos` traces
with the LuGre ODE (`lugre_predict`, `lsqnonlin`), all Test 1 params fixed.

**`SIG1` is not identified** (95% CI [-13.5, 13.5]): it multiplies `dz/dt`,
which is negligible throughout presliding. Same structural outcome as j1 --
this test cannot constrain it at any data quality.

**`SIG0` is effective, not literal.** Per-rate refits drift 12216 (0.33 A/s)
to 17673 (10 A/s) against CI widths of ~1100, and the model's bristle scale
`IS/SIG0` = 132 urad vs 569-8465 urad measured deflection. Gearbox windup and
rate-dependent creep sit in series with the friction element on a 510:1 joint.
Valid for roughly 1-10 A/s; rms residual 0.24-0.34 A.

**Gotchas.**
- `VEL_KP` must read back ~`3.5e-08` (count domain). It initially read `24` --
  the rad-domain value from `drive-gains.json` -- which rails the loop
  bang-bang at +/-5 A. Use `set-gains.sh`, which applies the conversion.
- Stride 1 overruns the RTT link (`CTRL_OVERFLOW`, truncates to ~560 records).
  Use stride >= 2.
- The skill's 2.0 A step is *below* j0's `IS`: only 1/5 trials broke away.
  ~2.6 A would be needed.
- 100 A/s is truncation-limited (ramp ends before the joint clears the
  50 mrad/s threshold); excluded from the fit.
- Velocity from unwrapped `mpos` (gear ratio -509.7, measured) is **828x
  quieter** than `vel_fbk`. This is why `SIG0` resolved here and not on j1.

### Captures

- `traces/j0-48V-friction-tune/vhold.0006.txf` (Test 1, velocity hold)
- `traces/j0-48V-friction-tune/br1p.0000.txf` (Test 2, current ramp)
- `traces/j0-48V-friction-tune/bstepp.0000.txf` (Test 2, literal current step)
