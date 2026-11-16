#!/bin/zsh
# [TRACE=ILOOP] [BOARD_ID=N] menc-flash.sh [-i IP] -- build drive DEBUG TRACE=${TRACE:-MECH}
# BOARD_ID=${BOARD_ID:-0} from ../module-fwpp,
# gdb-load it on the remote openocd, reset, re-attach RTT at the new control
# block, bring the power stage up, and check the boot log for menc errors.
set -e
IP=127.0.0.1
[[ "$1" == "-i" ]] && { IP=$2; shift 2; }
FW=${0:A:h}/../../module-fwpp
RTT=$FW/tools/rttcmd
ELF=$FW/output/drive/none/drive-none.elf

make -C "$FW" build BOARD=drive BANK=none DEBUG=1 TRACE=${TRACE:-MECH} BOARD_ID=${BOARD_ID:-0} -j16 >/tmp/menc-build.$$ 2>&1 \
	|| { tail -30 /tmp/menc-build.$$; exit 1; }
[[ $(jq -r .rtttrace.name "$FW/output/drive/none/drive-none.tables.json") == ${${TRACE:-MECH}:l}_trace || ${TRACE:-MECH} == ILOOP ]] \
	|| { echo "tables.json does not match TRACE" >&2; exit 1; }

# Capture the boot log: listen on the log channel across the reset.
arm-none-eabi-gdb "$ELF" -batch \
	-ex "target extended-remote $IP:3333" \
	-ex "monitor reset halt" -ex load -ex "monitor reset run" >/dev/null 2>&1
ADDR=$(arm-none-eabi-nm "$ELF" | awk '/ _SEGGER_RTT$/{print $1}')
sleep 1.5
printf "rtt stop\nrtt setup 0x$ADDR 0x30 \"SEGGER RTT\"\nrtt start\nexit\n" | nc -w 3 "$IP" 4444 >/dev/null
sleep 1
LOG=$(timeout 2 "$RTT/rttlog" -i "$IP" 2>/dev/null || true)
if print -r -- "$LOG" | grep -qi "menc"; then
	echo "boot log menc lines:"; print -r -- "$LOG" | grep -i menc
fi
print -r -- "$LOG" | grep -qi "menc reg cfg failed" && { echo "MENC CONFIG FAILED" >&2; exit 1; }

"$RTT/rtttask" -i "$IP" '{"command":"GHASH","hash":0}'
ST=$("$RTT/rtttask" -i "$IP" '{"command":"Jx_STATUS","action":"READ"}')
if ! print -r -- "$ST" | grep -q '"outp":"ON"'; then
	"$RTT/rtttask" -i "$IP" '{"command":"Jx_STATUS","action":"WRITE","ctrl":["CLR_FAULT"],"mode":"FOC"}' >/dev/null
	sleep 1
	ST=$("$RTT/rtttask" -i "$IP" '{"command":"Jx_STATUS","action":"READ"}')
fi
echo "$ST"
print -r -- "$ST" | grep -q '"outp":"ON"' || { echo "power stage not ON" >&2; exit 1; }
