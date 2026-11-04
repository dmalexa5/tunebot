#!/bin/zsh
# setgains.sh [-i IP] vkp vki pkp pki [tqclim] [vellim] -- write the whole cascade.
# Units match ../cn-seamless/configs/tunables/drive-*.json:
#   vkp/vki   A per deg/s  (and per deg/s^2)
#   pkp/pki   deg/s per deg (dimensionless 1/s)
#   tqclim    A
#   vellim    deg/s
set -e

SCRIPT_DIR=${0:A:h}
RTTTASK=$SCRIPT_DIR/../../module-fwpp/tools/rttcmd/rtttask

IP=127.0.0.1
if [[ "$1" == "-i" ]]; then
	IP=$2
	shift 2
fi

# Jx_CFG writes land in drive_cfg_t unconverted, and the cascade runs in
# output-shaft counts (2^32/rev) and counts/s (module-fwpp src/drive-control.h).
# Convert here so the arguments above stay in the deg domain the tunables
# are written in:
#   deg-valued limits          -> counts    (multiply)
#   vel gains A/(deg/s)        -> A/(cnt/s) (divide)
#   pos PID is 1/s either way               (unchanged)
# The vel loop outputs torque and FOC divides it by FOC_KT; the board ships
# FOC_KT = 1, so vel gains and VEL_TQC_LIM stay in amps. Only the *_BASE gains
# are written; *_SCHED gains apply only with VEL/POS_GAIN_SCHED set in ctrl.
CNT_PER_DEG=$(( 4294967296.0 / 360.0 ))
vel_gain(){ printf %.9e $(( $1 / CNT_PER_DEG )); }
deg_to_cnt(){ printf %.9e $(( $1 * CNT_PER_DEG )); }

"$RTTTASK" -i "$IP" -- >/dev/null <<EOJ
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KP_BASE","val":$(vel_gain $1)}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KI_BASE","val":$(vel_gain $2)}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KD_BASE","val":0.0}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_TQC_LIM","val":${5:-5.0}}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KP_BASE","val":$3}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KI_BASE","val":$4}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KD_BASE","val":0.0}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_VEL_LIM","val":$(deg_to_cnt ${6:-180.0})}
EOJ
