#!/bin/zsh
# setgains.sh [-i IP] vkp vki pkp pki [tqclim] [vellim] -- write the whole cascade.
set -e
source /Users/dmalexa/tmp/j0-fullarm-retune/_tools/env.sh

IP=127.0.0.1
if [[ "$1" == "-i" ]]; then
	IP=$2
	shift 2
fi

cd $RT
./rtttask -i $IP -- >/dev/null <<EOJ
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KP","val":$1}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KI","val":$2}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_KD","val":0.0}
{"command":"Jx_CFG","action":"WRITE","addr":"VEL_TQC_LIM","val":${5:-5.0}}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KP","val":$3}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KI","val":$4}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_KD","val":0.0}
{"command":"Jx_CFG","action":"WRITE","addr":"POS_VEL_LIM","val":${6:-3.1415927}}
EOJ
