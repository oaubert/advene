PARSER_META_PREFIX = "http://advene.liris.cnrs.fr/ns/parser-meta#"

class ModelError(Exception):
    """
    Integrity constraints of the Advene model have been violated.
    """
    pass
