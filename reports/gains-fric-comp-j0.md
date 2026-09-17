# gain update + friction-compensator trial: j0 (48 V)

Target `100.79.218.29`, RTT server already running, firmware `a55cf61`
(build 197, `DEBUG`, `TRACE=MECH`) — the build that adds the compensator and
the `iq_fric` trace.

### Gains written

The requested values were rad-domain and had to be scaled to the loop's
output-shaft count domain (`src/servo.h`). Written with `set-gains.sh`, which
applies `SERVO_VEL_GAIN_FROM_RAD` / `SERVO_RAD_TO_CNT` itself:

```sh
set-gains.sh -i 100.79.218.29 24.0 0.6 20.0 0.15 5.0 3.1415927
```

| addr | requested (rad domain) | written (count domain) |
|---|---|---|
| `VEL_KP` | 24.0 A/(rad/s) | `3.5110e-08` A/(cnt/s) |
| `VEL_KI` | 0.6 | `8.7775e-10` |
| `VEL_TQC_LIM` | 5.0 A | `5` (amps, unscaled) |
| `POS_KP` | 20.0 | `20` (1/s either way) |
| `POS_KI` | 0.15 | `0.15` |
| `POS_VEL_LIM` | 3.1415927 rad/s | `2147483648` cnt/s |

`VEL_KD`/`POS_KD` are 0. `POS_KP`/`VEL_KP` both read 0 before the write
(the documented unconfigured-loop precondition). Readback verified
`VEL_KP = 3.511e-08`, **not** 24 — the failure mode from
`reports/tune-friction-j0.md`.

### Validation: single-cycle slow sine

`run-sine.sh pos 0.1 0.138 1 20` — 0.1 Hz, 0.138 rad, one cycle, stride 20.
10040 records (10000 + the 20+20 edge samples), no truncation. Peak velocity
0.116 rad/s, which sits just under the compensator's `FRIC_VS` = 0.1246 rad/s,
so the whole sweep lives in the Stribeck knee.

Gains are good: gain 1.0025 (+0.02 dB), phase -0.06°, tracking error
0.32% of command amplitude, no railing.

### Friction compensator: enabled, then reverted

Enabled with
`{"command":"Jx_STATUS","action":"WRITE","ctrl":"FEATURE_FRIC_COMP","mode":"VEL"}`,
using the compiled defaults (`IC=1.7063`, `IS=2.1286`, `SIGMA2=1.1957`,
`VS=0.1246`) — j0's identified parameters, confirmed read back from the board.
`iq_fric` is identically zero across all 10040 baseline samples and nonzero on
10037/10040 with the bit set, so the feature was genuinely active.

| metric | baseline | fric comp | baseline repeat |
|---|---|---|---|
| err rms | 0.436 mrad | **0.457 mrad** | 0.434 mrad |
| err residual (rms) | 0.344 mrad | **0.370 mrad** | 0.342 mrad |
| err @fund (peak) | 0.378 mrad | 0.379 mrad | 0.378 mrad |
| err max | 2.951 mrad | 2.884 mrad | 2.905 mrad |
| `iq_fbk` max | 3.018 A | **6.834 A** | 2.948 A |
| `iq_cmd` jitter | 193.2 mA/samp | **499.8 mA/samp** | 186.0 mA/samp |
| vel pk | 0.116 rad/s | 0.144 rad/s | 0.112 rad/s |

**Tracking error did not improve.** The baseline repeat brackets the
run-to-run scatter at ±0.002 mrad rms and ±7 mA/samp, so the compensator's
+0.021 mrad rms / +0.026 mrad residual is a real, if small, *regression* — and
the 2.6x jitter and 2.3x peak-current numbers are far outside any scatter.

**Mechanism.** `drive_friction_eval()` (`board-drive.c`) applies a hard
`sign(vel)` discontinuity carrying the full `IS` ≈ 2.13 A, driven off raw
`foc_state.ovel`. Across the trial:

- 125 `iq_fric` sign flips against **2** genuine velocity zero-crossings;
  88 of them at `|vel| < 10 mrad/s`.
- Each flip is a median **4.27 A** step injected into the current command.
- The viscous term `SIGMA2*v` peaks at only 0.172 A of the 2.142 A total, so
  essentially all of the injected signal is that discontinuity.

