ADVENE_NS_PREFIX = "http://advene.liris.cnrs.fr/ns/"
PARSER_META_PREFIX = "%s%s" % (ADVENE_NS_PREFIX, "parser-meta#")

class ModelError(Exception):
    """
    Integrity constraints of the Advene model have been violated.
    """
    pass
