#!/bin/bash
# Start ArduCopter SITL with copter.parm + <parm file> (+ extra "NAME VALUE" pairs), run one lab script
# against it, stop SITL. The run folder (sitl.log, feed.log, logs/*.BIN) is kept.
# usage: ARDUPILOT=~/ardupilot ./run_lab.sh <tag> <parm file|-> "<extra params>" <lab.py> [lab args...]
#   e.g. ./run_lab.sh oa oa.parm "" oa_dijkstra_lab.py
#        ./run_lab.sh freeze extnav.parm "" vio_fault_feed.py --fault freeze --fault-at 10 --fault-len 20
#        ./run_lab.sh g_sats - "SIM_GPS1_NUMSATS 5" gnss_prearm.py
# <parm file>: a name in this folder or an absolute path (e.g. "$ARDUPILOT/Tools/autotest/default_params/copter-gps-for-yaw.parm")
# env: INSTANCE (default 3; TCP port 5760 + 10*INSTANCE), RUN_ROOT (default ./sitl-run),
#      HOME_LOC (default -35.363261,149.165230,584,0; nav-indoor used heading 353), LAB_TIMEOUT (default 300 s)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
AP="${ARDUPILOT:?set ARDUPILOT to your ardupilot checkout (with build/sitl/bin/arducopter)}"
TAG=$1; PARM=$2; EXTRA=$3; LAB=$4; shift 4
I=${INSTANCE:-3}; PORT=$((5760 + 10 * I))
RUN="${RUN_ROOT:-$HERE/sitl-run}/$TAG"; rm -rf "$RUN"; mkdir -p "$RUN"; cd "$RUN"
cp "$AP/Tools/autotest/default_params/copter.parm" defaults.parm
case "$PARM" in -) ;; /*) cat "$PARM" >> defaults.parm ;; *) cat "$HERE/$PARM" >> defaults.parm ;; esac
[ -n "$EXTRA" ] && echo "$EXTRA" | tr ',' '\n' >> defaults.parm
"$AP/build/sitl/bin/arducopter" -w -S -I "$I" --model + --speedup 1 --home "${HOME_LOC:--35.363261,149.165230,584,0}" \
  --defaults defaults.parm > sitl.log 2>&1 &
SITL=$!
trap 'kill $SITL 2>/dev/null; wait $SITL 2>/dev/null' EXIT
sleep 4
timeout "${LAB_TIMEOUT:-300}" python3 "$HERE/$LAB" --port "$PORT" "$@" | tee feed.log
