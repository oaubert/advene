"""Import external data."""

import sys
import time
import sre

from advene.model.package import Package
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment

import advene.util.handyxml as handyxml

class GenericImporter(object):
    def __init__(self, package=None, author='importer', defaulttype=None):
        self.package=package
        self.author=author
        self.timestamp=time.strftime("%F")
        self.defaulttype=defaulttype

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
                                            fragment=MillisecondFragment(begin=begin, end=end),
                                            ident=ident)
        else:
            a=self.package.createAnnotation(type=type_,
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
            elif duration in d:
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

class XiImporter(GenericImporter):
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

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    if fname.endswith('.txt'):
        i=TextImporter(author='textimporter')
    elif fname.endswith('.xml'):
        # FIXME: we should check the XML content
        i=XiImporter(author='xiimporter')
        p, at=i.create_package(schemaid='xi-schema',
                               annotationtypeid='xi-verbal')
        i.package=p
        i.defaulttype=at
    else:
        print "No importer for %s" % fname
        sys.exit(1)

    # FIXME: i.process_options()
    print "Converting %s to %s" % (fname, pname)
    p=i.process_file(fname)
    p.save(pname)
