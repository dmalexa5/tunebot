#!/bin/zsh
# run-sine.sh [-i IP] [-r] [-f] mode freq_hz amp [cycles] [stride] [prefix]
#   mode: pos | vel | torque
# Runs a servo_sine test (rtttest) and writes <prefix>.NNNN.txf in the
# current directory. See module-fwpp/cheatsheet.md "servo sine" section.
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json

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
AMP=$3
CYCLES=${4:-2}

case "$MODE_NAME" in
	torque) MODE=0; DEFAULT_STRIDE=1;  DEFAULT_PREFIX=tsine ;;
	vel)    MODE=1; DEFAULT_STRIDE=12; DEFAULT_PREFIX=vsine ;;
	pos)    MODE=2; DEFAULT_STRIDE=20; DEFAULT_PREFIX=psine ;;
	*) echo "usage: run-sine.sh [-i IP] [-r] [-f] {pos|vel|torque} freq_hz amp [cycles] [stride] [prefix]" >&2; exit 1 ;;
esac
STRIDE=${5:-$DEFAULT_STRIDE}
PREFIX=${6:-$DEFAULT_PREFIX}

"$RTTTEST" -n -s "$TABLES" -i "$IP" $RFLAG -o "$PREFIX" \
	"{\"test\":\"servo_sine\",\"mode\":$MODE,\"freq_hz\":$FREQ_HZ,\"amp\":$AMP,\"cycles\":$CYCLES,\"stride\":$STRIDE,\"ff\":$FF}"
