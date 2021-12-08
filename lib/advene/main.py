#! /usr/bin/env python3
#
#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2021 Olivier Aubert <contact@olivieraubert.net>
#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

# Let's start by configuring logging
import logging
import logging.config
import logging.handlers
logger = logging.getLogger(__name__)

import os
import sys
import time

import advene.core.config as config

def main(app_dir=None):

    if app_dir is not None:
        # Chances are that we are running from a development tree
        logger.warning("Using specified path %s" % str(app_dir))
        config.data.fix_paths(str(app_dir))

    # Check for directories
    for d in ('resources', 'web'):
        dir_path = config.data.path[d]
        if not dir_path.exists():
            logger.error("""Error: the %s directory does not exist.
Advene seems to be either badly installed or badly configured (maybe both).
Aborting.""", dir_path)
            sys.exit(1)

    logfile = config.data.advenefile('advene.log', 'settings')
    # Configure RotatingFileHandler logging handler
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(name)s %(message)s'
            },
            'simple': {
                'format': '%(name)s %(levelname)s %(message)s'
            },
        },
        'handlers': {
            'console': {
                'level':'DEBUG',
                'class':'logging.StreamHandler',
                'formatter': 'simple'
            },
            'logfile': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': logfile,
                'formatter': 'verbose',
                'backupCount': 7,
            },
        },
        'root': {
            'handlers':['console', 'logfile'],
            'level': 'INFO',
        },
        'loggers': {
            'cherrypy.error': {
                'handlers': [ 'logfile' ],
                'propagate': False,
                'level': 'INFO',
            },
        }
    }
    # Handle ADVENE_DEBUG variable.
    for m in os.environ.get('ADVENE_DEBUG', '').split(':'):
        LOGGING['loggers'][m] = { 'level': 'DEBUG' }
        LOGGING['loggers'][m.replace('.', '_')] = { 'level': 'DEBUG' }
        # Plugin package name can be mangled
        if '.plugins' in m:
            LOGGING['loggers'][m.replace('.', '_').replace('_plugins_', '_app_plugins_')] = { 'level': 'DEBUG' }

    logging.config.dictConfig(LOGGING)
    # Do a forced rollover for the RotatingFileHandler
    for h in logging.root.handlers:
        if hasattr(h, 'doRollover'):
            h.doRollover()

    # Locale selection
    if config.data.preferences['language']:
        # A non-empty value overrides the system default
        os.environ['LANGUAGE'] = config.data.preferences['language']

    logger.warning("%s run at %s on %s", config.data.version_string, time.strftime("%d/%m/%y %H:%M:%S %Z"), sys.platform)

    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk

    filter = config.data.options.filter
    if filter == 'help':
        # List available filters.
        import advene.core.controller
        c = advene.core.controller.AdveneController()
        c.init()
        logger.warning("Available export filters:\n%s",
                     "\n".join("%s\t: %s (.%s extension)" % (v.get_id(),
                                                             v.name,
                                                             v.extension)
                               for v in c.get_export_filters()))
        c.on_exit()
        sys.exit(0)
    elif filter is not None:
        # A filter has been specified.
        import advene.core.controller
        c = advene.core.controller.AdveneController()
        c.init()
        l = [ v for v in c.get_export_filters() if v.get_id() == filter ]
        if not l:
            logger.error("Export filter %s is not defined", filter)
            c.on_exit()
            sys.exit(1)
        l = l[0]
        if not config.data.args:
            logger.error("Syntax: advene -f filter_name [-o output=foo.ext] input.azp")
            c.on_exit()
            sys.exit(1)
        ext = l.extension

        for f in config.data.args:
            output = config.data.options.options.get('output')
            if output is None:
                # Use the input filename, replacing its extension.
                output = ".".join((os.path.splitext(f)[0], ext))
                # In this case, we do not want to overwrite existing files
                if os.path.exists(output):
                    logger.error("Output file %s already exists. Remove it before proceeding.", output)
                    continue
            logger.warning("Converting %s into %s", f, output)
            c.load_package(f)
            # FIXME: could trigger events?
            c.apply_export_filter(c.package, l, output)
        c.on_exit()
        sys.exit(0)

    # First time configuration
    if config.data.first_run:
        import advene.gui.util.initialconfig
        c = advene.gui.util.initialconfig.Config()
        c.main()

    if config.data.os in ('linux', ) and 'DISPLAY' not in os.environ:
        logger.error("The DISPLAY environment variable is not set. Cannot continue.")
        sys.exit(1)

    from advene.gui.main import AdveneApplication
    app = AdveneApplication()
    try:
        # import hotshot
        # filename = "/tmp/pythongrind.prof"
        # prof = hotshot.Profile(filename, lineevents=1)
        # prof.runcall(gui.main, config.data.args)
        # prof.close()
        logger.debug("Before app.main" )
        app.main(config.data.args)
        logger.warning("After app.main" )
    except Exception:
        logger.warning("Got exception. Stopping services...", exc_info=True)

        if logfile is not None:
            d = Gtk.MessageDialog(None,
                                  Gtk.DialogFlags.MODAL,
                                  Gtk.MessageType.ERROR,
                                  Gtk.ButtonsType.OK,
                                  "An error occurred.")
            d.format_secondary_text("You can inform the Advene developers by sending the file\n %s\n to support@advene.org, along with a description of how the bug occurred." % logfile)

            def q(*p):
                Gtk.main_quit()
                return True

            d.connect('response', q)
            d.show()
            Gtk.main()

if __name__ == "__main__":
    sys.exit(main())
