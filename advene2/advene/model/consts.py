"""I define constants used all over the `advene.model` package."""

ADVENE_NS_PREFIX = "http://advene.liris.cnrs.fr/ns/"

# useful meta prefixes
PARSER_META_PREFIX = "%s%s" % (ADVENE_NS_PREFIX, "parser-meta#")
DC_NS_PREFIX = "http://purl.org/dc/elements/1.1/"
RDFS_NS_PREFIX = "http://www.w3.org/2000/01/rdf-schema#"

# other advene-related namespace URIs
ADVENE_XML = "%s%s" % (ADVENE_NS_PREFIX, "advene-xml/0.1")

# implementation-related constant
# used as the ``default`` parameter to specify that an exception should be
# raised on default
_RAISE = object()
