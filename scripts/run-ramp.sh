#!/bin/zsh
# run-ramp.sh [-i IP] [-r] mode delta duration_ms [start] [stride] [prefix]
#   mode: pos | vel | torque
#   delta/start units: rad (pos), rad/s (vel), A (torque)
# Runs a ramp_servo test (rtttest): settle at start, linearly ramp to
# start+delta over duration_ms, fall back to start. Writes <prefix>.NNNN.txf
# in the current directory. See module-fwpp/cheatsheet.md "Tests (rtttest)"
# section. Raise stride for long ramps -- the link can't sustain full rate
# (see cheatsheet.md "Trace throughput").
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
DURATION_MS=$3

case "$MODE_NAME" in
	torque) MODE=0; SCALE=1;           DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tramp ;;
	vel)    MODE=1; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vramp ;;
	pos)    MODE=2; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=20; DEFAULT_PREFIX=pramp ;;
	*) echo "usage: run-ramp.sh [-i IP] [-r] {pos|vel|torque} delta duration_ms [start] [stride] [prefix]" >&2; exit 1 ;;
esac
DELTA=$(to_cmd $2)
START=$(to_cmd ${4:-0.0})
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

"$RTTTEST" -n -s "$TABLES" -i "$IP" $RFLAG -o "$PREFIX" \
	"{\"test\":\"ramp_servo\",\"mode\":$MODE,\"delta\":$DELTA,\"start\":$START,\"stride\":$STRIDE,\"duration_ms\":$DURATION_MS}"
