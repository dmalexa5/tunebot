# Test commands

Run from the repository root. Position is in radians, velocity in radians/s,
and torque in amps unless noted otherwise.

```sh
# environment
source env.zsh
```

## What the wrappers do

Since `module-fwpp` 0b9351e the firmware has one waveform engine
(`signal_step` / `signal_ramp` / `signal_sine` / `signal_chirp`) and no
`servo_*` / `foc_*` tests. The engine only *superimposes a delta* on a
command — it does not pick a control mode and it does not stop the joint when
it finishes. So each `run-*.sh`:

1. writes the FOC mode (`Jx_STATUS`): `pos` -> `POS`, `vel` -> `VEL`,
   `torque` -> `0TQ` with the waveform on `iq`;
2. runs the waveform with `start_pad = end_pad = 20 * stride` ticks, which is
   the fixed 20-sample baseline/tail the `txf-*.py` analyzers slice off;
3. writes `mode:0TQ` again on every exit path, including Ctrl-C and a failed
   capture. Without that a `vel` ramp would keep the joint turning — a ramp
   ends *holding its target*, it does not come back down.

Three consequences worth remembering:

- **`base` / `start` must be 0.** The waveform rides whatever the mode change
  leaves behind (0 A in `0TQ`, `vel_cmd` 0 on a VEL enable, `pos_cmd =
  pos_fbk` on a POS enable). A non-zero value is rejected.
- **`torque` is now a direct `iq` command** with the cascade off, so
  `VEL_TQC_LIM` does not clamp it and friction compensation does not apply
  (it needs the velocity loop). Only `FOC_I_TRIP` bounds it.
- **`-F` keeps `FEATURE_FRIC_COMP` set.** Writing a mode rebuilds the whole
  ctrl word, so a plain `run-*.sh` clears the compensator bit.

## Run length limit

The engine's timeline is raw 20 kHz servo ticks in a `uint16`:
`start_pad + duration + end_pad` must stay under 65535, i.e. **~3.27 s per
capture including the pads**. The scripts check this and refuse rather than
let the firmware truncate silently.

| | practical cap |
|---|---|
| `run-step.sh` / `run-ramp.sh`, stride 1 / 12 / 20 | 3274 / 3252 / 3236 ms |
| `run-sine.sh`, one cycle at stride 20 | freq >= 0.31 Hz |
| `run-sine.sh`, stride 20 | 3 cycles @ 1 Hz, 1 cycle @ 0.5 Hz |

`run-sine.sh` also prints the realized frequency, because the engine takes a
whole-tick period: pass *that* number to `txf-sine.py`, not the requested one.

## Step

```sh
# ip mode step hold
run-step.sh -i 100.79.218.29 pos 0.1 500
# ip mode step hold
run-step.sh -i 100.79.218.29 vel 0.2 500
# ip mode step hold base decimation
run-step.sh -i 100.79.218.29 torque 0.1 500 0 3
```

## Ramp

```sh
# ip mode delta duration
run-ramp.sh -i 100.79.218.29 pos 0.1 1000
# ip mode delta duration
run-ramp.sh -i 100.79.218.29 vel 0.2 1000
# ip mode delta duration start decimation
run-ramp.sh -i 100.79.218.29 torque 0.1 1000 0 3
```

## Sine

```sh
# ip mode frequency amplitude cycles
run-sine.sh -i 100.79.218.29 pos 1 0.05 3
# ip mode frequency amplitude cycles
run-sine.sh -i 100.79.218.29 vel 1 0.2 3
# ip mode frequency amplitude cycles decimation
run-sine.sh -i 100.79.218.29 torque 10 0.1 5 3
```

## Chirp

Chirp position and velocity amplitudes use output-shaft counts and counts/s;
torque amplitude uses amps. There is no wrapper, so set the mode and clear it
yourself — `signal_chirp` on `vel`/`pos` needs `VEL`/`POS` selected first and
leaves the loop enabled afterwards.

```sh
RTTTEST=../module-fwpp/tools/rttcmd/rtttest
RTTTASK=../module-fwpp/tools/rttcmd/rtttask
TABLES=../module-fwpp/output/drive/none/drive-none.tables.json

$RTTTASK -i 100.79.218.29 '{"command":"Jx_STATUS","action":"WRITE","mode":"POS"}'
# tables ip output test signal amplitude start end duration logging taper decimation
$RTTTEST -n -s $TABLES -i 100.79.218.29 -o pchirp '{"test":"signal_chirp","signal":"pos","amplitude":1e6,"f0_hz":1,"f1_hz":100,"duration_ms":3000,"log":true,"taper":true,"decimation":20}'
$RTTTASK -i 100.79.218.29 '{"command":"Jx_STATUS","action":"WRITE","mode":"0TQ"}'

$RTTTASK -i 100.79.218.29 '{"command":"Jx_STATUS","action":"WRITE","mode":"VEL"}'
# tables ip output test signal amplitude start end duration logging taper decimation
$RTTTEST -n -s $TABLES -i 100.79.218.29 -o vchirp '{"test":"signal_chirp","signal":"vel","amplitude":1e7,"f0_hz":1,"f1_hz":200,"duration_ms":3000,"log":true,"taper":true,"decimation":4}'
$RTTTASK -i 100.79.218.29 '{"command":"Jx_STATUS","action":"WRITE","mode":"0TQ"}'

# iq rides the raw current command, so the cascade must be off (0TQ)
$RTTTASK -i 100.79.218.29 '{"command":"Jx_STATUS","action":"WRITE","mode":"0TQ"}'
# tables ip output test signal amplitude start end duration logging decimation
$RTTTEST -n -s $TABLES -i 100.79.218.29 -o tqchirp '{"test":"signal_chirp","signal":"iq","amplitude":0.3,"f0_hz":10,"f1_hz":2000,"duration_ms":500,"log":true,"decimation":2}'
```

`duration_ms` is capped at 3276 ms by the same `uint16` tick timeline.

## Friction compensator (Jx_CFG)

Seven parameters as of `protocols` eaf82c5; `FRIC_SRC` is int, the rest float.

| addr | firmware default | meaning |
|---|---|---|
| `FRIC_IC` | 1.40 A | Coulomb current |
| `FRIC_IS` | 2.1286 A | static / breakaway current |
| `FRIC_SIGMA2` | 1.2 A/(rad/s) | viscous term |
| `FRIC_VS` | 0.030 rad/s | Stribeck velocity |
| `FRIC_VEPS` | 0.030 rad/s | zero-crossing smoothing half-width |
| `FRIC_LPF` | 1.0 (off) | 1-pole IIR on the velocity input, at 20 kHz |
| `FRIC_SRC` | 1 | 0 = measured `ovel`, 1 = `vel_cmd` (ff), 2 = measured `mvel` |

`FRIC_SRC=0` requires `FRIC_LPF ~= 0.005` (16 Hz) or the compensator
limit-cycles at ~33 Hz, and it still falls apart above ~2 Hz reversals — see
`module-fwpp/cheatsheet.md`. Enable with
`{"command":"Jx_STATUS","action":"WRITE","ctrl":"FEATURE_FRIC_COMP","mode":"VEL"}`,
and use `-F` on the run scripts to keep the bit set.
