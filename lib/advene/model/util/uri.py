from urlparse import urljoin
from xml.dom.ext.reader import BASIC_RESOLVER


def push(uri, id):
    return "%s#%s" % (uri,id)

def pop(uri):
    sharp = uri.rfind('#')
    slash = uri.rfind('/')
    cut = max(sharp,slash)
    return uri[:cut],uri[(cut+1):]

def fragment(uri):
    sharp = uri.rfind('#')
    if sharp>0: return uri[(sharp+1):]
    else: return ''

def no_fragment(uri):
    sharp = uri.rfind('#')
    if sharp>0: return uri[:sharp]
    else: return uri

def open(uri):
    return BASIC_RESOLVER.resolve(uri, base='')
