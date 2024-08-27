#! /bin/sh

DIRNAME=$(dirname "$0")
cd "$DIRNAME" || { echo "Cannot cd to $DIRNAME"; exit 1 ; }
./bootstrap.sh && ./build.sh && ./bundle.sh
