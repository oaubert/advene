"""Import external data.

Provides a generic framework to import/convert external data.

The general idea is:
* Create an instance of Importer, called im.
  If the destination package already exists, call the constructor with
  package and defaultype named parameters.

* Initialisation:
  * If the destination package already exists, set the
    im.package
    and
    im.defaultype
    to appropriate values
  
  * If you want to create a new package with specific type and schema id, use
    im.create_package(schemaid=..., annotationtypeid=...)
  
  * If nothing is given, a default package will be created, with a
    default schema and annotationtype

* Conversion:
Call the
im.process_file(filename)
which will return the package containing the converted annotations
"""

import sys
import time
import sre
import os

import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment

import advene.util.handyxml as handyxml
import xml.dom

class GenericImporter(object):
    def __init__(self, author='importer', package=None, defaulttype=None):
        self.package=package
        self.author=author
        self.timestamp=time.strftime("%F")
        self.defaulttype=defaulttype
        # FIXME: implement self.offset (in ms)

    def process_file(self, filename):
        """Abstract method.

        When called, it will parse the file and execute the
        self.convert annotations with a dictionary as parameter.
        """
        pass
    
    def create_annotation (self, type_=None, begin=None, end=None,
                           data=None, ident=None, author=None,
                           timestamp=None, title=None):
        """Create an annotation in the package
        """
        if ident is None:
            a=self.package.createAnnotation(type=type_,
                                            fragment=MillisecondFragment(begin=begin, end=end))
        else:
            a=self.package.createAnnotation(type=type_,
                                            ident=ident,
                                            fragment=MillisecondFragment(begin=begin, end=end))            
        a.author=author
        a.date=timestamp
        a.title=title
        a.content.data = data
        self.package.annotations.append(a)

    def create_package(self,
                       filename=None,
                       annotationtypeid='imported-type',
                       schemaid='imported-schema'):
        """Create a package with the given schema and  annotation type.
        Returns a tuple (package, annotationtype)
        """
        p=Package(uri=filename, source=None)
        
        s=p.createSchema(ident=schemaid)
        s.author=self.author
        s.date=self.timestamp
        s.title=s.id
        p.schemas.append(s)
        
        at=s.createAnnotationType(ident=annotationtypeid)
        at.author=self.author
        at.date=self.timestamp
        at.title=at.id
        at.mimetype='text/plain'
        s.annotationTypes.append(at)

        return p, at

    def convert(self, source):
        """Converts the source elements to annotations.

        Source is an iterator or a list returning dictionaries.
        The following keys MUST be defined:
        - begin (in ms)
        - end or duration (in ms)
        - content
        The following keys are optional:
        - id
        - type (which must be a *type*, not a type-id)
        """
        if self.package is None:
            self.package, self.defaulttype=self.create_package()
        for d in source:
            try:
                begin=d['begin']
            except KeyError:
                raise Exception("Begin is mandatory")
            if 'end' in d:
                end=d['end']
            elif 'duration' in d:
                end=begin+d['duration']
            else:
                raise Exception("end or duration is missing")
            try:
                content=d['content']
            except KeyError:
                content="Default content"
            try:
                ident=d['id']
            except KeyError:
                ident=None
            try:
                type_=d['type']
            except KeyError:
                type_=self.defaulttype
                if type_ is None:
                    if len(self.package.annotationTypes) > 0:
                        type_ = self.package.annotationTypes[0]
                    else:
                        raise Exception("No type")
            try:
                author=d['author']
            except KeyError:
                author=self.author
            try:
                title=d['title']
            except KeyError:
                title=content[:20]
            try:
                timestamp=d['timestamp']
            except KeyError:
                timestamp=self.timestamp

            self.create_annotation (type_=type_,
                                    begin=begin,
                                    end=end,
                                    data=content,
                                    ident=ident,
                                    author=author,
                                    title=title,
                                    timestamp=timestamp)


