"""
Cinelab parser implementation.
"""
from xml.etree.ElementTree import iterparse
from xml.parsers.expat import ExpatError

from advene.model.cam.consts import CAM_XML
import advene.model.serializers.cinelab_xml as serializer
from advene.model.parsers.advene_xml import Parser as _AdveneXmlParser
from advene.utils.files import get_path




class Parser(_AdveneXmlParser):
    NAME = serializer.NAME
    EXTENSION = serializer.EXTENSION
    MIMETYPE = serializer.MIMETYPE
    SERIALIZER = serializer # may be None for some parsers

    # this implementation tries to maximize the reusing of code from 
    # _AdveneXmlParser. It does so by "luring" it into using some methods
    # of self.package instead of others. This is a bit of a hack, but works
    # well... It assumes, however, that the parser is *not* multithreaded.

    _NAMESPACE_URI = CAM_XML

    def __init__(self, file_, package):
        _AdveneXmlParser.__init__(self, file_, package)

    def manage_package_subelements(self):
        self.optional_sequence("imports")
        self.optional_sequence("annotation-types")
        self.optional_sequence("relation-types")
        self.optional_sequence("tags")
        self.optional_sequence("medias")
        self.optional_sequence("resources")
        self.optional_sequence("annotations")
        self.optional_sequence("relations")
        self.optional_sequence("views")
        self.optional_sequence("queries", items_name="query")
        self.optional_sequence("schemas")
        self.optional_sequence("lists")
        self.optional_sequence("external-tag-associations",
                               items_name="association")

    # luring methods (cf. comment at top of that class)

    def handle_annotation_type(self):
        # lure `_AdveneXmlParser.handle_tag` into using
        # `create_annotation_type` instead of `create_tag`
        # by overridding method at instance level
        self.package.create_tag = self.package.create_annotation_type
        _AdveneXmlParser.handle_tag(self)
        # restore class level method
        del self.package.create_tag

    def handle_relation_type(self):
        # lure `_AdveneXmlParser.handle_tag` into using
        # `create_relation_type` instead of `create_tag`
        # by overridding method at instance level
        self.package.create_tag = self.package.create_relation_type
        _AdveneXmlParser.handle_tag(self)
        # restore class level method
        del self.package.create_tag

    def handle_tag(self, element=None):
        # lure `_AdveneXmlParser.handle_tag` into using
        # `create_user_tag` instead of `create_tag` or
        # `associate_user_tag` instead of `associate_tag`
        # by overridding method at instance level
        if element is None:
            self.package.create_tag = self.package.create_user_tag
        else:
            self.package.associate_tag = self.package.associate_user_tag
        _AdveneXmlParser.handle_tag(self, element)
        # restore class level method
        if element is None:
            del self.package.create_tag
        else:
            del self.package.associate_tag

    def handle_schema(self):
        # lure `_AdveneXmlParser.handle_list` into using
        # `create_schema` instead of `create_list`
        # by overridding method at instance level
        self.package.create_list = self.package.create_schema
        _AdveneXmlParser.handle_list(self)
        # restore class level method
        del self.package.create_list

    def handle_list(self):
        # lure `_AdveneXmlParser.handle_list` into using
        # `create_user_list` instead of `create_list`
        # by overridding method at instance level
        self.package.create_list = self.package.create_user_list
        _AdveneXmlParser.handle_list(self)
        # restore class level method
        del self.package.create_list

    def handle_element(self, advene_tag):
        # lure `_AdveneXmlParser.handle_element` into using
        # `associate_user_tag` instead of `associate_tag`
        # by overridding method at instance level
        self.package.associate_tag = self.package.associate_user_tag
        _AdveneXmlParser.handle_element(self, advene_tag)
        # restore class level method
        del self.package.associate_tag

    def handle_association(self):
        # lure `_AdveneXmlParser.handle_association` into using
        # `associate_user_tag` instead of `associate_tag`
        # by overridding method at instance level
        self.package.associate_tag = self.package.associate_user_tag
        _AdveneXmlParser.handle_association(self)
        # restore class level method
        del self.package.associate_tag

#
