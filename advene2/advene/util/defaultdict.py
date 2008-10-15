# From ASPN python cookbook
import copy

class DefaultDict(dict):
    """Dictionary with a default value for unknown keys."""
    def __init__(self, default=None, **items):
        dict.__init__(self, **items)
        self.default = default

    def __getitem__(self, key):
        if key in self:
            return self.get(key)
        else:
            ## Need copy in case self.default is something like []
            return self.setdefault(key, copy.deepcopy(self.default))

    def __copy__(self):
        return DefaultDict(self.default, **self)
