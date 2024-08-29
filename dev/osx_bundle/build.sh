#!/bin/bash

set -e

# shellcheck source-path=SCRIPTDIR
source env.sh

cargo -V || (echo "Requires rust"; exit 1)

jhbuild build meta-bootstrap
#jhbuild build advene
jhbuild build pulseaudio

# Ref dir:
#  /Users/runner/work/advene/advene/dev/osx_bundle/_home/jhbuild_checkoutroot/pulseaudio-v17.0/
LOGDIR=/Users/runner/work/advene/advene/dev/osx_bundle/_home/.cache/jhbuild/build/pulseaudio-v17.0/meson-logs/
ls -l $LOGDIR
echo "################################################################################# meson-log.txt"
[ -f $LOGDIR/meson-log.txt ] && cat $LOGDIR/meson-log.txt
echo "################################################################################# install-log.txt"
[ -f $LOGDIR/install-log.txt ] && cat $LOGDIR/install-log.txt
echo "#################################################################################"
