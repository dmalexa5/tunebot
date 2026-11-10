#!/bin/zsh
# menc-holds.sh [-i IP] PREFIX DIR "I1 I2 ..." [SETTLE_S]
#   Constant-torque holds for encoder calibration, one direction. DIR is f or r
#   (r negates the currents). From zero torque, ramp to each |I| in order, settle,
#   capture 3 s of mech_trace at stride 4 as PREFIX_<DIR><I>.NNNN.txf in the
#   current directory, then zero the torque (absolute Jx_TQC write) on any exit.
set -e
IP=127.0.0.1
[[ "$1" == "-i" ]] && { IP=$2; shift 2; }
PREFIX=$1; DIR=$2; LEVELS=(${=3}); SETTLE=${4:-7}
[[ "$DIR" == f || "$DIR" == r ]] || { echo "DIR must be f or r" >&2; exit 1; }
SIGN=1; [[ "$DIR" == r ]] && SIGN=-1
SD=${0:A:h}
RTT=$SD/../../module-fwpp/tools/rttcmd
TBL=$SD/../../module-fwpp/output/drive/none/drive-none.tables.json

zero(){ "$RTT/rtttask" -i "$IP" '{"command":"Jx_TQC","action":"WRITE","pos":0,"vel":0,"trq":0,"ctrl":["ENABLE"]}' >/dev/null 2>&1 || true; }
trap 'zero; exit 130' INT TERM
trap zero EXIT

"$RTT/rtttask" -i "$IP" '{"command":"Jx_STATUS","action":"WRITE","ctrl":["ENABLE"],"mode":"FOC"}' >/dev/null
zero
sleep 4   # let a previous spin run down
prev=0
for I in $LEVELS; do
	d=$(( SIGN * I - prev ))
	"$RTT/rtttest" -i "$IP" -s "$TBL" "{\"test\":\"signal_ramp\",\"signal\":\"iq\",\"step\":$d,\"slope_samples\":10000,\"duration\":10000,\"flags\":0}" >/dev/null
	prev=$(( SIGN * I ))
	sleep $SETTLE
	out=$("$SD/run-trace.sh" -i "$IP" torque 4 "${PREFIX}_${DIR}${I}" 2>&1 | tail -1)
	echo "$out"
	[[ "$out" == *"(15000 records)"* || "$out" == *"(15001 records)"* ]] || { echo "short capture" >&2; exit 1; }
done
