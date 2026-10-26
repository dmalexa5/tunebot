#!/bin/zsh
# run-chirp.sh [-i IP] [-r] [--delay SEC] [--rest-threshold RAD_S] [--taper FRACTION]
#   amplitude_A f0_hz f1_hz duration_ms repeats stride session_dir
set -e

SCRIPT_DIR=${0:A:h}
RTTTEST=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttest
RTTTASK=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttask
TABLES=$SCRIPT_DIR/../../module-fwpp/output/drive/none/drive-none.tables.json
PYTHON=$SCRIPT_DIR/../.venv/bin/python
IP=127.0.0.1
RFLAG=()
DELAY=1
REST_THRESHOLD=0.05
TAPER=()
while [[ "$1" == -* ]]; do
	case "$1" in
		-i) IP=$2; shift 2 ;;
		-r) RFLAG=(-r); shift ;;
		--delay) DELAY=$2; shift 2 ;;
		--rest-threshold) REST_THRESHOLD=$2; shift 2 ;;
		--taper) TAPER=(--taper "$2"); shift 2 ;;
		*) echo "unknown flag: $1" >&2; exit 1 ;;
	esac
done
if (( $# != 7 )); then
	echo "usage: run-chirp.sh [-i IP] [-r] [--delay SEC] [--rest-threshold RAD_S] [--taper FRACTION] amplitude_A f0_hz f1_hz duration_ms repeats stride session_dir" >&2
	exit 1
fi
AMP=$1
F0=$2
F1=$3
DURATION_MS=$4
REPEATS=$5
STRIDE=$6
SESSION=${7:A}
SETTINGS=(--amplitude "$AMP" --f0 "$F0" --f1 "$F1" --duration-ms "$DURATION_MS"
	--repeats "$REPEATS" --stride "$STRIDE" --delay "$DELAY" --rest-threshold "$REST_THRESHOLD")
SIGNAL_JSON=$("$PYTHON" "$SCRIPT_DIR/txf-chirp.py" $SETTINGS --signal-json)
"$PYTHON" -c 'import matplotlib'
if [[ -e "$SESSION" ]]; then
	echo "run-chirp.sh: use a new session directory: $SESSION" >&2
	exit 1
fi
mkdir -p "$SESSION"
cd "$SESSION"

IN_FLIGHT=0
zero_current(){
	local failed=0
	"$RTTTASK" -i "$IP" '{"command":"Jx_STATUS","action":"WRITE","mode":"FOC"}' >/dev/null || failed=1
	"$RTTTASK" -i "$IP" '{"command":"Jx_IDQ","action":"WRITE","id":0,"iq":0,"mvel":0,"mpos":0}' >/dev/null || failed=1
	return $failed
}
stop_motion(){
	zero_current || echo "run-chirp.sh: zero-current cleanup failed" >&2
	# Killing the host does not abort the board's waveform. Let its bounded
	# timeline expire, then zero again so no later waveform delta remains.
	if (( IN_FLIGHT )); then
		sleep 4
		zero_current || echo "run-chirp.sh: final zero-current cleanup failed" >&2
	fi
}
trap 'exit 130' INT TERM
trap stop_motion EXIT

"$RTTTASK" -i "$IP" $RFLAG '{"command":"Jx_STATUS","action":"WRITE","mode":"FOC"}' >/dev/null
CAPTURES=()
for (( trial=1; trial<=REPEATS; trial++ )); do
	zero_current
	# The iq signal rides the vel stage feedforward, which needs ENABLE.
	"$RTTTASK" -i "$IP" '{"command":"Jx_STATUS","action":"WRITE","ctrl":["ENABLE"],"mode":"FOC"}' >/dev/null
	sleep "$DELAY"
	PREFIX=$(printf 'chirp-%03d' "$trial")
	IN_FLIGHT=1
	"$RTTTEST" -n -s "$TABLES" -i "$IP" -o "$PREFIX" \
		"$SIGNAL_JSON"
	zero_current
	FOUND=("$PREFIX".*.txf(N/))
	if (( ${#FOUND} != 1 )); then
		echo "run-chirp.sh: expected one capture for $PREFIX, found ${#FOUND}" >&2
		exit 1
	fi
	"$PYTHON" "$SCRIPT_DIR/txf-chirp.py" $SETTINGS --check "$FOUND[1]"
	IN_FLIGHT=0
	CAPTURES+=("$FOUND[1]")
done
"$PYTHON" "$SCRIPT_DIR/txf-chirp.py" $SETTINGS $TAPER $CAPTURES --output-dir "$SESSION"