class TextImporter(GenericImporter):
    """Text importer.

    In addition to the parameters of GenericImporter, you can specify

    regexp: a regexp with named matching parentheses (coded
            as "(?P<name>\d+)" for instance, see sre doc) returning
            the parameters needed by GenericImporter.convert
            
    encoding: the default encoding for the textfile
    """
    
    def __init__(self, regexp=None, encoding=None, **kw):
        super(TextImporter, self).__init__(**kw)
        if regexp is None:
            regexp="(?P<begin>\d+)\s(?P<end>\d+)\s(?P<content>.+)"
        self.regexp=sre.compile(regexp)
        if encoding is None:
            encoding='latin1'
        self.encoding=encoding

    def iterator(self, f):
        for l in f:
            l=l.rstrip()
            l=unicode(l, self.encoding).encode('utf-8')
            m=self.regexp.search(l)
            if m is not None:
                yield m.groupdict()

    def set_regexp(self, r):
        self.regexp=sre.compile(r)
        
    def process_file(self, filename):
        f=open(filename, 'r')
        if self.package is None:
            self.create_package()
        self.convert(self.iterator(f))
        return self.package

class LsDVDImporter(GenericImporter):
    """lsdvd importer.
    """
    def __init__(self, regexp=None, encoding=None, **kw):
        super(LsDVDImporter, self).__init__(**kw)
        self.command="/usr/bin/lsdvd -c"
        #Chapter: 01, Length: 00:01:16, Start Cell: 01
        self.regexp="^\s*Chapter:\s*(?P<chapter>\d+),\s*Length:\s*(?P<h>\d\d):(?P<m>\d\d):(?P<s>\d\d)"
        self.encoding='latin1'

    def iterator(self, f):
        reg=sre.compile(self.regexp)
        begin=1
        for l in f:
            l=l.rstrip()
            l=unicode(l, self.encoding).encode('utf-8')
            m=reg.search(l)
            if m is not None:
                d=m.groupdict()
                duration=1000*(long(d['s'])+60*long(d['m'])+3600*long(d['h']))
                res={'content': "Chapter %s" % d['chapter'],
                     'begin': begin,
                     'duration': duration}
                begin += duration + 10
                yield res

    def process_file(self, filename):
        if filename != 'lsdvd':
            pass
        f=os.popen(self.command, "r")
        if self.package is None:
            self.create_package()
        self.convert(self.iterator(f))
        return self.package

class ChaplinImporter(GenericImporter):
    """lsdvd importer.
    """
    def __init__(self, **kw):
        super(ChaplinImporter, self).__init__(**kw)
        self.command="/usr/bin/chaplin -c"
        #   chapter 03  begin:    200.200 005005 00:03:20.05
        self.regexp="^\s*chapter\s*(?P<chapter>\d+)\s*begin:\s*.+(?P<h>\d\d):(?P<m>\d\d):(?P<s>\d\d)"
        self.encoding='latin1'

    def iterator(self, f):
        reg=sre.compile(self.regexp)
        begin=1
        end=1
        chapter=None
        for l in f:
            l=l.rstrip()
            l=unicode(l, self.encoding).encode('utf-8')
            m=reg.search(l)
            if m is not None:
                d=m.groupdict()
                end=1000*(long(d['s'])+60*long(d['m'])+3600*long(d['h']))
                if chapter is not None:
                    res={ 'content': "Chapter %s" % chapter,
                          'begin': begin,
                          'end': end }
                    yield res
                chapter=d['chapter']
                begin=end
        # FIXME: the last chapter is not valid (no end value). We
        # should run 'chaplin -l' and get its length there.

    def process_file(self, filename):
        if filename != 'chaplin':
            pass
        f=os.popen(self.command, "r")
        if self.package is None:
            self.create_package()
        self.convert(self.iterator(f))
        return self.package