`ovel`'s noise floor (~3 mrad/s std, spikes to ~14 mrad/s — see
`reports/tune-friction-j1.md`) is wide enough to dither the sign term
continuously whenever the joint is near a reversal, and at 0.1 Hz the joint
crawls through each reversal slowly. The compensator is doing exactly what it
was written to do; the parameters are right for this joint. The problem is
that an unfiltered `sign()` on a noisy velocity estimate is a chatter source.

### Fix: smoothed sign (firmware change)

`sign(vel)` in `drive_friction_eval()` (`board-drive.c`) replaced with
`vel / sqrtf(vel*vel + v_eps*v_eps)`, `v_eps = DRIVE_FRIC_V_EPS = 0.030f`
rad/s — above the `ovel` noise floor, well under `v_s` = 0.1246 so the
Stribeck shape is untouched. The `vel == 0` early return is gone; the smooth
form returns exactly 0 there. Rebuilt `drive-debug-no-bl TRACE=MECH`; the
trace layout is unchanged, so captures stay comparable. Flashed manually.

Both builds carry the same `FW_GIT_HASH` (`a55cf6`, dirty) and
`FW_BUILD_NUMBER` (197), so a version query cannot tell them apart. Confirmed
behaviourally instead: recorded `iq_fric` against the recorded `ovel` matches
the smooth model with **0.0000 A rms residual** (exact) versus 0.7107 A rms
for the hard-sign model, and 1433/10040 samples have `|iq_fric| < 1.0 A`,
which the hard-sign form cannot produce.

| metric | base (old fw) | **hard sign** | base (new fw) | **smooth sign** |
|---|---|---|---|---|
| err rms | 0.436 mrad | 0.457 | 0.436 mrad | 0.437 |
| err residual | 0.344 mrad | 0.370 | 0.345 mrad | 0.346 |
| err max | 2.951 mrad | 2.884 | 2.951 mrad | 2.727 |
| `iq_fbk` max | 3.018 A | 6.834 | 2.914 A | 3.831 |
| `iq_cmd` jitter | 193.2 mA/samp | 499.8 | 195.6 mA/samp | **196.9** |
| `iq_fric` jump at flip | — | 4.27 A median | — | **0.62 A** median |

**The chatter is fixed.** Jitter is back to baseline (196.9 vs 195.6 mA/samp,
against 499.8 before) and peak current dropped from 6.834 A to 3.831 A. Sign
flips rose 125 -> 381, but that number is no longer meaningful: the smooth
form makes small excursions near zero, so crossings are frequent and cheap —
median jump fell 4.27 A -> 0.62 A, which is the quantity that mattered.

**Tracking error still does not improve.** 0.437 vs 0.436 mrad rms against a
measured run-to-run scatter of ±0.002 mrad — no change, in either direction.

**Why: friction is not what limits tracking here.** Splitting the error by
proximity to a velocity reversal, where stiction would show up:

| | `\|v\| < 30` mrad/s | `\|v\| >= 30` mrad/s |
|---|---|---|
| baseline | 0.399 mrad | 0.447 mrad |
| smooth comp | 0.431 mrad | 0.439 mrad |

The error is no worse at the reversals than away from them — there is no
stiction spike to remove. `err @fund` is 0.378 mrad of the 0.436 total, i.e.
the error is dominated by linear position-loop lag, and the cascade already
has ample authority over friction (peak demand ~3 A against a 5 A
`VEL_TQC_LIM`). The compensator is working as designed — `iq_cmd` rms falls
1.948 -> 1.844 A, so the feedforward does carry ~5% of the current burden —
it just relieves a loop that was not struggling.

If the goal is lower tracking error on this joint, friction compensation is
the wrong lever; `POS_KP`/`VEL_KP` and the position-loop bandwidth are where
the 0.378 mrad fundamental lives. The compensator is worth keeping enabled
only if the aim is reduced velocity-loop effort or better behaviour at
velocities far below this test's 0.116 rad/s peak.

### Step and ramp comparison (smooth sign)

Same firmware, same gains. `run-step.sh pos 0.138 500` and
`run-ramp.sh pos 0.3 3000` (0.1 rad/s, at the `v_s` = 0.1246 knee), comp off
vs on, alternated trial-by-trial so drift cannot favour either arm.

