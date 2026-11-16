#!/bin/zsh
# menc_read_cfg.sh [-i IP] [-r]
# Reads the MA600A trim (BCT, CORR0..31) via Jx_CFG and prints each byte.
# Values come from the firmware's boot-time mirror, not the chip: to verify
# what's in NVM, power-cycle the board (not just reset the MCU) first.
# -r restarts RTT before the first read only.
set -e

SCRIPT_DIR=${0:A:h}
RTTTASK=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttask

IP=127.0.0.1
RFLAG=()
while [[ "$1" == -* ]]; do
	case "$1" in
		-i) IP=$2; shift 2 ;;
		-r) RFLAG=(-r); shift ;;
		*) echo "unknown flag: $1" >&2; exit 1 ;;
	esac
done

out=$("$RTTTASK" -i "$IP" $RFLAG '{"command":"Jx_CFG","addr":"MA600A_REG_BCT"}')
bct=$(print -r -- "$out" | jq -r .data.val)
printf "BCT     = %3d (0x%02x)\n" "$bct" "$bct"

# CORR: val = idx<<8 on the way in, idx<<8 | byte on the way back.
for i in {0..31}; do
	out=$("$RTTTASK" -i "$IP" "{\"command\":\"Jx_CFG\",\"addr\":\"MA600A_REG_CORR\",\"val\":$((i << 8))}")
	corr=$(( $(print -r -- "$out" | jq -r .data.val) & 0xFF ))
	printf "CORR%-2d  = %3d (0x%02x)\n" "$i" "$corr" "$corr"
done
