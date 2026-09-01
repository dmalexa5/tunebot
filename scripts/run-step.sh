#!/bin/zsh
# run-step.sh [-i IP] [-r] mode step hold_ms [base] [stride] [prefix]
#   mode: pos | vel | torque
# Runs a servo_step test (rtttest): settle at base, step to base+step for
# hold_ms, fall back to base. Writes <prefix>.NNNN.txf in the current
# directory. See module-fwpp/cheatsheet.md "servo step" section.
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json

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
STEP=$2
HOLD_MS=$3

case "$MODE_NAME" in
	torque) MODE=0; DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tstep ;;
	vel)    MODE=1; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vstep ;;
	pos)    MODE=2; DEFAULT_STRIDE=20; DEFAULT_PREFIX=pstep ;;
	*) echo "usage: run-step.sh [-i IP] [-r] {pos|vel|torque} step hold_ms [base] [stride] [prefix]" >&2; exit 1 ;;
esac
BASE=${4:-0.0}
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

"$RTTTEST" -n -s "$TABLES" -i "$IP" $RFLAG -o "$PREFIX" \
	"{\"test\":\"servo_step\",\"mode\":$MODE,\"step\":$STEP,\"base\":$BASE,\"stride\":$STRIDE,\"hold_ms\":$HOLD_MS}"
