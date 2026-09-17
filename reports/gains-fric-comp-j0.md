# j0 gains and friction compensation — 48 V

Historical trial on `100.79.218.29`, firmware `a55cf61` (build 197, DEBUG,
TRACE=MECH). Its 0.1 Hz tests and 6 s repositioning command are unsupported by
current wrappers. Results below describe that session, not current board state.

Gains: VEL_KP=24, VEL_KI=0.6, POS_KP=20, POS_KI=0.15, current limit 5 A,
velocity limit π rad/s; KD=0. Written with `set-gains.sh`, count-domain
VEL_KP readback 3.511e-08. Friction: Ic=1.7063 A, Is=2.1286 A,
sig2=1.1957 A/(rad/s), vs=0.1246 rad/s.

## Hard versus smooth sign

At 0.1 Hz, 0.138 rad position amplitude:

| Metric | Baseline | Hard sign | Smooth sign |
|---|---|---|---|
| Tracking RMS (mrad) | 0.436 | 0.457 | 0.437 |
| Current peak (A) | 3.018 | 6.834 | 3.831 |
| iq_cmd jitter (mA/sample) | 193.2 | 499.8 | 196.9 |

Raw velocity noise caused 125 friction-current sign flips for 2 real reversals,
with median 4.27 A jumps. Firmware smoothing `v / sqrt(v² + 0.030²)` removed
the excess chatter but did not improve sine tracking. Dirty hard/smooth builds
shared the same version identifiers; trace/model comparison distinguished them.

## Motion and parameter tradeoffs

Smooth compensation improved 0.138 rad steps (4 trials each): steady-state
error 7.255→3.898 mrad, rise 81.5→60.8 ms, overshoot 38.5→29.8%.
Peak current rose 5.094→9.173 A. A 0.1 rad/s ramp showed little improvement:
tracking RMS 0.737→0.725 mrad (3 trials each).

| Ic/Is scale | Sine jitter (mA/sample) | Step error (mrad) | Step peak (A) |
|---|---|---|---|
| Off | 195.6 | 7.095 | 5.124 |
| 1.0 | 196.9 | 3.832 | 9.174 |
| 0.8 | 178.2 | 4.069 | 8.866 |
| 0.6 | 168.4 | 4.284 | 8.498 |
| 0.4 | 165.0 | 4.531 | 8.213 |

Scale 0.8 balanced sine chatter and step accuracy. At that scale, reducing sig2
from 1.1957 to 0.6/0 reduced step peaks to 7.600/6.489 A, with error
4.389/4.771 mrad. Step jitter differences were smaller than trial scatter.

## Caveats and provenance

- Compensation was added after the velocity clamp, so `VEL_TQC_LIM` did not
  bound total current; `FOC_I_TRIP` was 12 A.
- Firmware enforced Ic≤Is: when scaling down write Ic first; up, Is first.
- Old position-test float-to-int32 casts saturated at +π, producing undersized
  commands and misleading errors. Verify measured command amplitude.
- At session end compensation was enabled, no tunables were changed, and
  the smoothing edit in `../module-fwpp` was uncommitted.

Captures: `traces/j0-gains-fric-validate/` (`base`, `fric`, `base2`);
`traces/j0-fric-smooth/` (`base`, `fric`, `pstep_base`, `pstep_fric`,
`rep_base`, `rep_fric`, `pramp_base`, `pramp_fric`, `rrep_base`, `rrep_fric`).
