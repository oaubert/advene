#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
"""Plugin loader.

"""

import imp
import os
import inspect
import zipfile
import zipimport

class PluginException(Exception):
    pass

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

        if os.path.exists(directory):
            it=self.standard_plugins(directory)
        elif '.zip' in directory:
            it=self.zip_plugins(directory)
        else:
            it=None

        if it:
            for d, fname in it:
                try:
                    p = Plugin(d, fname, self.prefix)
                    self.append(p)
                except PluginException:
                    # Silently ignore non-plugin files
                    continue
                except ImportError, e:
                    print "ImportError when loading %s: %s" % (fname, str(e))
                    continue

    def standard_plugins(self, d):
        for name in os.listdir(d):
            m, ext = os.path.splitext(name)
            if ext == '.py' and not name.startswith('_'):
                yield d, name

    def zip_plugins(self, d):
        """Extract the list of plugins from a .zip file import.
        """
        if not ('.zip' + os.sep) in d:
            return
        (zipname, plugins_dir) = d.split('.zip' + os.sep)
        # Zip files may use / as separator
        plugins_dir=plugins_dir.replace(os.sep, '/')
        zipname += '.zip'
        z=zipfile.ZipFile(zipname, 'r')
        p=[ os.path.splitext(n)[0]
            for n in z.namelist()
            if n.replace(os.sep, '/').startswith(plugins_dir) and n.endswith('.pyc')
            and not os.path.basename(n).startswith('_') ]
        for name in p:
            yield zipname, name

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
    def __init__(self, directory, fname, prefix="plugins"):
        def get_classes():
            """Return the classes defined in the module.
            """
            l=[ getattr(self._plugin, n)
                for n in dir(self._plugin) ]
            return [ c for c in l if inspect.isclass(c) ]

        fullname = os.path.join( directory, fname )

        if directory.endswith('.zip'):
            zi=zipimport.zipimporter(directory)
            self._plugin=zi.load_module(fname.replace('/', os.sep))
        else:
            name, ext = os.path.splitext(fname)
            if ext == '.py':
                try:
                    self._plugin = imp.load_source('_'.join( (prefix, name) ), fullname, open(fullname) )
                except Exception, e:
                    raise ImportError("Problem when loading %s : %s" % (fullname, unicode(e)))
            elif ext == '.pyc':
                try:
                    self._plugin = imp.load_compiled('_'.join( (prefix, name) ), fullname, open(fullname) )
                except Exception, e:
                    raise ImportError("Problem when loading %s : %s" % (fullname, unicode(e)))
        # Is this really a plugin ?
        if not hasattr(self._plugin, 'name') or not hasattr(self._plugin, 'register'):
            raise PluginException("%s is not a plugin" % fullname)
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

