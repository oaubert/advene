#! /usr/bin/python

"""Plugin loader
"""

import ihooks
import os

class PluginCollection(list):
    """A collection of plugins.

    A L{PluginCollection} is a list of L{Plugin} instance. It must be
    instanciated with the directory name.
    """
    def __init__(self, directory, prefix=""):
        """Loads available plugins from directory.
        
        @param directory: the plugins directory
        @type directory: string (path)
        """
        for m in os.listdir(directory):
            name, ext = os.path.splitext(m)
            if ext == '.py' and name.startswith(prefix) and not name.startswith('_'):
                p = Plugin(directory, name)
                self.append(p)

class Plugin(object):
    """A loaded Plugin.

    @ivar _plugin: the loaded plugin instance
    @type _plugin: module
    @ivar filename: the source filename
    @type filename: string (path)
    """
    def __init__(self, directory, name):
        loader = ihooks.BasicModuleLoader()
        info=loader.find_module_in_dir(name, directory)
        loader.load_module(name, info)
        importer = ihooks.BasicModuleImporter()
        importer.set_loader(loader)

        self._plugin = importer.import_module(name)
        self.filename = info[1]
	self.name = self._plugin.name

    def __getattribute__ (self, name):
        """Use the defined method if available. Else, forward the request to the plugin.
        """
        try:
            return object.__getattribute__ (self, name)
        except AttributeError, e:
            return self._plugin.__getattribute__ (name)

    def __str__(self):
        try:
            name=self._plugin.name
        except:
            name="loaded from %s" % self.filename
        return "Plugin %s" % name

if __name__ == '__main__':
    l=PluginCollection('plugins')
    for p in l:
        print p

