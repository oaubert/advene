#! /usr/bin/python

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
        except AttributeError, e:
            return self._plugin.__getattribute__ (name)

    def __str__(self):
        try:
            name=self._plugin.name
        except:
            name="loaded from %s" % self.filename
        return "Plugin %s" % name

if __name__ == '__main__':
    l = PluginCollection('plugins')
    for p in l:
        print p, ":", ",".join([ str(c) for c in p._classes ])

