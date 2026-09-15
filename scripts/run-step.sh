#!/bin/zsh
# run-step.sh [-i IP] [-r] mode step hold_ms [base] [stride] [prefix]
#   mode: pos | vel | torque
#   step/base units: rad (pos), rad/s (vel), A (torque)
# Runs a servo_step test (rtttest): settle at base, step to base+step for
# hold_ms, fall back to base. Writes <prefix>.NNNN.txf in the current
# directory. See module-fwpp/cheatsheet.md "Tests (rtttest)" section.
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json

# The servo loop speaks output-shaft counts (2^32/rev) and counts/s --
# "radians appear nowhere" (module-fwpp src/servo.h). pos/vel arguments are
# rad/rad-per-s and get converted here; torque is amps and passes through.
RAD_TO_CNT=$(( 4294967296.0 / (2 * 3.14159265358979324) ))
to_cmd(){   # scales by $SCALE, which the mode case below sets
	if [[ $SCALE == 1 ]]; then print -- $1; else printf %.0f $(( $1 * SCALE )); fi
}

IP=127.0.0.1
RFLAG=()
while [[ "$1" == -* ]]; do
	case "$1" in
		-i) IP=$2; shift 2 ;;
		-r) RFLAG=(-r); shift ;;
		*) echo "unknown flag: $1" >&2; exit 1 ;;
	esac
done

MODE_NAME=$1
HOLD_MS=$3

case "$MODE_NAME" in
	torque) MODE=0; SCALE=1;           DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tstep ;;
	vel)    MODE=1; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vstep ;;
	pos)    MODE=2; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=20; DEFAULT_PREFIX=pstep ;;
	*) echo "usage: run-step.sh [-i IP] [-r] {pos|vel|torque} step hold_ms [base] [stride] [prefix]" >&2; exit 1 ;;
esac
STEP=$(to_cmd $2)
BASE=$(to_cmd ${4:-0.0})
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

"$RTTTEST" -n -s "$TABLES" -i "$IP" $RFLAG -o "$PREFIX" \
	"{\"test\":\"servo_step\",\"mode\":$MODE,\"step\":$STEP,\"base\":$BASE,\"stride\":$STRIDE,\"hold_ms\":$HOLD_MS}"
