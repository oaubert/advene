#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
import unittest

import sys
sys.path.insert(0, ".")

from advene.util.expat import PyExpat

from modeled import Modeled

class ModeledTestCase(unittest.TestCase):

    xml = u"""<?xml version="1.0" encoding="utf-8"?>
<test>
  <a/>
  <b/>
  <c id="1"/>
  <c id="2"/>
  <c id="3"/>
  <d/>
  This text will be ignored
  <e/>
  <f/>
</test>
    """

    fooNS = "http://foo.com/"

    xml_w_ns = u"""<?xml version="1.0" encoding="utf-8"?>
<test xmlns="%s">
  <a/>
  <b/>
  <c/>
</test>
    """ % fooNS

    def setUp(self):
        self.reader = PyExpat.Reader()
        self.doc = self.reader.fromString(self.xml)
        self.element = self.doc.documentElement
        self.modeled = Modeled(self.element)

        self.doc_w_ns = self.reader.fromString(self.xml_w_ns)
        self.element_w_ns = self.doc_w_ns.documentElement
        self.modeled_w_ns = Modeled(self.element_w_ns)

    def tearDown(self):
        self.reader.releaseNode(self.doc)
        self.reader.releaseNode(self.doc_w_ns)

    def test_getModelChildren__length(self):
        self.assertEqual(
            len(self.modeled._getModelChildren()),
            8
        )

    def test_getChild__no_arg(self):
        e = self.modeled._getChild()
        self.assert_(e)
        self.assertEqual(e.localName,"a")

    def test_getChild__match_alone__qname(self):
        e = self.modeled._getChild((None,"d"))
        self.assert_(e)
        self.assertEqual(e.localName,"d")
        e = self.modeled._getChild((None,"g"))
        self.assertEqual(e, None)

    def test_getChild__match_alone__element(self):
        elt = self.modeled._getChild((None,"d"))
        e = self.modeled._getChild(elt)
        self.assert_(e)
        self.assert_(e==elt)
        e = self.modeled._getChild(self.element)
        self.assertEqual(e, None)

    def test_getChild__before_alone__qname(self):
        e = self.modeled._getChild(before=(None,"b"))
        self.assert_(e)
        self.assertEqual(e.localName,"a")
        e = self.modeled._getChild(before=(None,"a"))
        self.assertEqual(e, None)

    def test_getChild__before_alone__element(self):
        elt = self.modeled._getChild((None,"b"))
        e = self.modeled._getChild(before=elt)
        self.assert_(e)
        self.assertEqual(e.localName,"a")
        elt = e
        e = self.modeled._getChild(before=elt)
        self.assertEqual(e, None)

    def test_getChild__after_alone__qname(self):
        e = self.modeled._getChild(after=(None,"e"))
        self.assert_(e)
        self.assertEqual(e.localName,"f")
        e = self.modeled._getChild(after=(None,"f"))
        self.assertEqual(e, None)

    def test_getChild__after_alone__element(self):
        elt = self.modeled._getChild((None,"e"))
        e = self.modeled._getChild(after=elt)
        self.assert_(e)
        self.assertEqual(e.localName,"f")
        elt = e
        e = self.modeled._getChild(after=elt)
        self.assertEqual(e, None)

    def test_getChild__before_and_match(self):
        e = self.modeled._getChild((None, "e"), before=(None,"f"))
        self.assert_(e)
        self.assertEqual(e.localName, "e")
        e = self.modeled._getChild((None, "d"), before=(None,"f"))
        self.assertEqual(e,None)

    def test_getChild__before_and_after(self):
        e = self.modeled._getChild(after=(None,"d"),before=(None,"f"))
        self.assert_(e)
        self.assertEqual(e.localName,"e")
        e = self.modeled._getChild(after=(None,"e"),before=(None,"f"))
        self.assertEqual(e,None)

    def test_getChild__match_and_after(self):
        e = self.modeled._getChild(after=(None,"d"),match=(None,"e"))
        self.assert_(e)
        self.assertEqual(e.localName,"e")
        e = self.modeled._getChild(after=(None,"d"),match=(None,"f"))
        self.assertEqual(e,None)

    def test_getChild__before_match_and_after(self):
        e = self.modeled._getChild(after=(None,"d"),
                                   match=(None,"e"),
                                   before=(None,"f"))
        self.assert_(e)
        self.assertEqual(e.localName,"e")
        e = self.modeled._getChild(after=(None,"a"),
                                   match=(None,"e"),
                                   before=(None,"f"))
        self.assertEqual(e,None)

        e = self.modeled._getChild(after=(None,"c"),
                                   match=(None,"d"),
                                   before=(None,"f"))
        self.assertEqual(e,None)

    def test_getChild__multiple_match(self):
        e = self.modeled._getChild(after=(None,"c"),
                                   match=(None,"c"),
                                   before=(None,"c"))
        self.assert_(e)
        self.assertEqual(e.localName,"c")
        self.assertEqual(e.getAttribute("id"),"2")
        e = self.modeled._getChild((None,"c"))
        self.assert_(e)
        self.assertEqual(e.localName,"c")
        self.assertEqual(e.getAttribute("id"),"1")
        elt = e
        e = self.modeled._getChild(after=elt)
        self.assert_(e)
        self.assertEqual(e.localName,"c")
        self.assertEqual(e.getAttribute("id"),"2")
        elt = e
        e = self.modeled._getChild(after=elt)
        self.assert_(e)
        self.assertEqual(e.localName,"c")
        self.assertEqual(e.getAttribute("id"),"3")

    def test_getChild__match_alone__qname_ns(self):
        e = self.modeled_w_ns._getChild((self.fooNS,"b"))
        self.assert_(e)
        self.assertEqual(e.localName,"b")
        e = self.modeled_w_ns._getChild((self.fooNS,"d"))
        self.assertEqual(e,None)
        e = self.modeled_w_ns._getChild((self.fooNS+"bar/","b"))
        self.assertEqual(e,None)



if __name__ == "__main__":
    testsuite = unittest.defaultTestLoader.loadTestsFromTestCase(ModeledTestCase)
    testrunner = unittest.TextTestRunner()
    testrunner.run(testsuite)
