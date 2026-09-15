#!/bin/zsh
# clear-faults.sh [-i IP] [-r]
# Clears latched FOC faults (overvoltage, undervoltage, overtemp, etc.) via
# Jx_STATUS ctrl=CLR_FAULT (rtttask) and prints the resulting status word.
# See module-fwpp/cheatsheet.md "FOC current-loop PID" section for the
# Jx_STATUS/Jx_CFG command shapes.
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

"$RTTTASK" -i "$IP" $RFLAG '{"command":"Jx_STATUS","ctrl":"CLR_FAULT"}'
