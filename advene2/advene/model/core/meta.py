from weakref import ref, ReferenceType

from advene import _RAISE
from advene.model.core.dirty import DirtyMixin

class WithMetaMixin(DirtyMixin):
    """Metadata access mixin.

    I am a mixin for a class with methods _get_meta(self, key), _set_meta
    (self, key, val) and _can_reference(self, element). I provide methods
    get_meta and set_meta method, that cache the values of metadata to reduce
    access to the backend.

    I also provide an alias mechanism to make frequent metadata easily
    accessible as python properties.
    """

    __cache = {}   # global dict, keys are (self, metadata-key)
    __dirty = None # local dict, generated for each instance set_meta

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
            try:
                val = self._get_meta(key)
            except KeyError, e:
                val = cache[self, key] = _RAISE # caching _RAISE
                if default is _RAISE:
                    raise
                else:
                    return default
            except UnreachableElement, e:
                if default is _RAISE:
                    raise
                else:
                    raise default
            else:
                if hasattr(val, "ADVENE_TYPE"):
                    cache[self, key] = ref(val)
                else:
                    cache[self, key] = val
        elif val is _RAISE: # cached _RAISE
            if default is _RAISE:
                raise KeyError, key
            else:
                val = default
        return val

    def set_meta(self, key, val):
        """Set the metadata.

        ``val`` can either be a PackageElement or a string. If an element, it
        must be directly imported by the package of self, or a ModelError will
        be raised.
        """
        if hasattr(val, "ADVENE_TYPE") and not self._can_reference(val):
            raise ModelError, "Element should be directy imported"
        else:
            val = str(val)

        dirty = self.__dirty
        if dirty is None:
            dirty = self.__dirty = {}
        self.__cache[self,key] = val
        dirty[key] = val
        self.add_cleaning_operation_once(self.__clean)

    def __clean(self):
        dirty = self.__dirty
        while dirty:
            k,v = dirty.popitem()
            try:
                self._set_meta(k,v)
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
 
