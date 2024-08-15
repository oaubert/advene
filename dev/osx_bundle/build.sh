#!/bin/bash

set -e

# shellcheck source-path=SCRIPTDIR
source env.sh

cargo -V || (echo "Requires rust"; exit 1)

jhbuild build meta-bootstrap
jhbuild build advene
# Add python package through pip, since it handles dependencies automatically
echo python3 -m pip install cherrypy | jhbuild shell
echo python3 -m pip install Pillow | jhbuild shell
echo python3 -m pip install rdflib | jhbuild shell
