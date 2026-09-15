#!/bin/zsh
# run-sine.sh [-i IP] [-r] [-f] mode freq_hz amp [cycles] [stride] [prefix]
#   mode: pos | vel | torque
#   amp units: rad (pos), rad/s (vel), A (torque)
# Runs a servo_sine test (rtttest) and writes <prefix>.NNNN.txf in the
# current directory. See module-fwpp/cheatsheet.md "Tests (rtttest)" section.
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
FF=false
while [[ "$1" == -* ]]; do
	case "$1" in
		-i) IP=$2; shift 2 ;;
		-r) RFLAG=(-r); shift ;;
		-f) FF=true; shift ;;
		*) echo "unknown flag: $1" >&2; exit 1 ;;
	esac
done

MODE_NAME=$1
FREQ_HZ=$2
CYCLES=${4:-2}

case "$MODE_NAME" in
	torque) MODE=0; SCALE=1;           DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tsine ;;
	vel)    MODE=1; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vsine ;;
	pos)    MODE=2; SCALE=$RAD_TO_CNT; DEFAULT_STRIDE=20; DEFAULT_PREFIX=psine ;;
	*) echo "usage: run-sine.sh [-i IP] [-r] [-f] {pos|vel|torque} freq_hz amp [cycles] [stride] [prefix]" >&2; exit 1 ;;
esac
AMP=$(to_cmd $3)
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

"$RTTTEST" -n -s "$TABLES" -i "$IP" $RFLAG -o "$PREFIX" \
	"{\"test\":\"servo_sine\",\"mode\":$MODE,\"freq_hz\":$FREQ_HZ,\"amp\":$AMP,\"cycles\":$CYCLES,\"stride\":$STRIDE,\"ff\":$FF}"
