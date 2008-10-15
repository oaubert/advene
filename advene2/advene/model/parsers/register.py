import advene.model.parsers.advene_xml as advene_xml_parser

# parser register functions

def iter_parsers():
    global _parsers
    return iter(_parsers)

def register_parser(b):
    global _parsers
    _parsers.insert(0, b)

def unregister_parser(b):
    global _parsers
    _parsers.remove(b)

# implementation

_parsers = []

# default registration

register_parser(advene_xml_parser)
