#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2024 Olivier Aubert <contact@olivieraubert.net>
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""
Corpus handling tools
=====================
"""
import logging
logger = logging.getLogger(__name__)

import os
from pathlib import Path
import sys

from gi.repository import Gtk

import advene.core.config as config
from advene.core.imagecache import ImageCache
import advene.core.idgenerator

import advene.util.helper as helper
from advene.util.website_export import WebsiteExporter

class ProxyController:
    def __init__(self, controller):
        self.controller = controller
        self.package = None
        # Bad hack...
        self.server = self
        self.urlbase = 'http://localhost:1234/'
        self.gui = self

    def __getattr__(self, attr):
        """Proxying method
        It will be invoked for attributes that are not natively defined in ProxyController
        """
        return getattr(self.controller, attr)

    def get_urlbase(self):
        return self.urlbase

    def set_package(self, p):
        self.package = p
        self.package.imagecache = ImageCache()
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            self.package.imagecache.load(helper.mediafile2id (mediafile))
        self.package._idgenerator = advene.core.idgenerator.Generator(self.package)

    def overlay(self, png_data, svg_data, other_thread=False):
        return png_data

    def get_default_media(self):
        mediafile = self.package.getMetaData (config.data.namespace,
                                              "mediafile")
        if mediafile is None or mediafile == "":
            return ""
        return mediafile

    def build_context(self, here=None, alias=None, baseurl=None):
        """Build a context object with additional information.

        The information is cached if no additional parameter (alias,
        baseurl) is specified.
        """
        if here is None:
            here = self.package
        if alias is None and baseurl is None:
            try:
                c = here._cached_context
                c.restore()
                return c
            except AttributeError:
                pass
        if baseurl is None:
            baseurl=self.get_default_url(root=True, alias=alias)
        c = advene.model.tal.context.AdveneContext(here,
                                                   options={
                                                       'package_url': baseurl,
                                                       'snapshot': self.package.imagecache,
                                                       'namespace_prefix': config.data.namespace_prefix,
                                                       'config': config.data.web,
                                                       'aliases': self.aliases,
                                                       'controller': self,
                                                   })
        c.addGlobal('package', self.package)
        c.addGlobal('packages', self.packages)
        c.addGlobal('player', self.player)
        for name, method in config.data.global_methods.items():
            c.addMethod(name, method)
        # Preserve a copy of globals/locals for later restoring
        c.checkpoint()
        return c

def corpus_website_export(controller, destination):

    def log(*p):
        controller.log(*p)

    def progress(value, msg):
        log(msg)
        for i in range(8):
            if Gtk.events_pending():
                Gtk.main_iteration()
            else:
                break
        return True

    proxy = ProxyController(controller)

    destination = Path(destination)
    log(f"Exporting corpus as website into {destination}")

    created = []
    for alias, p in controller.packages.items():
        if alias == 'advene' or alias == 'new_pkg':
            continue
        proxy.set_package(p)
        media = p.getMetaData(config.data.namespace, "mediafile")
        if media is None or media == "":
            video_url = ""
        else:
            video_url = os.path.basename(media.replace('\\', '/'))
        exporter = WebsiteExporter(proxy)
        exporter.set_options({
            'video_url': video_url,
            'depth': 3
            })
        try:
            logger.debug(f"Exporting {alias} to { destination / alias }")
            output_dir = destination / alias
            exporter.export(output_dir)
            created.append((alias, p, Path(alias)))
        except Exception as e:
            log(f"Corpus - error when exporting {p.uri}")
            log(str(e))
            e, v, tb = sys.exc_info()
            import code
            log("".join( code.traceback.format_exception (e, v, tb) ))

    # Write TOC for generated exports
    links = "\n".join(f"""<li><a href="{ output_dir }/index.html">{ controller.get_title(p) } - { alias }</a></li>"""
                      for alias, p, output_dir in created)
    toc = f"""<html>
    <head>
    <title>Corpus website</title>
    </head>
    <body>
    <ul>
    { links }
    </ul>
    </body>
    </html>"""
    toc_file = destination / "index.html"
    toc_file.write_text(toc)

    return str(toc_file)
