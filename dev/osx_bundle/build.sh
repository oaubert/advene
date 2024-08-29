#!/bin/bash

set -e

# shellcheck source-path=SCRIPTDIR
source env.sh

cargo -V || (echo "Requires rust"; exit 1)

jhbuild --no-interact build meta-bootstrap
jhbuild --no-interact build advene
