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
"""Plugin loader.

"""

import imp
import os
import inspect

class PluginCollection(list):
    """A collection of plugins.

    A L{PluginCollection} is a list of L{Plugin} instance. It must be
    instanciated with the directory name.  The prefix is used to
    register the module in sys.modules (to avoid nameclashes).
    """
    def __init__(self, directory, prefix="plugins"):
        """Loads available plugins from directory.
        
        @param directory: the plugins directory
        @type directory: string (path)
        """
        super(PluginCollection, self).__init__()
        self.prefix=prefix
        for m in os.listdir(directory):
            name, ext = os.path.splitext(m)
            if ext == '.py' and not name.startswith('_'):
                p = Plugin(directory, name, self.prefix)
                self.append(p)

class Plugin(object):
    """A loaded Plugin.

    A Plugin *must* have a name attribute.

    @ivar _plugin: the loaded plugin instance
    @type _plugin: module
    @ivar _classes: a list of the classes implemented by module
    @type _classes: list of classes
    @ivar _filename: the source filename
    @type _filename: string (path)
    """
    def __init__(self, directory, name, prefix="plugins"):
        def get_classes():
            """Return the classes defined in the module.
            """
            l=[ getattr(self._plugin, n) 
                for n in dir(self._plugin) ]
            return [ c for c in l if inspect.isclass(c) ]

        fullname = os.path.join( directory, name + '.py' )
        self._plugin = imp.load_source('_'.join( (prefix, name) ), fullname, open(fullname) )
        self._filename = fullname
        self.name = self._plugin.name
        self._classes = get_classes()

    def __getattribute__ (self, name):
        """Use the defined method if available. Else, forward the request to the plugin.
        """
        try:
            return object.__getattribute__ (self, name)
        except AttributeError:
            return self._plugin.__getattribute__ (name)

    def __str__(self):
        try:
            name=self._plugin.name
        except AttributeError:
            name="loaded from %s" % self.filename
        return "Plugin %s" % name

if __name__ == '__main__':
    l = PluginCollection('plugins')
    for p in l:
        print p, ":", ",".join([ str(c) for c in p._classes ])

