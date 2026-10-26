#!/bin/zsh
# run-sine.sh [-i IP] [-r] [-c FLAG]... mode freq_hz amp [cycles] [stride] [prefix]
#   mode: pos | vel | torque
#   amp units: rad (pos), rad/s (vel), A (torque)
#   -c FLAG: extra Jx_STATUS ctrl bit to set with the mode (repeatable),
#            e.g. VEL_USE_MENC; every mode write replaces the whole ctrl word
# Selects the FOC control mode, runs a signal_sine (rtttest) of `cycles` whole
# cycles on the matching command, then returns the joint to FOC
# (cascade disabled). Writes <prefix>.NNNN.txf in the current directory. See
# module-fwpp/cheatsheet.md "Signal injection (rtttest signal_*)".
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
RTTTASK=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttask
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json

# The servo loop speaks output-shaft counts (2^32/rev) and counts/s --
# "radians appear nowhere" (module-fwpp src/drive-control.h vel_fbk).
# pos/vel arguments are rad/rad-per-s and get converted here; torque is amps
# and passes through.
RAD_TO_CNT=$(( 4294967296.0 / (2 * 3.14159265358979324) ))
to_cmd(){   # scales by $SCALE, which the mode case below sets
	if [[ $SCALE == 1 ]]; then print -- $1; else printf %.0f $(( $1 * SCALE )); fi
}

# The signal engine's timeline is raw 20 kHz servo ticks in a uint16
# (test-signal.c rejects start_pad+duration+end_pad >= 65535, and the sine's
# period is itself a uint16). The pads are what produce the fixed
# baseline/tail the txf-*.py analyzers slice off as EDGE, so they are
# EDGE_SAMPLES *captured samples* worth of ticks.
SERVO_HZ=20000
EDGE_SAMPLES=20
TICKS_MAX=65534

IP=127.0.0.1
RFLAG=()
CTRL=()
FEAT_JSON=
while [[ "$1" == -* ]]; do
	case "$1" in
		-i) IP=$2; shift 2 ;;
		-r) RFLAG=(-r); shift ;;
		-c) CTRL+=($2); shift 2 ;;
		*) echo "unknown flag: $1" >&2; exit 1 ;;
	esac
done

MODE_NAME=$1
FREQ_HZ=$2
CYCLES=${4:-2}

case "$MODE_NAME" in
	torque) FOC_MODE=FOC; SIGNAL=iq;  SCALE=1;           DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tsine ;;
	vel)    FOC_MODE=VEL; SIGNAL=vel; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vsine ;;
	pos)    FOC_MODE=POS; SIGNAL=pos; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=20; DEFAULT_PREFIX=psine ;;
	*) echo "usage: run-sine.sh [-i IP] [-r] [-c FLAG]... {pos|vel|torque} freq_hz amp [cycles] [stride] [prefix]" >&2; exit 1 ;;
esac
AMP=$(to_cmd $3)
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

# The engine takes a whole-tick period, not a frequency, so the realized
# frequency is SERVO_HZ/round(SERVO_HZ/freq_hz). Report it: txf-sine.py takes
# the frequency as its DFT bin and a mismatch shows up as leakage.
PERIOD=$(printf %.0f $(( 1.0 * SERVO_HZ / FREQ_HZ )))
PAD=$(( EDGE_SAMPLES * STRIDE ))
DURATION=$(( PERIOD * CYCLES ))
if (( PERIOD < 2 )); then
	echo "run-sine.sh: ${FREQ_HZ} Hz is above the ${SERVO_HZ} Hz servo tick rate" >&2
	exit 1
fi
if (( PERIOD > TICKS_MAX )); then
	echo "run-sine.sh: ${FREQ_HZ} Hz is a ${PERIOD}-tick period; the signal engine's uint16 timeline caps one cycle at ${TICKS_MAX} ticks (>= $(printf %.4f $(( 1.0 * SERVO_HZ / TICKS_MAX ))) Hz)" >&2
	exit 1
fi
if (( 2 * PAD + DURATION > TICKS_MAX )); then
	echo "run-sine.sh: ${CYCLES} cycles at ${FREQ_HZ} Hz, stride ${STRIDE} needs $(( 2 * PAD + DURATION )) servo ticks; the signal engine's uint16 timeline caps a run at ${TICKS_MAX} (~3.27 s including the ${EDGE_SAMPLES}-sample pads)" >&2
	exit 1
fi
print -u2 -- "run-sine.sh: period ${PERIOD} ticks -> $(printf %.6g $(( 1.0 * SERVO_HZ / PERIOD ))) Hz (pass this to txf-sine.py)"

# The signal tests neither select a mode nor stop the joint when they finish
# (the old servo_* tests did both). Leaving VEL/POS enabled means the joint
# keeps servoing after the capture, so drop to FOC with the cascade
# disabled on every exit path.
STOPPED=0
stop_motion(){
	if (( STOPPED )); then return 0; fi
	STOPPED=1
	# Keep the -c flags: changing VEL_USE_MENC while enabled is refused (CTRL_BUSY).
	"$RTTTASK" -i "$IP" "{\"command\":\"Jx_STATUS\",\"action\":\"WRITE\",\"ctrl\":[$FEAT_JSON],\"mode\":\"FOC\"}" >/dev/null 2>&1 || true
	"$RTTTASK" -i "$IP" '{"command":"Jx_IDQ","action":"WRITE","id":0,"iq":0,"mvel":0,"mpos":0}' >/dev/null 2>&1 || true
}
trap 'stop_motion; exit 130' INT TERM
trap stop_motion EXIT

# Every mode needs ENABLE: torque injection rides the vel stage feedforward.
for flag in $CTRL; do FEAT_JSON+="${FEAT_JSON:+,}\"$flag\""; done
CTRL_JSON="\"ENABLE\"${FEAT_JSON:+,}$FEAT_JSON"
"$RTTTASK" -i "$IP" $RFLAG \
	"{\"command\":\"Jx_STATUS\",\"action\":\"WRITE\",\"ctrl\":[$CTRL_JSON],\"mode\":\"$FOC_MODE\"}" >/dev/null

"$RTTTEST" -n -s "$TABLES" -i "$IP" -o "$PREFIX" \
	"{\"test\":\"signal_sine\",\"signal\":\"$SIGNAL\",\"amplitude\":$AMP,\"period\":$PERIOD,\"ncycles\":$CYCLES,\"start_pad\":$PAD,\"end_pad\":$PAD,\"decimation\":$STRIDE}"
