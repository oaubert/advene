from bisect import insort

from advene.model.consts import PARSER_META_PREFIX

# unserialized prefices register functions

def iter_unserialized_meta_prefix():
    """Iter over all the metadata key prefixes that must not be serialized.

    Note that they are iterated in lexicographic order.
    """
    return iter(_unserialized_meta_prefixes)

def register_unserialized_meta_prefix(p):
    """Registers a new prefix for metadata keys that must not be serialized.

    Some metadata are used at runtime only, and should not be serialized in
    persistent storages of packages.
    """
    insort(_unserialized_meta_prefixes, p)

# implementation

_unserialized_meta_prefixes = []

# default registrations

register_unserialized_meta_prefix(PARSER_META_PREFIX)

