#!/bin/bash

set -e

# shellcheck source-path=SCRIPTDIR
source env.sh

rm -Rf "$HOME"
rm -Rf "$QL_OSXBUNDLE_JHBUILD_DEST"
rm -Rf "$QL_OSXBUNDLE_BUNDLER_DEST"
rm -Rf "$QL_OSXBUNDLE_BUNDLE_DEST"
