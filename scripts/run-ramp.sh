#!/bin/zsh
# run-ramp.sh [-i IP] [-r] mode delta duration_ms [start] [stride] [prefix]
#   mode: pos | vel | torque
# Runs a ramp_servo test (rtttest): settle at start, linearly ramp to
# start+delta over duration_ms, fall back to start. Writes <prefix>.NNNN.txf
# in the current directory. See module-fwpp/cheatsheet.md "servo ramp"
# section. Raise stride for long ramps -- the link can't sustain full rate
# (see cheatsheet.md "Trace throughput").
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
DELTA=$2
DURATION_MS=$3

case "$MODE_NAME" in
	torque) MODE=0; DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tramp ;;
	vel)    MODE=1; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vramp ;;
	pos)    MODE=2; DEFAULT_STRIDE=20; DEFAULT_PREFIX=pramp ;;
	*) echo "usage: run-ramp.sh [-i IP] [-r] {pos|vel|torque} delta duration_ms [start] [stride] [prefix]" >&2; exit 1 ;;
esac
START=${4:-0.0}
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

"$RTTTEST" -n -s "$TABLES" -i "$IP" $RFLAG -o "$PREFIX" \
	"{\"test\":\"ramp_servo\",\"mode\":$MODE,\"delta\":$DELTA,\"start\":$START,\"stride\":$STRIDE,\"duration_ms\":$DURATION_MS}"