class XiImporter(GenericImporter):
    """Xi importer.
    """
    def __init__(self, **kw):
        super(XiImporter, self).__init__(**kw)
        self.factors = {'s': 1000,
                        'ms': 1}
        self.anchors={}
        self.signals={}

    def iterator(self, xi):
        for t in xi.Turn:
            d={}
            d['begin']=self.anchors[t.start]
            d['end']=self.anchors[t.end]
            clist=[]
            try:
                for vc in t.Verbal[0].VContent:
                    clist.append(" ".join([ t.value for t in vc.Token ]))
                content = "\n".join(clist)
            except AttributeError:
                content = "No verbal content"

            d['content']=content
            yield d
            
    def process_file(self, filename):
        xi=handyxml.xml(filename)

        # self.signals init
        for s in xi.Signals[0].Signal:
            self.signals[s.id] = s.loc

        # self.anchors init
        filename=None
        for a in xi.Anchors[0].Anchor:
            self.anchors[a.id] = long(float(a.offset.replace(',','.')) * self.factors[a.unit])
            if filename is None:
                filename = self.signals[a.refSignal]
            elif filename != self.signals[a.refSignal]:
                print "Erreur: plusieurs fichiers sources, non supportes"
                sys.exit(1)

        self.convert(self.iterator(xi))
        return self.package

class ElanImporter(GenericImporter):
    """Elan importer.
    """
    def __init__(self, **kw):
        super(ElanImporter, self).__init__(**kw)
        self.anchors={}
        self.atypes={}
        self.relations=[]

    def xml_to_text(self, element):
        l=[]
        if element._get_nodeType() is xml.dom.Node.TEXT_NODE:
            # Note: element._get_data() returns a unicode object
            # that happens to be in the default encoding (iso-8859-1
            # currently on my system). We encode it to utf-8 to
            # be sure to deal only with this encoding afterwards.
            l.append(element._get_data().encode('utf-8'))
        elif element._get_nodeType() is xml.dom.Node.ELEMENT_NODE:
            for e in element._get_childNodes():
                l.append(self.xml_to_text(e))
        return "".join(l)

    def iterator(self, elan):
        for tier in elan.TIER:
            for an in tier.ANNOTATION:
                d={}
                d['type']=self.atypes[tier.LINGUISTIC_TYPE_REF]
                
                if hasattr(an, 'ALIGNABLE_ANNOTATION'):
                    # Annotation on a timeline
                    al=an.ALIGNABLE_ANNOTATION[0]
                    d['begin']=self.anchors[al.TIME_SLOT_REF1]
                    d['end']=self.anchors[al.TIME_SLOT_REF2]
                    d['id']=al.ANNOTATION_ID
                    d['content']=self.xml_to_text(al.ANNOTATION_VALUE[0].node)
                    yield d
                elif hasattr(an, 'REF_ANNOTATION'):
                    # Reference to another annotation. We will reuse the
                    # related annotation's fragment and put it in relation
                    ref=an.REF_ANNOTATION[0]
                    d['id']=ref.ANNOTATION_ID
                    d['content']=self.xml_to_text(ref.ANNOTATION_VALUE[0].node)
                    # Related annotation:
                    rel_id = ref.ANNOTATION_REF
                    rel_an=self.package.annotations['#'.join( (self.package.uri,
                                                               rel_id) ) ]
                    # We reuse the related annotation fragment
                    d['begin'] = rel_an.fragment.begin
                    d['end'] = rel_an.fragment.end
                    self.relations.append( (rel_id, d['id']) )
                    yield d
                else:
                    raise Exception('Unknown annotation type')

    def create_relations(self):
        """Postprocess the package to create relations."""        
        # We could store in self.relations the origin annotationtypes
        # and create corresponding relation types for each couple
        for (source_id, dest_id) in self.relations:
            source=self.package.annotations['#'.join( (self.package.uri,
                                                       source_id) ) ]
            dest=self.package.annotations['#'.join( (self.package.uri,
                                                     dest_id) ) ]
            r=self.package.createRelation(
                ident='r'+source_id+'_'+dest_id,
                type=self.rtype,
                author=source.author,
                date=source.date,
                members=(source, dest))
            r.title="Relation between %s and %s" % (source_id, dest_id)
            self.package.relations.append(r)

    def process_file(self, filename):
        elan=handyxml.xml(filename)

        if self.package is None:
            self.package=Package(uri='dummy:1', source=None)
    
        p=self.package        
        schema=p.createSchema(ident='elan')
        #schema.author=elan.AUTHOR
        schema.date=elan.DATE
        schema.title="ELAN converted schema"
        p.schemas.append(schema)
        
        # self.anchors init
        if elan.HEADER[0].TIME_UNITS != 'milliseconds':
            raise Exception('Cannot process non-millisecond fragments')
        
        for a in elan.TIME_ORDER[0].TIME_SLOT:
            self.anchors[a.TIME_SLOT_ID] = long(a.TIME_VALUE)

        # Process types
        for lt in elan.LINGUISTIC_TYPE:
            at=schema.createAnnotationType(ident=lt.LINGUISTIC_TYPE_ID)
            #at.author=schema.author
            at.date=schema.date
            at.title=at.id
            at.mimetype='text/plain'
            schema.annotationTypes.append(at)
            self.atypes[at.id]=at

        rt=schema.createRelationType(ident='elan_ref')
        #rt.author=schema.author
        rt.date=schema.date
        rt.title="ELAN reference"
        rt.mimetype='text/plein'
        schema.relationTypes.append(rt)
        self.rtype=rt

        self.convert(self.iterator(elan))
        self.create_relations()
        return self.package

