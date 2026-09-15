# tune-friction report: j0

### Final parameters:

- `IC = 1.7063 A`
- `IS = 2.1286 A`
- `STRIBECK_VEL = 0.1246 rad/s`
- `SIG0 = 16174 A/rad` (output-referred; see Notes -- 12216-17673 across loading rates)
- `SIG1 = not identifiable (see Notes)`
- `SIG2 = 1.1957 A/(rad/s)`

### Notes

Target `100.79.218.29`, 48 V bus, RTT server already running, firmware
`TRACE=MECH`. Joint is continuous-rotation (confirmed with user), so all
Test 1 holds ran in the +direction without repositioning.

**Gain precondition (cost one test round).** `VEL_KP`/`POS_KP` initially read
0. After they were set, `VEL_KP` read back as exactly `24` -- the *rad-domain*
value from `cn-seamless drive-gains.json`, written into a field the servo loop
reads as A/(count/s) (`src/servo.h:53`, `SERVO_VEL_GAIN_FROM_RAD`). Effective
gain was 1.64e10 A/(rad/s), so a 0.1 rad/s error demanded 1.6e9 A: a sanity
probe showed `iq_cmd` bang-banging between +/-5.0 A on nearly every sample
(jitter 6656 mA/samp) with -68% steady-state error. Re-running
`set-gains.sh 24 0.6 60 0.15`, which applies the conversion itself, wrote
`VEL_KP = 3.511e-08` and the loop regulated: 0.39% steady-state error, jitter
168 mA/samp. **Always verify the readback is ~3.5e-8, not 24.**

**Test 1** (steady-state friction-velocity map): 13 log-spaced velocity holds,
0.010-0.875 rad/s, 1000 ms hold, stride 12, `fit_stribeck.m` (`lsqcurvefit`,
300 ms settle skip). Tracking error <1% on 11 of 13. Unlike j1, j0 shows a
genuine Stribeck knee -- `IS > IC` and the fit is physical. Parameters are
stable against point removal (`IC` 1.66-1.75, `IS` 2.04-2.13, `SIG2`
1.07-1.26 across subsets). Two caveats: `vhold.0012` (0.875 rad/s) clipped the
5 A `VEL_TQC_LIM` on 58/1166 samples, and `vhold.0002` (0.022 rad/s) is a
0.31 A outlier that alone accounts for 4x the resnorm (0.155 -> 0.036 when
dropped) without materially moving the parameters. `STRIBECK_VEL` has the
weakest support (95% CI [0.005, 0.245]) -- the knee is sampled by only a few
points. `SIG2` is independently corroborated: the Test 2 ramps coast to a
terminal 1.126 rad/s at 3 A, against 1.08 rad/s predicted by `IC + SIG2*w`.

**Test 2** (breakaway vs loading rate): current ramps 0->3 A at 0.1, 0.33, 1,
3.3, 10, 33, 100 A/s, 5 trials per rate per direction, plus a literal 0->2.0 A
step; 2 s dwell at rest between trials (verified: baseline |vel| <= 29 mrad/s
on every trial). Breakaway current rises monotonically with loading rate,
2.08-2.16 A at 0.1 A/s to 2.78 A at 100 A/s.

Three measurement notes:

- **Stride 1 is unusable.** All stride-1 captures returned `CTRL_OVERFLOW`
  (code 79, `board-drive.c:2237`) and truncated to ~560 records. Stride 2
  (10 kHz) captured exact record counts. Re-ran 33/100 A/s and the step at
  stride 2.
- **The 100 A/s point is truncation-limited.** The 30 ms ramp ends before the
  joint accelerates past the 50 mrad/s detection threshold, so only 1/5
  negative-direction trials triggered; deflection confirms breakaway did
  occur. Its `I_br` is biased high and was not used to anchor the fit.
- **The 2.0 A step is below j0's static friction.** Only 1/5 trials moved
  (0.18 rad/s); the other four deflected ~650 urad and stuck. Expected, given
  `IS = 2.13 A` -- the skill's 2.0 A step sits just under breakaway on this
  joint. A ~2.6 A step would be needed to break away reliably.

`SIG0` was extracted from the presliding `mpos` traces, not from the velocity
threshold. `mpos` (motor-side, unwrapped at +/-pi, referred to output through a
gear ratio of **-509.7** measured from unwrapped `mpos` vs `opos` over five
velocity holds) gives an output-referred resolution of 1.88e-7 rad, and a
`mpos`-differentiated velocity with **828x lower noise than `vel_fbk`**
(std 1e-5 vs 4.3e-3 rad/s while stuck). This is precisely the fix
`tune-friction-j1.md` proposed, and it is why `SIG0` is identified here and
was not on j1. 14 presliding segments (0.33-10 A/s, both directions) were fit
with the LuGre ODE (`lugre_predict`, `lsqnonlin`), `IC`/`IS`/`STRIBECK_VEL`
fixed from Test 1.

`SIG2` had to be fixed from Test 1 as well. Fitting it jointly against
presliding data returned -8.66 A/(rad/s) -- non-physical, and contradicting
Test 1's +1.196. Presliding holds w ~ 0 by construction, so the `SIG2*w` term
carries almost no information there; the steady-state sweep is the experiment
that identifies viscous damping, and Test 2 should not be allowed to move it.

**`SIG1` is not identified.** Its 95% CI is [-13.5, 13.5] around an estimate of
1e-4 -- it multiplies `dz/dt`, which is negligible throughout presliding. Same
outcome as j1, and for the same structural reason; this test cannot constrain
it regardless of data quality.

**`SIG0` carries a real model caveat.** The pooled fit gives 16174 A/rad with a
narrow statistical CI [15937, 16412], but refitting per rate yields 12216
(0.33 A/s), 14269 (1), 17134 (3.3), 17673 (10) -- a 45% systematic drift
against CI widths of ~1100, so the subsets are genuinely distinguishable.
A single-bristle LuGre would give one `SIG0` at every rate. Supporting
evidence: the model's bristle scale `IS/SIG0` is 132 urad, while measured
breakaway deflection ran 569 urad (100 A/s) to 8465 urad (0.1 A/s), 4-60x
larger. The presliding compliance of a 510:1 geared joint is evidently not a
single bristle -- gearbox windup and rate-dependent creep sit in series with
the friction element. Treat `SIG0 = 16174` as an effective value good to about
+/-20%, valid for loading rates of roughly 1-10 A/s; rms residual is 0.24-0.34 A
across subsets (~15% of the ~2 A breakaway current).

### Captures

`traces/j0-48V-friction-tune/` (96 captures, 6.8 MB)

- `vstep.0000.txf` (railed velocity loop, before the gain fix -- kept as evidence)
- `vstep.0001.txf` (same probe after the fix)
- `vhold.0000-0012.txf` (Test 1, 13 velocity holds)
- `pilot.0000.txf` (Test 2 pilot, 1 A/s)
- `br{0p1,0p33,1,3p3,10,33,100}{p,n}.0000-0004.txf` (Test 2, 70 ramps)
- `bstep{p,n}.0000-0004.txf` (Test 2, literal 2.0 A step)
