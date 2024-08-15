#!/bin/bash
# Copyright 2016,2017 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# Pass the tag/revision to install, or install the current revision
# if nothing is passed

set -e

# shellcheck source-path=SCRIPTDIR
source env.sh

function main {
    local GIT_TAG=${1:-"main"}

    rm -rf "$QL_OSXBUNDLE_BUNDLE_DEST"

    PYTHON="python3"
    PYTHONID="python"$(jhbuild run "${PYTHON}" -c \
        "import sys;sys.stdout.write('.'.join(map(str, sys.version_info[:2])))")

    export QL_PYTHON="$PYTHON"
    export QL_PYTHONID="$PYTHONID"
    jhbuild run gtk-mac-bundler misc/bundle/app.bundle

    APP="$QL_OSXBUNDLE_BUNDLE_DEST/Application.app"
    APP_PREFIX="$APP"/Contents/Resources

    # kill some useless files
    rm -f "$APP"/Contents/MacOS/_launcher-bin
    rm -Rf "$APP_PREFIX"/include/

    # Python stdlib bytecode and test files
    find "$APP_PREFIX"/lib/"$PYTHONID" -name '*.pyo' -delete
    find "$APP_PREFIX"/lib/"$PYTHONID" -name '*.pyc' -delete
    find "$APP_PREFIX"/lib/"$PYTHONID" -name '*.a' -delete
    find "$APP_PREFIX"/lib/"$PYTHONID" -name '*.whl' -delete
    rm -Rf "$APP_PREFIX"/lib/"$PYTHONID"/*/test
    rm -Rf "${APP_PREFIX}"/lib/"${PYTHONID}"/test
    find "${APP_PREFIX}"/lib/"${PYTHONID}" -type d -name "test*" \
        -prune -exec rm -rf {} \;
    find "${APP_PREFIX}"/lib/"${PYTHONID}" -type d -name "*_test*" \
        -prune -exec rm -rf {} \;
    # strip debug symbols
    find "${APP_PREFIX}"/lib -type f -name "*.dylib" -exec strip -S {} \;

    # remove some larger icon theme files
    rm -Rf "${APP_PREFIX}/share/icons/Adwaita/cursors"
    rm -Rf "${APP_PREFIX}/share/icons/Adwaita/512x512"
    rm -Rf "${APP_PREFIX}/share/icons/Adwaita/256x256"
    rm -Rf "${APP_PREFIX}/share/icons/Adwaita/96x96"
    rm -Rf "${APP_PREFIX}/share/icons/Adwaita/48x48"
    jhbuild run gtk-update-icon-cache "${APP_PREFIX}/share/icons/Adwaita"

    # compile the stdlib
    jhbuild run "$PYTHON" -m compileall -b -d "" -f "$APP_PREFIX"/lib/"$PYTHONID"
    # delete stdlib source
    find "$APP_PREFIX"/lib/"$PYTHONID" -name '*.py' -delete

    # clone this repo and install into the bundle
    CLONE="$QL_OSXBUNDLE_BUNDLE_DEST"/_temp_clone
    git clone ../.. "$CLONE"
    (cd "$CLONE"; git checkout "$GIT_TAG")
    (
     ## FIXME check quodlibet backport
     ## # This is is a bit hackish. More proper investigation would be needed to determine why setup.py install does not find its own install dir
     ## export PYTHONPATH="$APP_PREFIX/lib/$PYTHONID/site-packages:$PYTHONPATH"
     ## cd "$CLONE"
     jhbuild run "$PYTHON" "$CLONE"/setup.py install \
        --prefix="$APP_PREFIX" --root="/" \
        --record="$QL_OSXBUNDLE_BUNDLE_DEST"/_install_log.txt
    )
    rm -Rf "$CLONE"

    jhbuild run "$PYTHON" ./misc/prune_translations.py \
        "$APP_PREFIX"/share/locale

    # create launchers
    (cd "$APP"/Contents/MacOS/ && ln -s _launcher advene)
    (cd "$APP"/Contents/MacOS/ && ln -s _launcher run)
    (cd "$APP"/Contents/MacOS/ && ln -s _launcher gst-plugin-scanner)

    # remove empty directories
    find "$APP_PREFIX" -type d -empty -delete

    ADVENE="$QL_OSXBUNDLE_BUNDLE_DEST/Advene.app"
    ADVENE_PREFIX="$ADVENE"/Contents/Resources

    mv "$APP" "$ADVENE"

    ## FIXME: check quodlibet backport
    #echo 'BUILD_TYPE = u"osx-advene"' >> \
    #    "$ADVENE_PREFIX"/lib/"$PYTHONID"/site-packages/advene/build.py

    # force compile again to get relative paths in pyc files and for the
    # modified files
    jhbuild run "$PYTHON" -m compileall -b -d "" -f "$ADVENE_PREFIX"/lib/"$PYTHONID"

    VERSION=$("$ADVENE"/Contents/MacOS/run -c \
        "import sys, advene.core.version;sys.stdout.write(advene.core.version.version)")
    jhbuild run "$PYTHON" ./misc/create_info.py "Advene" "$VERSION" > \
        "$ADVENE"/Contents/Info.plist

    jhbuild run "$PYTHON" ./misc/list_content.py "$HOME/jhbuild_prefix" \
        "$ADVENE" > "$ADVENE/Contents/Resources/content.txt"

    DMG_SETTINGS="misc/dmg_settings.py"
    jhbuild run dmgbuild -s "$DMG_SETTINGS" -D app="$ADVENE" \
        "Advene $VERSION" "$QL_OSXBUNDLE_BUNDLE_DEST/ADVENE-$VERSION.dmg"

    (cd "$QL_OSXBUNDLE_BUNDLE_DEST" && \
        shasum -a256 "Advene-$VERSION.dmg" > "Advene-$VERSION.dmg.sha256")
}

main "$@";
