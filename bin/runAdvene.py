#! /usr/bin/env python

import sys
import time
import xml.dom.ext

import advene.model.constants
from advene.model.package import Package
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment
import advene.model.viewable as viewable
from cStringIO import StringIO

from advene.model.tal.context import AdveneContext

def setSystemDefaultView(str):
    viewable.__system_default_view = (StringIO(str))

def myPrettyPrint (x):
    if hasattr (x, '_getModel'):
        x = x._getModel ()
    return xml.dom.ext.PrettyPrint (x)


try:
    __IPYTHON__
except NameError:
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed()
    # Now ipshell() will open IPython anywhere in the code
else:
    # Define a dummy ipshell() so the same code doesn't crash inside an
    # interactive IPython
    def ipshell(): pass

if __name__ == "__main__":

    try:
        fichier = sys.argv[1]
    except IndexError:
        fichier = '../test.xml'

    for i in (
        "pp = myPrettyPrint",
        "p0 = Package(uri='dummy:1', source=None)",
        "p = Package(uri='%s')" % fichier,
        "a = p.annotations[-1]",
        "r = p.relations[-1]",
        "v = p.views[-1]",
        "s = p.schemas[-1]",
        "at = p.annotationTypes[-1]",
        "rt = p.relationTypes[-1]",
        "f = advene.model.fragment.MillisecondFragment (begin=123, end=456)",
    ):
        try:
            exec (i)
            print i
        except:
            print 'FAILED:', i
    try:
        dico = {
            'package_url': "/packages/advene",
            'snapshot': {},
            'namespace_prefix': { 'advenetool':
                                  "/".join([advene.model.constants.adveneNS, "advenetool"]),
                                  'dc': 'http://purl.org/dc/elements/1.1/'}
            }
        c = AdveneContext(a, dico)
        print "c = AdveneContext(a)"
        c.log = advene.model.tal.context.DebugLogger ()
    except:
        pass

    ipshell ()
