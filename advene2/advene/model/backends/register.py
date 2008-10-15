import advene.model.backends.sqlite as sqlite_backend

# backend register functions

def iter_backends():
    global _backends
    return iter(_backends)

def register_backend(b):
    global _backends
    _backends.insert(0, b)

def unregister_backend(b):
    global _backends
    _backends.remove(b)

# implementation

_backends = []

# default registration

register_backend(sqlite_backend) 
