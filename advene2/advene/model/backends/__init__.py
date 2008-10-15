def iter_backends():
    global _backends
    return iter (_backends)

def register_backend (b):
    global _backends
    _backends.insert (0, b)

def unregister_backend (b):
    global _backends
    _backends.remove (b)

class NoBackendClaiming (Exception):
    pass

class PackageInUse (Exception):
    pass

_backends = []