**Step — the compensator clearly helps** (n=4 each):

| metric | comp OFF | comp ON | |
|---|---|---|---|
| steady-state err | 7.255 mrad (6.83-7.85) | **3.898 mrad** (3.81-4.10) | -46% |
| rise time (10-90%) | 81.5 ms | **60.8 ms** | -25% |
| overshoot | 38.5 % | **29.8 %** | -8.7 pt |
| 2% settle | never, never, 497, 495 ms | **462-469 ms** (4/4) | |
| `iq_fbk` max | 5.094 A | **9.173 A** | +80% |
| `iq_cmd` jitter | 191.3 mA/samp | 229.2 mA/samp | +20% |

The steady-state distributions do not overlap (worst comp-on 4.10 mrad beats
best comp-off 6.83 mrad), so this is not scatter.

**Ramp — no meaningful change** (n=3 each):

| metric | comp OFF | comp ON |
|---|---|---|
| err rms | 0.737 mrad (0.731-0.743) | 0.725 mrad (0.720-0.728) |
| err max | 3.388 mrad | 3.263 mrad |
| tracking lag | -0.002 mrad | -0.002 mrad |
| `iq_fbk` max | 2.746 A | 2.899 A |

A consistent but negligible ~1.6% edge. (`txf-ramp.py`'s post-ramp overshoot
figure is meaningless for a pos ramp — it is measured against the scripted
snap-back to `start`, not a real overshoot. Ignore it.)

**This resolves the earlier negative result.** The compensator helps exactly
where the motion *stops*: the steady-state error at the end of a step is the
stiction dead-band, where the position integrator must wind up against
Coulomb friction to close the last few mrad, and the feedforward supplies that
current directly. Sine and ramp are continuous-motion tests — the joint never
dwells at zero velocity, friction is a slowly-varying bias the loop already
rejects, and there is nothing for the feedforward to win. The sine simply did
not exercise the regime the compensator was built for.

**Cost: `VEL_TQC_LIM` no longer bounds the current.** Peak `iq_fbk` goes
5.094 A -> 9.173 A, because the compensator is summed *after* the velocity
loop's clamp and is re-clipped against `FOC_I_TRIP` (12 A on this board), not
against `VEL_TQC_LIM` (5 A). The 5 A clamp is what normally protects the
joint, and with the compensator enabled it is advisory. Worth deciding
deliberately: either clip the sum at `VEL_TQC_LIM`, or set `VEL_TQC_LIM` in
the knowledge that the real ceiling is `FOC_I_TRIP`.

### Parameter sweep: scaling IC/IS

`FRIC_IC`/`FRIC_IS` scaled together (0.4-1.0 x the identified j0 values),
`SIGMA2`/`VS` held. Written via `Jx_CFG`; note the firmware range-checks
`IC <= i_s` and `IS >= i_c`, so a downward move must write **IC first** and an
upward move **IS first**, or the second write returns `CTRL_VAL_OOB_ERR`.

**Sine, 0.1 Hz** — jitter repeats to +/-0.6 mA/samp here, so it resolves:

| IC/IS scale | err rms | err resid | `iq_fbk` max | `iq_cmd` jitter |
|---|---|---|---|---|
| comp OFF | 0.436 mrad | 0.345 | 2.914 A | 195.6 mA/samp |
| 1.0 | 0.437 | 0.346 | 3.831 A | 196.9 |
| 0.8 | 0.434 | 0.343 | 3.704 A | **178.2** |
| 0.6 | 0.432 | 0.340 | 3.212 A | **168.4** |
| 0.4 | 0.429 | 0.336 | 2.881 A | **165.0** |

Monotonic: every metric improves as IC/IS come down. At 0.4 the jitter
(165.0) is 16% *below* the comp-off baseline — the feedforward supplies the
friction current smoothly so the velocity PID stops hunting for it.

**Step, 0.138 rad** — the trade-off (n=3 each):

| IC/IS scale | steady-state err | rise | overshoot | `iq_fbk` max |
|---|---|---|---|---|
| comp OFF | 7.095 mrad | 81.0 ms | 38.2% | 5.124 A |
| 1.0 | **3.832** | 60.7 ms | 29.6% | 9.174 A |
| 0.8 | 4.069 | 61.3 ms | 30.7% | 8.866 A |
| 0.6 | 4.284 | 62.7 ms | 31.5% | 8.498 A |
| 0.4 | 4.531 | 64.0 ms | 32.3% | 8.213 A |

