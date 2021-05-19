#!/bin/bash

DIR="$( cd "$( dirname "$0" )" && pwd )"
IMGDIR="$DIR"/../../advene/share/pixmaps

python3 svg2icns.py "$IMGDIR"/icon_advene.svg "$DIR"/bundle/advene.icns
