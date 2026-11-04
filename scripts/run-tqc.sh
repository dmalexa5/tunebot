#!/bin/zsh
# run-tqc.sh [-i IP] [-r] [-c FLAG]... freq_hz amp [cycles] [stride] [prefix]
#   amp units: rad. The position wave is amp*(1 - cos), i.e. it swings
#   0 -> 2*amp -> 0 about the pos_des held at start, with vel = its analytic
#   derivative -- both start and end at zero.
#   -c FLAG: extra Jx_STATUS ctrl bit to set with POS mode (repeatable),
#            e.g. VEL_USE_MENC
# Puts the joint in POS mode and runs signal_tqc (rtttest): the firmware
# feeds pos_cmd_set() (pos, vel) every 40 servo ticks (500 Hz), exactly as a
# host Jx_TQC stream would, so the 1 kHz interpolator + vel feedforward are
# exercised. Returns the joint to FOC (cascade disabled) on exit. Writes
# <prefix>.NNNN.txf in the current directory. Analyze with
# `txf-sine.py capture.txf <printed Hz> pos` (it removes the DC offset).
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
RTTTASK=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttask
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json

RAD_TO_CNT=$(( 4294967296.0 / (2 * 3.14159265358979324) ))

# Same uint16 servo-tick timeline and 20-sample edges as run-sine.sh.
SERVO_HZ=20000
EDGE_SAMPLES=20
TICKS_MAX=65534
CMD_TICKS=40   # firmware tqc command period; end_pad must cover one

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
if (( $# < 2 )); then
	echo "usage: run-tqc.sh [-i IP] [-r] [-c FLAG]... freq_hz amp [cycles] [stride] [prefix]" >&2
	exit 1
fi

FREQ_HZ=$1
AMP=$(printf %.0f $(( $2 * RAD_TO_CNT )))
CYCLES=${3:-2}
STRIDE=${4:-20}
PREFIX=${5:-qsine}

PERIOD=$(printf %.0f $(( 1.0 * SERVO_HZ / FREQ_HZ )))
PAD=$(( EDGE_SAMPLES * STRIDE ))
DURATION=$(( PERIOD * CYCLES ))
if (( PERIOD < 2 * CMD_TICKS )); then
	echo "run-tqc.sh: ${FREQ_HZ} Hz is under 2 commands/cycle at the 500 Hz tqc rate" >&2
	exit 1
fi
if (( PAD < CMD_TICKS )); then
	echo "run-tqc.sh: stride ${STRIDE} gives a ${PAD}-tick end pad; need >= ${CMD_TICKS} so the final (base, 0) command lands" >&2
	exit 1
fi
if (( PERIOD > TICKS_MAX || 2 * PAD + DURATION > TICKS_MAX )); then
	echo "run-tqc.sh: ${CYCLES} cycles at ${FREQ_HZ} Hz, stride ${STRIDE} needs $(( 2 * PAD + DURATION )) servo ticks; cap is ${TICKS_MAX}" >&2
	exit 1
fi
print -u2 -- "run-tqc.sh: period ${PERIOD} ticks -> $(printf %.6g $(( 1.0 * SERVO_HZ / PERIOD ))) Hz (pass this to txf-sine.py)"

STOPPED=0
stop_motion(){
	if (( STOPPED )); then return 0; fi
	STOPPED=1
	"$RTTTASK" -i "$IP" "{\"command\":\"Jx_STATUS\",\"action\":\"WRITE\",\"ctrl\":[$FEAT_JSON],\"mode\":\"FOC\"}" >/dev/null 2>&1 || true
	"$RTTTASK" -i "$IP" '{"command":"Jx_IDQ","action":"WRITE","id":0,"iq":0,"mvel":0,"mpos":0}' >/dev/null 2>&1 || true
}
trap 'stop_motion; exit 130' INT TERM
trap stop_motion EXIT

for flag in $CTRL; do FEAT_JSON+="${FEAT_JSON:+,}\"$flag\""; done
CTRL_JSON="\"ENABLE\"${FEAT_JSON:+,}$FEAT_JSON"
"$RTTTASK" -i "$IP" $RFLAG \
	"{\"command\":\"Jx_STATUS\",\"action\":\"WRITE\",\"ctrl\":[$CTRL_JSON],\"mode\":\"POS\"}" >/dev/null

# "signal" is ignored by the firmware but required by the JSON parser.
"$RTTTEST" -n -s "$TABLES" -i "$IP" -o "$PREFIX" \
	"{\"test\":\"signal_tqc\",\"signal\":\"pos\",\"amplitude\":$AMP,\"period\":$PERIOD,\"ncycles\":$CYCLES,\"start_pad\":$PAD,\"end_pad\":$PAD,\"decimation\":$STRIDE}"