Exactly opposite: step steady-state error degrades monotonically as IC/IS come
down, because closing the last few mrad at v -> 0 needs the full Coulomb
current. Every scale still beats comp-off (7.095) comfortably.

**Step jitter is not a usable chatter metric.** Within-set spread is
32-44 mA/samp against between-set differences of ~25 — the 540-sample window
is dominated by a few transient samples. None of the step jitter differences
here are significant, including the +20% quoted in the section above. Use the
sine for chatter.

**`SIGMA2` is the peak-current knob, not IC/IS** (all at scale 0.8, step):

| `SIGMA2` | steady-state err | `iq_fbk` max |
|---|---|---|
| 1.1957 | 4.069 mrad | 8.866 A |
| 0.60 | 4.389 | 7.600 A |
| 0.00 | 4.771 | 6.489 A |

Decomposing `iq_fric` at the step's 2.28 rad/s slew peak: viscous `SIGMA2*v` =
2.728 A against Stribeck 1.365 A, so the viscous term sets peak current.
Jitter splits the other way — Stribeck 100.2 of 105.4 mA/samp, viscous 22.7.
Two problems, two knobs.

**Where to sit.** Scale 0.8 (the requested -20%) is a sound operating point:
-10% sine jitter, step error only 6% off its best. Push to 0.6 for -14%
jitter at 12% worse step error. `SIGMA2` is worth reducing only if the 9 A
peak matters more than the last 0.7 mrad of step accuracy.

The sine wanting lower IC/IS is consistent with the j0 fit itself: its
`STRIBECK_VEL` 95% CI was [0.005, 0.245] rad/s and the sine's 0.114 rad/s peak
sits inside that poorly-constrained knee, so the model likely overestimates
friction there.

### Firmware bug found: pos test commands saturate at the wrap boundary

`test_servo_step_cmd()` does `pos_cmd = (int32_t)(dg->pos_ref + val)` in
float, and `test_servo_sine_cmd()` the same through `servo_pos_cmd_set()`.
When `pos_ref + val` exceeds `INT32_MAX` the float->int32 cast **saturates**
at `INT32_MAX` (= +pi rad) instead of wrapping. This defeats the design
invariant in `src/servo.h` -- "two's-complement wrap makes the position error
and the host-frame gap exact across the rev boundary with no wrap logic" --
because the value leaves the int32 domain on the way through float.

Symptom: every pos step and ramp moves the joint one way, so it walks toward
the boundary over a session. Four captures here silently ran with commanded
steps of 75.0, 14.1, 6.5 and 3.2 mrad instead of 138.0, and the truncated ones
reported a *spectacular* 0.059 mrad steady-state error -- a tiny step the loop
closes easily, which reads as a 120x improvement if the step size is not
checked. Discarded and re-run after walking the joint back with
`run-step.sh vel -0.5 6000`; a velocity step is the only one of these tests
that does not return to its start.

**Check `step +138.000` in the `txf-step.py` header before trusting a pos
capture.** Suggested fix: keep the arithmetic in int32 (`pos_ref + (int32_t)val`)
so it wraps, matching the servo loop's own convention.

### Board state left behind

Gains as written above (verified by readback after the reflash — a reset
zeroes them). `FEATURE_FRIC_COMP` is **enabled** from the last capture; clear
it with `{"command":"Jx_STATUS","action":"WRITE","mode":"VEL"}` if that is not
wanted. Compiled friction parameters unmodified. No tunables files touched.
The `board-drive.c` change is **uncommitted** in `../module-fwpp`.

### Captures

Hard sign (`traces/j0-gains-fric-validate/`): `base.0000.txf`,
`fric.0000.txf`, `base2.0000.txf` (scatter).
Smooth sign (`traces/j0-fric-smooth/`): sine `base.0000.txf` / `fric.0000.txf`;
step `pstep_base` / `pstep_fric` / `rep_base.000{0,1,2}` / `rep_fric.000{0,1,2}`;
ramp `pramp_base` / `pramp_fric` / `rrep_base.000{0,1}` / `rrep_fric.000{0,1}`.
