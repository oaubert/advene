from advene import RAISE

class WithMetaMixin:
    """
    I am a mixin for a class with methods _get_meta (self, key) and _set_meta
    (self, key, val). I provide them with equivalent methods get_meta and
    set_meta method, that cache the values of metadata to reduce access to
    the backend.

    I also provide an alias mechanism to make frequent metadata easily
    accessible as python properties.
    """

    # TODO : do the actual caching

    def get_meta (self, key, default=None):
        """
        Return the metadata with given key.

        If the given key does not exist: an KeyError is raised if default is RAISE, else default is 
        returned.
        """
        return self._get_meta (key, default)

    def set_meta (self, key, val):
        return self._set_meta (key, val)

    @classmethod
    def make_metadata_property (cls, key, alias=None):
        """
        Attempts to create a python property in cls mapping to metadata key.

        If alias is None, key is considered as a URI, and the last part of
        that URI (after # or /) is used.

        Raises an AttributeError if cls already has a member with that name.
        """
        if alias is None:
            cut = max (key.rfind("#"), key.rfind("/"))
            alias = key[cut+1:]

        if hasattr (cls, alias):
            raise AttributeError, alias

        def getter (obj):
            return obj.get_meta (key)

        def setter (obj, val):
            return obj.set_meta (key, val)

        def deller (obj):
            return self.set_meta (key, None)

        setattr (cls, alias, property (getter, setter, deller))
 
