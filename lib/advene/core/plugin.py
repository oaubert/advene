#! /usr/bin/python

import ihooks
import os

class PluginCollection(list):
    def from_dir(self, d, prefix=""):
        for m in os.listdir(d):
            name, ext = os.path.splitext(m)
            if ext == '.py' and name.startswith(prefix) and not name.startswith('_'):
                p = Plugin(d, name)
                self.append(p)

class Plugin(object):
    def __init__(self, directory, name):
        loader = ihooks.BasicModuleLoader()
        info=loader.find_module_in_dir(name, directory)
        loader.load_module(name, info)
        importer = ihooks.BasicModuleImporter()
        importer.set_loader(loader)

        self._plugin = importer.import_module(name)
        self.filename = info[1]

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
    l=PluginCollection()
    l.from_dir('plugins')
    for p in l:
        print p

