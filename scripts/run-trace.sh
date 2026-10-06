#!/bin/zsh
# run-trace.sh [-i IP] [-r] mode [stride] [prefix]
# Capture 3 seconds of the selected drive-board trace set without changing the
# control mode or applying a nonzero signal. The zero-step signal arms RTTTrace.
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json

# Signal-test timeline is in 20 kHz servo ticks. Three seconds is 60000 ticks;
# default stride 20 keeps the trace stream at 1 kHz and within RTT throughput.
DURATION=60000
IP=127.0.0.1
RFLAG=()
while [[ "$1" == -* ]]; do
	case "$1" in
		-i) IP=$2; shift 2 ;;
		-r) RFLAG=(-r); shift ;;
		*) echo "unknown flag: $1" >&2; exit 1 ;;
	esac
done

if (( $# < 1 || $# > 3 )); then
	echo "usage: run-trace.sh [-i IP] [-r] {pos|vel|torque} [stride] [prefix]" >&2
	exit 1
fi
MODE=$1
case "$MODE" in
	pos)    SIGNAL=pos; DEFAULT_PREFIX=trace ;;
	vel)    SIGNAL=vel; DEFAULT_PREFIX=trace ;;
	torque) SIGNAL=iq;  DEFAULT_PREFIX=trace ;;
	*) echo "run-trace.sh: mode must be pos, vel, or torque" >&2; exit 1 ;;
esac
STRIDE=${2:-20}
PREFIX=${3:-$DEFAULT_PREFIX}
if (( STRIDE < 1 || STRIDE > 255 )); then
	echo "run-trace.sh: stride must be between 1 and 255" >&2
	exit 1
fi

"$RTTTEST" -n -s "$TABLES" -i "$IP" $RFLAG -o "$PREFIX" \
	"{\"test\":\"signal_step\",\"signal\":\"$SIGNAL\",\"step\":0,\"duration\":$DURATION,\"start_pad\":0,\"end_pad\":0,\"decimation\":$STRIDE}"