class SubtitleImporter(GenericImporter):
    """Subtitle importer.

    srt importer
    """    
    def __init__(self, encoding=None, **kw):
        super(SubtitleImporter, self).__init__(**kw)
        if encoding is None:
            encoding='latin1'
        self.encoding=encoding

    def srt_iterator(self, f):
        base='(\d\d):(\d\d):(\d+),(\d+)'
        pattern=sre.compile(base + '.+' + base)
        for l in f:
            tc=None
            content=[]
            for line in f:
                line=line.rstrip()
                match=pattern.search(line)
                if match is not None:
                    l=[ long(i) for i in  match.groups()]
                    (h,m,s,ms) = l[:4]
                    b=ms+s*1000+m*60000+h*3600000
                    (h,m,s,ms) = l[4:]
                    e=ms+s*1000+m*60000+h*3600000
                    tc=(b,e)
                elif len(line) == 0:
                    # Empty line: end of subtitle
                    # Convert if and reset the data
                    d={'begin': tc[0],
                       'end': tc[1],
                       'content': "\n".join(content)}
                    tc=None
                    content=[]
                    yield d
                else:
                    if tc is not None:
                        content.append(unicode(line, self.encoding).encode('utf-8'))
                    # else We could check line =~ /^\d+$/
                        
    def process_file(self, filename):
        f=open(filename, 'r')
        if self.package is None:
            self.package, self.defaulttype=self.create_package(schemaid='subtitle-schema',
                                                               annotationtypeid='subtitle')
        # FIXME: implement subtitle type detection
        self.convert(self.srt_iterator(f))
        return self.package

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    if fname == 'chaplin':
        i=ChaplinImporter()
        p, at=i.create_package(schemaid='dvd',
                               annotationtypeid='chapter')
        i.package=p
        i.defaulttype=at
        # FIXME: should specify title
        p.setMetaData (config.data.namespace, "mediafile", "dvdsimple:///dev/dvd@1,1")        
    elif fname == 'lsdvd':
        i=LsDVDImporter()
        p, at=i.create_package(schemaid='dvd',
                               annotationtypeid='chapter')
        i.package=p
        i.defaulttype=at
        p.setMetaData (config.data.namespace, "mediafile", "dvdsimple:///dev/dvd@1,1")
    elif fname.endswith('.txt'):
        i=TextImporter(author='text-importer')
    elif fname.endswith('.srt'):
        i=SubtitleImporter(author='subtitle-importer')
    elif fname.endswith('.eaf'):
        i=ElanImporter(author='elan-importer')
    elif fname.endswith('.xml'):
        # FIXME: we should check the XML content
        i=XiImporter(author='xi-importer')
        p, at=i.create_package(schemaid='xi-schema',
                               annotationtypeid='xi-verbal')
        i.package=p
        i.defaulttype=at
    else:
        print "No importer for %s" % fname
        sys.exit(1)

    # FIXME: i.process_options()
    # (for .sub conversion for instance, --fps, --offset)
    print "Converting %s to %s" % (fname, pname)
    p=i.process_file(fname)
    p.save(pname)
