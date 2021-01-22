#!/usr/bin/env bash
# Copyright 2016 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

set -e

function main {

    local MSYS2_ARCH="x86_64"

    pacman --noconfirm -Suy

    pacman --noconfirm -S --needed \
        git \
        base-devel \
        mingw-w64-$MSYS2_ARCH-gettext \
        mingw-w64-$MSYS2_ARCH-gdk-pixbuf2 \
        mingw-w64-$MSYS2_ARCH-librsvg \
        mingw-w64-$MSYS2_ARCH-gtk3 \
        mingw-w64-$MSYS2_ARCH-libsoup \
        mingw-w64-$MSYS2_ARCH-gstreamer \
        mingw-w64-$MSYS2_ARCH-gst-plugins-base \
        mingw-w64-$MSYS2_ARCH-gst-plugins-good \
        mingw-w64-$MSYS2_ARCH-libsrtp \
        mingw-w64-$MSYS2_ARCH-gst-plugins-bad \
        mingw-w64-$MSYS2_ARCH-gst-libav \
        mingw-w64-$MSYS2_ARCH-gst-plugins-ugly \
        mingw-w64-$MSYS2_ARCH-toolchain

    pacman --noconfirm -S --needed \
        mingw-w64-$MSYS2_ARCH-python3 \
        mingw-w64-$MSYS2_ARCH-python3-gobject \
        mingw-w64-$MSYS2_ARCH-python3-cairo \
        mingw-w64-$MSYS2_ARCH-python3-pip \
        mingw-w64-$MSYS2_ARCH-gtksourceview3  \
        mingw-w64-$MSYS2_ARCH-goocanvas \
        mingw-w64-$MSYS2_ARCH-libsrtp \
        mingw-w64-$MSYS2_ARCH-python3-pillow

    #pip3 install --user -U feedparser musicbrainzngs mutagen
}

main;
