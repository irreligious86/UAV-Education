#!/bin/bash
# Start ArduCopter SITL (instance 3, TCP 5790) and run the vision node against it.
# usage: ARDUPILOT=~/ardupilot ./run_sitl.sh <output.txt> [extra sitl_vtrn.py args]
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
AP="${ARDUPILOT:?set ARDUPILOT to your ardupilot checkout (with build/sitl/bin/arducopter)}"
RUN="$HERE/sitl-run"; mkdir -p "$RUN"; cd "$RUN"
"$AP/build/sitl/bin/arducopter" -S --model + --speedup 1 -I 3 -w \
  --defaults "$AP/Tools/autotest/default_params/copter.parm" --home 55.693712,37.504782,150,0 > sim.log 2>&1 &
SITL=$!
trap 'kill $SITL 2>/dev/null' EXIT
sleep 2
cd "$HERE" && VTRN_JSON="$RUN/sitl_series.json" python3 -u sitl_vtrn.py tcp:127.0.0.1:5790 "${@:2}" > "$1" 2>&1
