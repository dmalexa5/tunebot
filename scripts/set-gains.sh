#!/bin/zsh
# setgains.sh [-i IP] vkp vki pkp pki [tqclim] [vellim] -- write the whole cascade.
#   vkp/vki   A per rad/s  (and per rad/s^2)
#   pkp/pki   rad/s per rad (dimensionless 1/s)
#   tqclim    A
#   vellim    rad/s
set -e
source /Users/dmalexa/tmp/j0-fullarm-retune/_tools/env.sh

IP=127.0.0.1
if [[ "$1" == "-i" ]]; then
	IP=$2
	shift 2
fi

# Jx_CFG writes land in servo_cfg_t unconverted, and that struct is in
# output-shaft counts (2^32/rev) -- "radians appear nowhere" in the loop
# (module-fwpp src/servo.h). The three macros there name the conversions the
# host is expected to apply; this mirrors them, so the arguments above stay
# in the rad domain the tunables and reports are written in:
#   SERVO_RAD_TO_CNT        rad-valued limits     -> counts   (multiply)
#   SERVO_VEL_GAIN_FROM_RAD A/(rad/s) -> A/(cnt/s)            (divide)
#   SERVO_POS_GAIN_FROM_RAD pos PID is 1/s either way         (unchanged)
CNT_PER_RAD=$(( 4294967296.0 / (2 * 3.14159265358979324) ))
vel_gain(){ printf %.9e $(( $1 / CNT_PER_RAD )); }
rad_to_cnt(){ printf %.9e $(( $1 * CNT_PER_RAD )); }

cd $RT
./rtttask -i $IP -- >/dev/null <<EOJ
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KP","val":$(vel_gain $1)}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KI","val":$(vel_gain $2)}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KD","val":0.0}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_TQC_LIM","val":${5:-5.0}}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KP","val":$3}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KI","val":$4}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KD","val":0.0}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_VEL_LIM","val":$(rad_to_cnt ${6:-3.1415927})}
EOJ
