#!/bin/bash

set -e

# shellcheck source-path=SCRIPTDIR
source env.sh

# to allow bootstrapping again, try to delete everything first
# shellcheck source-path=SCRIPTDIR
source clean.sh

# Cargo and Rust must be installed in the user's home directory.
# They cannot be run successfully from JHBuild's prefix or home
# directory.
rustup install 1.69.0

JHBUILD_REVISION="3.38.0"

# brew install needed packages
brew install autoconf automake gettext pkgconfig yelp-tools python-setuptools
# Dependencies for pulseaudio:
brew install libsndfile dbus-glib

mkdir -p "$HOME"
git clone https://gitlab.gnome.org/GNOME/jhbuild.git "$QL_OSXBUNDLE_JHBUILD_DEST"
(cd "$QL_OSXBUNDLE_JHBUILD_DEST" && git checkout "$JHBUILD_REVISION" && ./autogen.sh && DISABLE_GETTEXT=1 make install)
cp misc/gtk-osx-jhbuildrc "$HOME/.jhbuildrc"
cp misc/advene-jhbuildrc-custom "$HOME/.jhbuildrc-custom"
git clone https://gitlab.gnome.org/GNOME/gtk-mac-bundler.git "$QL_OSXBUNDLE_BUNDLER_DEST"
(cd "$QL_OSXBUNDLE_BUNDLER_DEST" && make install)
