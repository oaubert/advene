"""
Serializer implementation
=========================

yet to be done
"""

from bisect import bisect, insort


# serializer register functions

def iter_serializers():
    global _serializers
    return iter(_serializers)

def register_serializer(b):
    global _serializers
    _serializers.insert(0, b)

def unregister_serializer(b):
    global _serializers
    _serializers.remove(b)


def iter_unserialized_meta_prefix():
    """Iter over all the metadata key prefixes that must not be serialized.

    Note that they are serialized in lexicographic order.
    """
    return iter(_unserialized_meta_prefixes)

def register_unserialized_meta_prefix(p):
    """Registers a new prefix for metadata keys that must not be serialized.

    Some metadata are used at runtime only, and should not be serialized in
    persistent storages of packages.
    """
    insort(_unserialized_meta_prefixes, p)


# implementation

_serializers = []
_unserialized_meta_prefixes = []
