from advene.model import ADVENE_NS_PREFIX
from advene.model.serializers import register_unserialized_meta_prefix

PARSER_META_PREFIX = "%s%s" % (ADVENE_NS_PREFIX, "parser-meta#")
register_unserialized_meta_prefix(PARSER_META_PREFIX)
