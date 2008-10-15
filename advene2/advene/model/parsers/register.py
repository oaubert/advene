import advene.model.parsers.advene_xml as advene_xml_parser
import advene.model.parsers.advene_zip as advene_zip_parser
import advene.model.parsers.cinelab_xml as cinelab_xml_parser
import advene.model.parsers.cinelab_zip as cinelab_zip_parser


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

register_parser(advene_xml_parser.Parser)
register_parser(advene_zip_parser.Parser)
register_parser(cinelab_xml_parser.Parser)
register_parser(cinelab_zip_parser.Parser)
