#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2016 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import advene.core.config as config

if __name__ == "__main__":

    exts = list(config.data.video_extensions)
    exts.extend([ '.azp', '.xml', '.apl' ])
    # these are for showing up in the openwith dialog
    for ext in sorted(exts):
        print('WriteRegStr HKLM "${ADVENE_ASSOC_KEY}" '
              '"%s" "${ADVENE_ID}.assoc.ANY"' % ext)
