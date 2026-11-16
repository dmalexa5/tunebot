#!/bin/zsh
# setup-menc-calibration.sh -- bench prep for menc-calibration (local probe):
#   1) build drive DEBUG=1 TRACE=MECH in ../module-fwpp (build check, no flash)
#      and rebuild the rttcmd host tools against the same protocol sources
#   2) kill any openocd, start a fresh one on scripts/g4.cfg in the background
#      (log: module-fwpp/.openocd.log), and resume the target g4.cfg halts
#   3) stream the RTT log in the foreground with rttlog -r
# Ctrl-C stops rttlog only; openocd keeps running for menc-calibration.
set -e
FW=${0:A:h:h:h}/module-fwpp
OCDLOG=$FW/.openocd.log
BUILDLOG=${TMPDIR:-/tmp}/setup-menc-calibration.build.log

echo "== build drive DEBUG=1 TRACE=MECH"
make -C "$FW" build BOARD=drive BANK=none DEBUG=1 TRACE=MECH -j16 >"$BUILDLOG" 2>&1 \
	|| { tail -30 "$BUILDLOG"; echo "build failed; full log $BUILDLOG" >&2; exit 1; }
[[ $(jq -r .rtttrace.name "$FW/output/drive/none/drive-none.tables.json") == mech_trace ]] \
	|| { echo "tables.json is not mech_trace" >&2; exit 1; }
# rttcmd compiles the protocol tables in; a stale binary can't decode
# Jx_STATUS or resolve Jx_CFG names like MA600A_REG_BCT.
make -C "$FW/tools/rttcmd" >>"$BUILDLOG" 2>&1 \
	|| { tail -30 "$BUILDLOG"; echo "rttcmd build failed; full log $BUILDLOG" >&2; exit 1; }
echo "ok"

echo "== restart openocd"
if pkill -x openocd; then
	while pgrep -x openocd >/dev/null; do sleep 0.2; done
fi
(cd "$FW" && nohup openocd -f scripts/g4.cfg >"$OCDLOG" 2>&1 &)
for i in {1..50}; do
	nc -z 127.0.0.1 4444 2>/dev/null && break
	sleep 0.2
done
nc -z 127.0.0.1 4444 2>/dev/null || { tail -20 "$OCDLOG"; echo "openocd did not start" >&2; exit 1; }
printf "reset run\nexit\n" | nc -w 3 127.0.0.1 4444 >/dev/null
sleep 1.5   # let the firmware initialize its RTT control block
echo "ok (log $OCDLOG)"

echo "== rttlog -r (Ctrl-C to stop; openocd keeps running)"
exec "$FW/tools/rttcmd/rttlog" -r
