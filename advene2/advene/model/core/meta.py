from weakref import ref, ReferenceType

from advene import _RAISE
from advene.model.core.dirty import DirtyMixin

class WithMetaMixin(DirtyMixin):
    """Metadata access mixin.

    I factrorize all metradata-related code for classes Package and
    PackageElement.

    I also provide an alias mechanism to make frequent metadata easily
    accessible as python properties.
    """

    __cache = {}   # global dict, keys are (self, metadata-key)
    __dirty = None # local dict, generated for each instance by set_meta

    def get_meta(self, key, default=_RAISE):
        """Return the metadata associated to the given key.

        The returned value can be either an
        `advene.model.core.elemenet.PackageElement` or a string.

        If the given key does not exist: an KeyError is raised if default is 
        not given, else default is returned.

        If the metadata refers to an element but that element can not be
        reached, an UnreachableElement exception is raised, else default is
        returned.
        """
        cache = self.__cache
        val = cache.get((self, key))
        if isinstance(val, ReferenceType):
            val = val()
        if val is None:
            if hasattr(self, "ADVENE_TYPE"):
                p = self._owner
                eid = self._id
                typ = self.ADVENE_TYPE
            else:
                p = self
                eid = ""
                typ = ""
            tpl = p._backend.get_meta(p._id, eid, typ, key)
            if tpl is None:
                val = KeyError
            elif tpl[1]:
                val = p.get_element(tpl[0], default)
            else:
                val = tpl[0]
            cache[self,key] = val
        if val is KeyError:
            if default is _RAISE:
                raise KeyError(key)
            else:
                val = default
        return val

    def set_meta(self, key, val):
        """Set the metadata.

        ``val`` can either be a PackageElement or a string. If an element, it
        must be directly imported by the package of self, or a ModelError will
        be raised.
        """
        if hasattr(self, "ADVENE_TYPE"):
            p = self._owner
            eid = self._id
            typ = self.ADVENE_TYPE
        else:
            p = self
            eid = ""
            typ = ""
        if hasattr(val, "ADVENE_TYPE"):
            if not p._can_reference(val):
                raise ModelError, "Element should be directy imported"
            vstr = val.make_idref_for(p)
            vstr_is_idref = True
        else:
            vstr = str(val)
            vstr_is_idref = False
        dirty = self.__dirty
        if dirty is None:
            dirty = self.__dirty = {}
        self.__cache[self,key] = val
        dirty[key] = vstr, vstr_is_idref
        self.add_cleaning_operation_once(self.__clean)

    def __clean(self):
        dirty = self.__dirty
        if dirty:
            if hasattr(self, "ADVENE_TYPE"):
                p = self._owner
                eid = self._id
                typ = self.ADVENE_TYPE
            else:
                p = self
                eid = ""
                typ = ""
        while dirty:
            k,v = dirty.popitem()
            val, val_is_idref = v
            try:
                p._backend.set_meta(p._id, eid, typ, k, val, val_is_idref)
            except:
                dirty[k] = v
                raise

    @classmethod
    def make_metadata_property(cls, key, alias=None):
        """
        Attempts to create a python property in cls mapping to metadata key.

        If alias is None, key is considered as a URI, and the last part of
        that URI (after # or /) is used.

        Raises an AttributeError if cls already has a member with that name.
        """
        if alias is None:
            cut = max(key.rfind("#"), key.rfind("/"))
            alias = key[cut+1:]

        if hasattr(cls, alias):
            raise AttributeError(alias)

        def getter(obj):
            return obj.get_meta(key)

        def setter(obj, val):
            return obj.set_meta(key, val)

        def deller(obj):
            return self.set_meta(key, None)

        setattr(cls, alias, property(getter, setter, deller))
 
