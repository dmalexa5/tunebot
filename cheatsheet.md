# Test commands

Run from the repository root. Position is in radians, velocity in radians/s,
and torque in amps unless noted otherwise.

```sh
# environment
source env.zsh
```

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
run-sine.sh -i 100.79.218.29 pos 1 0.05 5
# ip mode frequency amplitude cycles
run-sine.sh -i 100.79.218.29 vel 1 0.2 5
# ip mode frequency amplitude cycles decimation
run-sine.sh -i 100.79.218.29 torque 10 0.1 5 3
```

## Chirp

Chirp position and velocity amplitudes use output-shaft counts and counts/s;
torque amplitude uses amps.

```sh
RTTTEST=../module-fwpp/tools/rttcmd/rtttest
TABLES=../module-fwpp/output/drive/none/drive-none.tables.json

# tables ip output test signal amplitude start end duration logging taper decimation
$RTTTEST -n -s $TABLES -i 100.79.218.29 -o pchirp '{"test":"signal_chirp","signal":"pos","amplitude":1e6,"f0_hz":1,"f1_hz":100,"duration_ms":3000,"log":true,"taper":true,"decimation":20}'
# tables ip output test signal amplitude start end duration logging taper decimation
$RTTTEST -n -s $TABLES -i 100.79.218.29 -o vchirp '{"test":"signal_chirp","signal":"vel","amplitude":1e7,"f0_hz":1,"f1_hz":200,"duration_ms":3000,"log":true,"taper":true,"decimation":4}'
# tables ip output test signal amplitude start end duration logging decimation
$RTTTEST -n -s $TABLES -i 100.79.218.29 -o tqchirp '{"test":"signal_chirp","signal":"iq","amplitude":0.3,"f0_hz":10,"f1_hz":2000,"duration_ms":500,"log":true,"decimation":2}'
```
