#!/bin/zsh
# run-step.sh [-i IP] [-r] [-F] mode step hold_ms [base] [stride] [prefix]
#   mode: pos | vel | torque
#   step/base units: rad (pos), rad/s (vel), A (torque)
#   -F: keep FEATURE_FRIC_COMP set when selecting the mode
# Selects the FOC control mode, runs a signal_step (rtttest) that rides the
# matching command up by `step` for hold_ms and back down, then returns the
# joint to 0TQ. Writes <prefix>.NNNN.txf in the current directory. See
# module-fwpp/cheatsheet.md "Signal injection (rtttest signal_*)".
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
RTTTASK=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttask
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json

# The servo loop speaks output-shaft counts (2^32/rev) and counts/s --
# "radians appear nowhere" (module-fwpp src/servo.h). pos/vel arguments are
# rad/rad-per-s and get converted here; torque is amps and passes through.
RAD_TO_CNT=$(( 4294967296.0 / (2 * 3.14159265358979324) ))
to_cmd(){   # scales by $SCALE, which the mode case below sets
	if [[ $SCALE == 1 ]]; then print -- $1; else printf %.0f $(( $1 * SCALE )); fi
}

# The signal engine's timeline is raw 20 kHz servo ticks in a uint16
# (test-signal.c rejects start_pad+duration+end_pad >= 65535). The pads are
# what produce the fixed baseline/tail the txf-*.py analyzers slice off as
# EDGE, so they are EDGE_SAMPLES *captured samples* worth of ticks.
TICKS_PER_MS=20
EDGE_SAMPLES=20
TICKS_MAX=65534

IP=127.0.0.1
RFLAG=()
FRIC=
while [[ "$1" == -* ]]; do
	case "$1" in
		-i) IP=$2; shift 2 ;;
		-r) RFLAG=(-r); shift ;;
		-F) FRIC='"ctrl":"FEATURE_FRIC_COMP",'; shift ;;
		*) echo "unknown flag: $1" >&2; exit 1 ;;
	esac
done

MODE_NAME=$1
HOLD_MS=$3

case "$MODE_NAME" in
	torque) FOC_MODE=0TQ; SIGNAL=iq;  SCALE=1;           DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tstep ;;
	vel)    FOC_MODE=VEL; SIGNAL=vel; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vstep ;;
	pos)    FOC_MODE=POS; SIGNAL=pos; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=20; DEFAULT_PREFIX=pstep ;;
	*) echo "usage: run-step.sh [-i IP] [-r] [-F] {pos|vel|torque} step hold_ms [base] [stride] [prefix]" >&2; exit 1 ;;
esac
STEP=$(to_cmd $2)
BASE=${4:-0.0}
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

# The engine superimposes its waveform on whatever is already driving the
# command and has no baseline of its own, so a step always rides the value
# the mode change leaves behind: 0 A in 0TQ, vel_cmd 0 on a VEL enable,
# pos_cmd = pos_fbk on a POS enable.
if (( BASE != 0 )); then
	echo "run-step.sh: base must be 0 -- signal_step injects a delta onto the live command, it cannot settle at a base first" >&2
	exit 1
fi

PAD=$(( EDGE_SAMPLES * STRIDE ))
DURATION=$(( HOLD_MS * TICKS_PER_MS ))
if (( DURATION < 1 )); then
	echo "run-step.sh: hold_ms must be at least 1" >&2
	exit 1
fi
if (( 2 * PAD + DURATION > TICKS_MAX )); then
	echo "run-step.sh: ${HOLD_MS} ms at stride ${STRIDE} needs $(( 2 * PAD + DURATION )) servo ticks; the signal engine's uint16 timeline caps a run at ${TICKS_MAX} (~3.27 s including the ${EDGE_SAMPLES}-sample pads)" >&2
	exit 1
fi

# The signal tests neither select a mode nor stop the joint when they finish
# (the old servo_* tests did both). Leaving VEL/POS enabled means the joint
# keeps servoing after the capture, so drop to 0TQ on every exit path.
STOPPED=0
stop_motion(){
	if (( STOPPED )); then return 0; fi
	STOPPED=1
	"$RTTTASK" -i "$IP" '{"command":"Jx_STATUS","action":"WRITE","mode":"0TQ"}' >/dev/null 2>&1 || true
	# 0TQ disables the cascade but leaves the direct current command intact.
	"$RTTTASK" -i "$IP" '{"command":"Jx_IDQ","action":"WRITE","id":0,"iq":0,"mvel":0,"mpos":0}' >/dev/null 2>&1 || true
}
trap 'stop_motion; exit 130' INT TERM
trap stop_motion EXIT

"$RTTTASK" -i "$IP" $RFLAG \
	"{\"command\":\"Jx_STATUS\",\"action\":\"WRITE\",${FRIC}\"mode\":\"$FOC_MODE\"}" >/dev/null

"$RTTTEST" -n -s "$TABLES" -i "$IP" -o "$PREFIX" \
	"{\"test\":\"signal_step\",\"signal\":\"$SIGNAL\",\"step\":$STEP,\"duration\":$DURATION,\"start_pad\":$PAD,\"end_pad\":$PAD,\"decimation\":$STRIDE}"
