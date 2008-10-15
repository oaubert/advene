import advene.model.serializers.advene_xml as advene_xml_serializer
import advene.model.serializers.advene_zip as advene_zip_serializer
import advene.model.serializers.cinelab_xml as cinelab_xml_serializer
import advene.model.serializers.cinelab_zip as cinelab_zip_serializer

# serializer register functions

def iter_serializers():
    global _serializers
    return iter(_serializers)

def register_serializer(b):
    global _serializers
    _serializers.insert(0, b)

def unregister_serializer(b):
    global _serializers
    _serializers.remove(b)

# implementation

_serializers = []

# default registrations

register_serializer(advene_xml_serializer)
register_serializer(advene_zip_serializer)
register_serializer(cinelab_xml_serializer)
register_serializer(cinelab_zip_serializer)
