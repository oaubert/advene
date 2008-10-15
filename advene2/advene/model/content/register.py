import advene.model.content.builtin as builtin

# content_handler register functions

def iter_content_handlers():
    global _content_handlers
    return iter(_content_handlers)

def register_content_handler(b):
    global _content_handlers
    _content_handlers.insert(0, b)

def unregister_content_handler(b):
    global _content_handlers
    _content_handlers.remove(b)

# implementation

_content_handlers = []

# default registration

register_content_handler(builtin)
