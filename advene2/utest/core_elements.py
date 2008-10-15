import gc
from os import tmpnam, unlink
from os.path import abspath, split
from urllib import pathname2url
from unittest import TestCase, main
from warnings  import filterwarnings

from advene.model.backends.sqlite import _set_module_debug
from advene.model.core.content import PACKAGED_ROOT
from advene.model.core.media import FOREF_PREFIX
from advene.model.core.package import Package, UnreachableImportError, \
                                      NoSuchElementError

filterwarnings("ignore", "tmpnam is a potential security risk to your program")
_set_module_debug(True) # enable all asserts in backend_sqlite

dc_creator = "http://purl.org/dc/elements/1.1/creator"
dc_description = "http://purl.org/dc/elements/1.1/description"
rdfs_seeAlso = "http://www.w3.org/1999/02/22-rdf-syntax-ns#seeAlso"

class TestElements(TestCase):
    def setUp(self):
        self.p = Package("sqlite::memory:", create=True, _transient=True)
        self.foref = "http://advene.liris.cnrs.fr/ns/frame_of_reference/ms;o=0"
        self.p.create_media("m1", "http://example.com/m1.avi", self.foref)

        self.q = Package("sqlite::memory:;foo", create=True, _transient=True)

    def tearDown(self):
        self.q.close()
        self.p.close()

    # utility methodes for mixins and common behaviours

    def _test_with_content(self, e):
        # content related attributes
        self.assertEqual("text/plain", e.content_mimetype)
        self.assertEqual("text/plain", e.content.mimetype)
        self.assertEqual("", e.content_url)
        self.assertEqual("", e.content.url)
        self.assertEqual("", e.content_data)
        self.assertEqual("", e.content.data)
        e.content_mimetype = "text/html"
        self.assertEqual("text/html", e.content_mimetype)
        self.assertEqual("text/html", e.content.mimetype)
        e.content.mimetype = "text/plain"
        self.assertEqual("text/plain", e.content_mimetype)
        self.assertEqual("text/plain", e.content.mimetype)
        e.content_data = "listen carefuly"
        self.assertEqual("listen carefuly", e.content_data)
        self.assertEqual("listen carefuly", e.content.data)
        e.content.data = "I shall say this only once"
        self.assertEqual("I shall say this only once", e.content_data)
        self.assertEqual("I shall say this only once", e.content.data)

        # external content (url)
        url = "file:" + pathname2url(__file__)
        e.content_url = url
        f = open(__file__); lines = f.read(); f.close()
        self.assertEqual(url, e.content_url)
        self.assertEqual(url, e.content.url)
        self.assertEqual(lines, e.content_data)
        self.assertEqual(lines, e.content.data)

        f = e.content_as_file 
        self.assertEqual(lines, f.read())
        f.close()

        f = e.content.as_file 
        self.assertEqual(lines, f.read())
        f.close()

        # backend-stored content (cancels url)
        e.content_data = "good moaning"
        self.assertEqual("", e.content_url)
        self.assertEqual("", e.content.url)

        f = e.content_as_file
        self.assertEqual("good moaning", f.read())
        f.seek(0)
        f.truncate()
        f.write("hello chaps")
        f.seek(0)
        self.assertEqual("hello chaps", f.read())
        pos = f.tell()
        self.assertEqual("hello chaps", e.content_data)
        self.assertEqual("hello chaps", e.content.data)
        self.assertEqual(pos, f.tell())
        self.assertRaises(IOError, setattr, e, "content_data", "foo")
        self.assertRaises(IOError, setattr, e.content, "data", "foo")
        self.assertRaises(IOError, getattr, e, "content_as_file")
        self.assertRaises(IOError, getattr, e.content, "as_file")
        f.close()

        # package-stored content (backend sees URL, users sees internal)
        filename = tmpnam()
        base, file  = split(filename)
        base_url = "file:" + pathname2url(base)
        file_url = "packaged:/" + pathname2url(file)
        f = open(filename, "w")
        f.write("packaged data")
        f.close()
        e._owner.set_meta(PACKAGED_ROOT, base_url)
        e.content_url = file_url
        self.assertEqual("packaged data", e.content_data)
        self.assertEqual("packaged data", e.content.data)
        e.content_data = "still packaged data"

        f = open(filename, "r")
        self.assertEqual("still packaged data", f.read())
        f.close()

        f = e.content_as_file
        self.assertEqual("still packaged data", f.read())
        f.seek(0)
        f.truncate()
        f.write("hello chaps")
        f.seek(0)
        self.assertEqual("hello chaps", f.read())
        pos = f.tell()
        self.assertEqual("hello chaps", e.content_data)
        self.assertEqual("hello chaps", e.content.data)
        self.assertEqual(pos, f.tell())
        self.assertRaises(IOError, setattr, e, "content_data", "foo")
        self.assertRaises(IOError, setattr, e.content, "data", "foo")
        self.assertRaises(IOError, getattr, e, "content_as_file")
        self.assertRaises(IOError, getattr, e.content, "as_file")
        f.close()

        # schema
        self.assertEqual(None, e.content_schema)
        self.assertEqual(None, e.content.schema)
        self.assertEqual(None, e.content_schema_idref)
        self.assertEqual(None, e.content.schema_idref)
        s = e._owner.create_resource("myschema", "test/plain")
        e.content_schema = s
        self.assertEqual(s, e.content_schema)
        self.assertEqual(s, e.content.schema)
        self.assertEqual("myschema", e.content_schema_idref)
        self.assertEqual("myschema", e.content.schema_idref)
        e.content_schema = None
        self.assertEqual(None, e.content_schema)
        self.assertEqual(None, e.content.schema)
        self.assertEqual(None, e.content_schema_idref)
        self.assertEqual(None, e.content.schema_idref)
        s.delete()

        unlink(filename)
        e.content_url = ""
        e._owner.del_meta(PACKAGED_ROOT)

    def _test_with_meta(self, e):

        def test_is_list():
            def has_idref(a): return hasattr(a, "ADVENE_TYPE")
            def idref(a): return has_idref(a) and a.id or a
            eq = self.assertEqual
            refid = [ (k, idref(v)) for k, v in ref ]
            refiid = [ (k, has_idref(v)) for k, v in ref ]
            def mapisid1(L): return [ i.is_idref for i in L ]
            def mapisid2(L): return [ (k, v.is_idref) for k, v in L ]

            eq(ref, list(e.iter_meta()))
            eq(ref, e.meta.items())
            eq(ref, list(e.meta.iteritems()))
            eq([k for k,v in ref], e.meta.keys())
            eq([k for k,v in ref], list(e.meta))
            eq([k for k,v in ref], list(e.meta.iterkeys()))
            eq([v for k,v in ref], e.meta.values())
            eq([v for k,v in ref], list(e.meta.itervalues()))

            eq(refid, list(e.iter_meta_idrefs()))
            eq(refid, e.meta.items_idrefs())
            eq(refid, list(e.meta.iteritems_idrefs()))
            eq([v for k,v in refid], e.meta.values_idrefs())
            eq([v for k,v in refid], list(e.meta.itervalues_idrefs()))

            eq(refiid, mapisid2(e.iter_meta_idrefs()))
            eq(refiid, mapisid2(e.meta.items_idrefs()))
            eq(refiid, mapisid2(e.meta.iteritems_idrefs()))
            eq([v for k,v in refiid], mapisid1(e.meta.values_idrefs()))
            eq([v for k,v in refiid], mapisid1(e.meta.itervalues_idrefs()))

        def test_has_item(k, v):
            self.assert_(e.meta.has_key(k))
            self.assertEqual(v, e.get_meta(k))
            self.assertEqual(v, e.get_meta(k))
            self.assertEqual(v, e.get_meta(k, None))
            self.assertEqual(v, e.meta[k])
            self.assertEqual(v, e.meta.get(k))
            self.assertEqual(v, e.meta.get(k, None))
            self.assertEqual(v, e.meta.pop(k)); e.meta[k] = v
            self.assertEqual(v, e.meta.pop(k, None)); e.meta[k] = v
            if hasattr(v, "ADVENE_TYPE"):
                idref = v.make_idref_in(self.p)
                self.assertEqual(idref, e.get_meta_idref(k))
                self.assertEqual(idref, e.get_meta_idref(k, "!"))
                self.assertEqual(idref, e.meta.get_idref(k))
                self.assertEqual(idref, e.meta.get_idref(k, "!"))
                self.assertEqual(idref, e.meta.pop_idref(k)); e.meta[k] = v
                self.assertEqual(idref, e.meta.pop_idref(k, "!")); e.meta[k]= v
                self.assert_(e.get_meta_idref(k).is_idref)
                self.assert_(e.meta.get_idref(k).is_idref)
                self.assert_(e.meta.pop_idref(k).is_idref); e.meta[k] = v
            else:
                self.assertEqual(v, e.get_meta_idref(k))
                self.assertEqual(v, e.get_meta_idref(k, "!"))
                self.assertEqual(v, e.meta.get_idref(k))
                self.assertEqual(v, e.meta.get_idref(k, "!"))
                self.assertEqual(v, e.meta.pop_idref(k)); e.meta[k] = v
                self.assertEqual(v, e.meta.pop_idref(k, "!")); e.meta[k] = v
                self.assert_(not e.get_meta_idref(k).is_idref)
                self.assert_(not e.meta.get_idref(k).is_idref)
                self.assert_(not e.meta.pop_idref(k).is_idref); e.meta[k] = v

        def test_has_not_item(k):
            self.assert_(not e.meta.has_key(k))
            self.assertRaises(KeyError, e.get_meta, k)
            self.assertRaises(KeyError, e.get_meta_idref, k)
            self.assertRaises(KeyError, e.meta.__getitem__, k)
            self.assertRaises(KeyError, e.meta.pop, k)
            self.assertRaises(KeyError, e.meta.pop_idref, k)
            self.assertEqual("!", e.get_meta(k, "!"))
            self.assertEqual("!", e.get_meta_idref(k, "!"))
            self.assertEqual(None, e.meta.get(k))
            self.assertEqual("!", e.meta.get(k, "!"))
            self.assertEqual("!", e.meta.get_idref(k, "!"))
            self.assertEqual("!", e.meta.pop(k, "!"))
            self.assertEqual("!", e.meta.pop_idref(k, "!"))

        info = self.p.create_resource("info", "text/html")
        ref = []
        random_items = [
            (dc_description, "bla bla bla"),
            (rdfs_seeAlso, info),
            (dc_creator, "pchampin"),
        ]

        test_is_list() # ref is empty

        for k, v in random_items:
            test_has_not_item(k)
            ref.append((k, v))
            ref.sort()
            e.set_meta(k, v)
            for k2, v2 in ref:
                test_has_item(k2, v2)
            test_is_list()

        for k, v in random_items:
            ref.remove((k,v))
            e.del_meta(k)
            for k2, v2 in ref:
                test_has_item(k2, v2)
            test_is_list()
            test_has_not_item(k)

        test_is_list() # ref is empty

        # TODO: not yet tested: some dict methods in meta

    def _test_list_like(self, L, a, name):
        # L is the list-like element to test
        # a is a list of 2O potential items for L
        p = self.p

        get_item = getattr(L, "get_%s" % name)
        get_idref = getattr(L, "get_%s_idref" % name)
        iter_items = getattr(L, "iter_%ss" % name)
        iter_idrefs = getattr(L, "iter_%ss_idrefs" % name)

        self.assertEqual([], list(L))
        self.assertEqual([], list(iter_items()))
        self.assertEqual([], list(iter_idrefs()))
        L.append(a[2])
        self.assertEqual([a[2],], list(L))
        self.assertEqual([a[2],], list(iter_items()))
        self.assertEqual([a[2].id,], list(iter_idrefs()))
        L.insert(0,a[1])
        self.assertEqual([a[1], a[2]], list(L))
        self.assertEqual([a[1], a[2]], list(iter_items()))
        self.assertEqual([a[1].id, a[2].id], list(iter_idrefs()))
        L.insert(2,a[4])
        self.assertEqual([a[1], a[2], a[4]], list(L))
        self.assertEqual([a[1], a[2], a[4]], list(iter_items()))
        self.assertEqual([a[1].id, a[2].id, a[4].id], list(iter_idrefs()))
        L.insert(100,a[5])
        self.assertEqual([a[1], a[2], a[4], a[5]], list(L))
        self.assertEqual([a[1], a[2], a[4], a[5]], list(iter_items()))
        self.assertEqual([a[1].id, a[2].id, a[4].id, a[5].id], 
                         list(iter_idrefs()))
        L.insert(-2,a[3])
        self.assertEqual(a[1:6], list(L))
        self.assertEqual(a[1:6], list(iter_items()))
        self.assertEqual([ i.id for i in a[1:6] ], list(iter_idrefs()))
        L.insert(-6,a[0])
        self.assertEqual(a[0:6], list(L))
        self.assertEqual(a[0:6], list(iter_items()))
        self.assertEqual([ i.id for i in a[0:6] ], list(iter_idrefs()))
        L.extend(a[6:9])
        self.assertEqual(a[0:9], list(L))
        self.assertEqual(a[0:9], list(iter_items()))
        self.assertEqual([ i.id for i in a[0:9] ], list(iter_idrefs()))

        for i in xrange(9):
            self.assertEqual(a[i], L[i])
            self.assertEqual(a[i], get_item(i))
            self.assertEqual(a[i].id, get_idref(i))
            L[i] = a[i+10]
            self.assertEqual(a[i+10], L[i])
            self.assertEqual(a[i+10], get_item(i))
            self.assertEqual(a[i+10].id, get_idref(i))

        del L[5]
        self.assertEqual(a[10:15]+a[16:19], list(L))
        self.assertEqual(a[10:15]+a[16:19], list(iter_items()))
        self.assertEqual([i.id for i in a[10:15]+a[16:19] ],
                         list(iter_idrefs()))
        L.insert(5,a[15])


        self.assertEqual(a[10:19], L[:])
        self.assertEqual(a[10:13], L[:3])
        self.assertEqual(a[12:19], L[2:])
        self.assertEqual(a[12:13], L[2:3])
        self.assertEqual(a[10:19:2], L[::2])
        self.assertEqual(a[15:11:-2], L[5:1:-2])

        b = L[:]

        L[2:4] = a[0:9]
        b[2:4] = a[0:9]
        self.assertEqual(b, list(L))
        self.assertEqual(b, list(iter_items()))
        self.assertEqual([ i.id for i in b ], list(iter_idrefs()))

        L[:] = a[0:10]
        b[:] = a[0:10]
        self.assertEqual(b, list(L))
        self.assertEqual(b, list(iter_items()))
        self.assertEqual([ i.id for i in b ], list(iter_idrefs()))

        L[9:0:-2] = a[19:10:-2]
        b[9:0:-2] = a[19:10:-2]
        self.assertEqual(b, list(L))
        self.assertEqual(b, list(iter_items()))
        self.assertEqual([ i.id for i in b ], list(iter_idrefs()))

        del L[0::2]
        del b[0::2]
        self.assertEqual(b, list(L))
        self.assertEqual(b, list(iter_items()))
        self.assertEqual([ i.id for i in b ], list(iter_idrefs()))

    def _test_with_tag(self, e):
        p = self.p
        t1 = p.create_tag("t1")
        t2 = p.create_tag("t2")
        t3 = p.create_tag("t3")
        tm = p.create_media("tm", "http://example.com/tm.avi", self.foref)
        ta1 = p.create_annotation("ta1", tm, 0, 10, "text/plain")
        ta2 = p.create_annotation("ta2", tm, 5, 15, "text/plain")
        p.associate_tag(tm, t1)
        p.associate_tag(tm, t2)
        p.associate_tag(ta1, t1)
        p.associate_tag(ta2, t2)
        p.associate_tag(e, t1)
        p.associate_tag(e, t3)

        def idrefs(elts, p):
            return frozenset( t.make_idref_in(p) for t in elts )       
        eq = self.assertEqual
 
        eq(frozenset((t1, t3)), frozenset(e.iter_tags(p)))
        eq(frozenset((t1, t2)), frozenset(tm.iter_tags(p)))
        eq(frozenset((t1,)), frozenset(ta1.iter_tags(p)))
        eq(frozenset((t2,)), frozenset(ta2.iter_tags(p)))
        eq(idrefs((t1, t3), p), frozenset(e.iter_tags_idrefs(p)))
        eq(idrefs((t1, t2), p), frozenset(tm.iter_tags_idrefs(p)))
        eq(idrefs((t1,), p), frozenset(ta1.iter_tags_idrefs(p)))
        eq(idrefs((t2,), p), frozenset(ta2.iter_tags_idrefs(p)))

        eq(frozenset((t1, t3)), frozenset(e.iter_tags(p, 0)))
        eq(frozenset((t1, t2)), frozenset(tm.iter_tags(p, 0)))
        eq(frozenset((t1,)), frozenset(ta1.iter_tags(p, 0)))
        eq(frozenset((t2,)), frozenset(ta2.iter_tags(p, 0)))
        eq(idrefs((t1, t3), p), frozenset(e.iter_tags_idrefs(p, 0)))
        eq(idrefs((t1, t2), p), frozenset(tm.iter_tags_idrefs(p, 0)))
        eq(idrefs((t1,), p), frozenset(ta1.iter_tags_idrefs(p, 0)))
        eq(idrefs((t2,), p), frozenset(ta2.iter_tags_idrefs(p, 0)))

        eq(frozenset((tm, ta1, e)), frozenset(t1.iter_elements(p)))
        eq(frozenset((tm, ta2)), frozenset(t2.iter_elements(p)))
        eq(frozenset((e,)), frozenset(t3.iter_elements(p)))
        eq(idrefs((tm, ta1, e), p), frozenset(t1.iter_elements_idrefs(p)))
        eq(idrefs((tm, ta2), p), frozenset(t2.iter_elements_idrefs(p)))
        eq(idrefs((e,), p), frozenset(t3.iter_elements_idrefs(p)))

        eq(frozenset((tm, ta1, e)), frozenset(t1.iter_elements(p, 0)))
        eq(frozenset((tm, ta2)), frozenset(t2.iter_elements(p, 0)))
        eq(frozenset((e,)), frozenset(t3.iter_elements(p, 0)))
        eq(idrefs((tm, ta1, e), p), frozenset(t1.iter_elements_idrefs(p, 0)))
        eq(idrefs((tm, ta2), p), frozenset(t2.iter_elements_idrefs(p, 0)))
        eq(idrefs((e,), p), frozenset(t3.iter_elements_idrefs(p, 0)))

        q = self.q
        q.create_import("i", self.p)
        q.associate_tag(tm, t3)
        q.associate_tag(ta1, t2)
        q.associate_tag(ta2, t1)
        q.associate_tag(e, t2)
        q.associate_tag(e, t3)

        eq(frozenset((t1, t2, t3)), frozenset(e.iter_tags(q)))
        eq(frozenset((t1, t2, t3)), frozenset(tm.iter_tags(q)))
        eq(frozenset((t1, t2)), frozenset(ta1.iter_tags(q)))
        eq(frozenset((t1, t2)), frozenset(ta2.iter_tags(q)))
        eq(idrefs((t1, t2, t3), q), frozenset(e.iter_tags_idrefs(q)))
        eq(idrefs((t1, t2, t3), q), frozenset(tm.iter_tags_idrefs(q)))
        eq(idrefs((t1, t2), q), frozenset(ta1.iter_tags_idrefs(q)))
        eq(idrefs((t1, t2), q), frozenset(ta2.iter_tags_idrefs(q)))

        eq(frozenset((t2, t3)), frozenset(e.iter_tags(q, 0)))
        eq(frozenset((t3,)), frozenset(tm.iter_tags(q, 0)))
        eq(frozenset((t2,)), frozenset(ta1.iter_tags(q, 0)))
        eq(frozenset((t1,)), frozenset(ta2.iter_tags(q, 0)))
        eq(idrefs((t2, t3), q), frozenset(e.iter_tags_idrefs(q, 0)))
        eq(idrefs((t3,), q), frozenset(tm.iter_tags_idrefs(q, 0)))
        eq(idrefs((t2,), q), frozenset(ta1.iter_tags_idrefs(q, 0)))
        eq(idrefs((t1,), q), frozenset(ta2.iter_tags_idrefs(q, 0)))
 
        eq(frozenset((t1, t3)), frozenset(e.iter_tags(p)))
        eq(frozenset((t1, t2)), frozenset(tm.iter_tags(p)))
        eq(frozenset((t1,)), frozenset(ta1.iter_tags(p)))
        eq(frozenset((t2,)), frozenset(ta2.iter_tags(p)))
        eq(idrefs((t1, t3), p), frozenset(e.iter_tags_idrefs(p)))
        eq(idrefs((t1, t2), p), frozenset(tm.iter_tags_idrefs(p)))
        eq(idrefs((t1,), p), frozenset(ta1.iter_tags_idrefs(p)))
        eq(idrefs((t2,), p), frozenset(ta2.iter_tags_idrefs(p)))

        eq(frozenset((tm, ta1, ta2, e)), frozenset(t1.iter_elements(q)))
        eq(frozenset((tm, ta1, ta2, e)), frozenset(t2.iter_elements(q)))
        eq(frozenset((tm, e)), frozenset(t3.iter_elements(q)))
        eq(idrefs((tm, ta1, ta2, e), q), frozenset(t1.iter_elements_idrefs(q)))
        eq(idrefs((tm, ta1, ta2, e), q), frozenset(t2.iter_elements_idrefs(q)))
        eq(idrefs((tm, e), q), frozenset(t3.iter_elements_idrefs(q)))

        eq(frozenset((ta2,)), frozenset(t1.iter_elements(q, 0)))
        eq(frozenset((ta1, e)), frozenset(t2.iter_elements(q, 0)))
        eq(frozenset((tm, e)), frozenset(t3.iter_elements(q, 0)))
        eq(idrefs((ta2,), q), frozenset(t1.iter_elements_idrefs(q, 0)))
        eq(idrefs((ta1, e), q), frozenset(t2.iter_elements_idrefs(q, 0)))
        eq(idrefs((tm, e), q), frozenset(t3.iter_elements_idrefs(q, 0)))

        eq(frozenset((tm, ta1, e)), frozenset(t1.iter_elements(p)))
        eq(frozenset((tm, ta2)), frozenset(t2.iter_elements(p)))
        eq(frozenset((e,)), frozenset(t3.iter_elements(p)))
        eq(idrefs((tm, ta1, e), p), frozenset(t1.iter_elements_idrefs(p)))
        eq(idrefs((tm, ta2), p), frozenset(t2.iter_elements_idrefs(p)))
        eq(idrefs((e,), p), frozenset(t3.iter_elements_idrefs(p)))

        eq(frozenset((p,)), frozenset(e.iter_taggers(t1, q)))
        eq(frozenset((p,)), frozenset(e.iter_taggers(t1, p)))
        eq(frozenset((p, q,)), frozenset(e.iter_taggers(t3, q)))
        eq(frozenset((p,)), frozenset(e.iter_taggers(t3, p)))

        self.assert_(e.has_tag(t1, q))
        self.assert_(not e.has_tag(t1, q, 0))
        self.assert_(e.has_tag(t1, p))
        self.assert_(e.has_tag(t1, p, 0))
        self.assert_(t1.has_element(e, q))
        self.assert_(not t1.has_element(e, q, 0))
        self.assert_(t1.has_element(e, p))
        self.assert_(t1.has_element(e, p, 0))
        self.assert_(e.has_tag(t3, q))
        self.assert_(e.has_tag(t3, q, 0))
        self.assert_(e.has_tag(t3, p))
        self.assert_(t3.has_element(e, q))
        self.assert_(t3.has_element(e, q, 0))
        self.assert_(t3.has_element(e, p))

        p.dissociate_tag(e, t3)
        eq(frozenset((t1, t2, t3)), frozenset(e.iter_tags(q)))
        eq(idrefs((t1, t2, t3), q), frozenset(e.iter_tags_idrefs(q)))
        eq(frozenset((t2, t3)), frozenset(e.iter_tags(q, 0)))
        eq(idrefs((t2, t3), q), frozenset(e.iter_tags_idrefs(q, 0)))
        eq(frozenset((t1,)), frozenset(e.iter_tags(p)))
        eq(idrefs((t1,), p), frozenset(e.iter_tags_idrefs(p)))
        eq(frozenset((tm, e)), frozenset(t3.iter_elements(q)))
        eq(idrefs((tm, e), q), frozenset(t3.iter_elements_idrefs(q)))
        eq(frozenset((tm, e)), frozenset(t3.iter_elements(q, 0)))
        eq(idrefs((tm, e), q), frozenset(t3.iter_elements_idrefs(q, 0)))
        eq(frozenset(()), frozenset(t3.iter_elements(p)))
        eq(idrefs((), p), frozenset(t3.iter_elements_idrefs(p)))
        eq(frozenset((q,)), frozenset(e.iter_taggers(t3, q)))
        eq(frozenset(), frozenset(e.iter_taggers(t3, p)))
        self.assert_(e.has_tag(t3, q))
        self.assert_(e.has_tag(t3, q, 0))
        self.assert_(not e.has_tag(t3, p))
        self.assert_(t3.has_element(e, q))
        self.assert_(t3.has_element(e, q, 0))
        self.assert_(not t3.has_element(e, p))

        q.dissociate_tag(e, t3)
        eq(frozenset((t1, t2)), frozenset(e.iter_tags(q)))
        eq(idrefs((t1, t2), q), frozenset(e.iter_tags_idrefs(q)))
        eq(frozenset((t2,)), frozenset(e.iter_tags(q, 0)))
        eq(idrefs((t2,), q), frozenset(e.iter_tags_idrefs(q, 0)))
        eq(frozenset((t1,)), frozenset(e.iter_tags(p)))
        eq(idrefs((t1,), p), frozenset(e.iter_tags_idrefs(p)))
        eq(frozenset((tm,)), frozenset(t3.iter_elements(q)))
        eq(idrefs((tm,), q), frozenset(t3.iter_elements_idrefs(q)))
        eq(frozenset((tm,)), frozenset(t3.iter_elements(q, 0)))
        eq(idrefs((tm,), q), frozenset(t3.iter_elements_idrefs(q, 0)))
        eq(frozenset(()), frozenset(t3.iter_elements(p)))
        eq(idrefs((), p), frozenset(t3.iter_elements_idrefs(p)))
        eq(frozenset(), frozenset(e.iter_taggers(t3, q)))
        eq(frozenset(), frozenset(e.iter_taggers(t3, p)))
        self.assert_(not e.has_tag(t3, q))
        self.assert_(not e.has_tag(t3, q, 0))
        self.assert_(not e.has_tag(t3, p))
        self.assert_(not t3.has_element(e, q))
        self.assert_(not t3.has_element(e, q, 0))
        self.assert_(not t3.has_element(e, p))

    # actual test methods

    def test_package_meta(self):
        p = self.p
        self._test_with_meta(p)

    def test_annotation(self):
        p = self.p
        m = p["m1"]
        a = p.create_annotation("a1", m, 10, 25, "text/plain")
        self.assertEqual( m, a.media)
        self.assertEqual(10, a.begin)
        self.assertEqual(25, a.end)
        self.assertEqual(15, a.duration)
        a.begin += 5
        self.assertEqual(15, a.begin)
        self.assertEqual(25, a.end)
        a.end += 10
        self.assertEqual(15, a.begin)
        self.assertEqual(35, a.end)
        a.duration += 5
        self.assertEqual(15, a.begin)
        self.assertEqual(40, a.end)
        m2 = p.create_media("m2", "http://example.com/m2.avi", self.foref)
        a.media = m2
        self.assertEqual(m2, a.media)
        self._test_with_content(a)
        self._test_with_meta(a)
        self._test_with_tag(a)

    def test_relation(self):
        p = self.p
        m = p["m1"]
        a = [ p.create_annotation("a%s" % i, m, i*10, i*10+19, "text/plain")
              for i in xrange(20) ]

        r = p.create_relation("r1", "text/plain")
        self._test_list_like(r, a, "member")
        self._test_with_content(r)
        self._test_with_meta(r)
        self._test_with_tag(r)

        r2 = p.create_relation("r2", "text/plain", members=a)
        self.assertEqual(a, list(r2))

    def test_list(self):
        p = self.p
        a = [ p.create_relation("r%s" % i, "text/plain") for i in xrange(10) ] \
          + [ p.create_list("x%s" % i) for i in xrange(10) ]

        L = p.create_list("l1")
        self._test_list_like(L, a, "item")
        self._test_with_meta(L)
        self._test_with_tag(L)

        L2 = p.create_list("l2", items=a)
        self.assertEquals(a, list(L2))


class TestUnreachable(TestCase):
    def setUp(self):
        self.filename = tmpnam()
        self.url1 = "sqlite:" + pathname2url(self.filename)
        self.url2 = self.url1 + ";foo"
        self.url3 = self.url2 + ";bar"

        p1 = Package(self.url1, create=True)
        p2 = Package(self.url2, create=True)
        i = p1.create_import("p2", p2)
        m = p2.create_media("m", "http://example.com/m.avi",
                            FOREF_PREFIX+"ms;o=0")
        s = p2.create_resource("schema", "text/plain")
        d = p1.create_resource("desc", "text/plain")
        a2 = p2.create_annotation("a2", m, 0, 10, "text/plain")
        a1 = p1.create_annotation("a1", m, 0, 10, "text/plain", schema=s)
        r = p1.create_relation("r", "text/plain", members=[a1, a2,])
        l = p1.create_list("l", items=[a1, s])
        t1 = p1.create_tag("t1")
        t2 = p2.create_tag("t2")
        p1.associate_tag(a1, t1)
        p1.associate_tag(a1, t2)
        p1.associate_tag(a2, t1)
        p1.associate_tag(a2, t2)
        p1.set_meta(dc_description, d)
        p1.set_meta(rdfs_seeAlso, m)
        p1.set_meta(dc_creator, "pchampin")
        p1.close()
        p2.close()

        p3 = Package(self.url3, create=True)
        p3.close()

    def tearDown(self):
        unlink(self.filename)

    def make_import_unreachable(self):
        p1 = Package(self.url1)
        p1["p2"].url = "x-unknown-scheme:abc"
        p1.close()

    def make_elements_inexistant(self):
        p1 = Package(self.url1)
        p1["p2"].url = self.url3
        p1.close()

    def _make_both_tests(f):
        def both_tests(self, f=f):
            self.make_import_unreachable()
            f(self, UnreachableImportError)
            self.make_elements_inexistant()
            f(self, NoSuchElementError)
        return both_tests

    @_make_both_tests
    def test_schema(self, exception_type):
        p1 = Package(self.url1)
        self.assertEquals("p2:schema", p1["a1"].content_schema_idref)
        self.assertRaises(exception_type,
                          getattr, p1["a1"], "content_schema")
        self.assertEquals(None, p1["a1"].get_content_schema(None))
        p1.close()

    @_make_both_tests
    def test_media(self, exception_type):
        p1 = Package(self.url1)
        self.assertEquals("p2:m", p1["a1"].media_idref)
        self.assertRaises(exception_type,
                          getattr, p1["a1"], "media")
        self.assertEquals(None, p1["a1"].get_media(None))
        p1.close()

    @_make_both_tests
    def test_member(self, exception_type):
        p1 = Package(self.url1)
        r = p1["r"]
        a1 = p1["a1"]
        self.assertEquals("p2:a2", r.get_member_idref(1))
        self.assertRaises(exception_type, r.__getitem__, 1)
        self.assertEquals(None, r.get_member(1))
        iter(r).next() # no exception before the actual yield
        self.assertRaises(exception_type, list, iter(r))
        self.assertEquals([a1, "p2:a2",], list(r.iter_members()))
        self.assertEquals(["a1", "p2:a2",], list(r.iter_members_idrefs()))
        p1.close()

    @_make_both_tests
    def test_item(self, exception_type):
        p1 = Package(self.url1)
        L = p1["l"]
        a1 = p1["a1"]
        self.assertEquals("p2:schema", L.get_item_idref(1))
        self.assertRaises(exception_type, L.__getitem__, 1)
        self.assertEquals(None, L.get_item(1))
        iter(L).next() # no exception before the actual yield
        self.assertRaises(exception_type, list, iter(L))
        self.assertEquals([a1, "p2:schema",], list(L.iter_items()))
        self.assertEquals(["a1", "p2:schema",], list(L.iter_items_idrefs()))
        p1.close()

    @_make_both_tests
    def test_meta(self, exception_type):
        p1 = Package(self.url1)
        self.assertEqual(None, p1.get_meta(rdfs_seeAlso, None))
        self.assertEqual("!", p1.get_meta(rdfs_seeAlso, "!"))
        self.assertEqual("p2:m", p1.get_meta_idref(rdfs_seeAlso, "!"))
        self.assertRaises(exception_type, p1.get_meta, rdfs_seeAlso)
        self.assertEqual(None, p1.meta.get(rdfs_seeAlso))
        self.assertEqual("!", p1.meta.get(rdfs_seeAlso, "!"))
        self.assertEqual("p2:m", p1.meta.get_idref(rdfs_seeAlso))
        self.assertEqual("p2:m", p1.meta.get_idref(rdfs_seeAlso, "!"))
        self.assertRaises(exception_type, p1.meta.__getitem__, rdfs_seeAlso)

        d = p1["desc"]
        ref = [(dc_creator, "pchampin"), (dc_description, "desc"),
               (rdfs_seeAlso, "p2:m"),]
        refiid = [False, True, True,]
        def mapiid1(L):
            return [ v.is_idref for v in L ]
        def mapiid2(L):
            return [ v.is_idref for k, v in L ]
        i = p1.iter_meta(); i.next(); i.next() # no raise before actual yield
        p1.meta.keys() # no exception when iterating over keys only
        list(p1.meta.iterkeys()) # no exception when iterating over keys only
        list(p1.meta) # no exception when iterating over keys only
        self.assertRaises(exception_type, list, p1.iter_meta())
        self.assertRaises(exception_type, list, p1.meta.iteritems())
        self.assertRaises(exception_type, list, p1.meta.itervalues())
        self.assertRaises(exception_type, p1.meta.items)
        self.assertRaises(exception_type, p1.meta.values)
        self.assertEqual(ref, list(p1.iter_meta_idrefs()))
        self.assertEqual(ref, list(p1.meta.iteritems_idrefs()))
        self.assertEqual(ref, p1.meta.items_idrefs())
        self.assertEqual([v for k,v in ref], list(p1.meta.itervalues_idrefs()))
        self.assertEqual([v for k,v in ref], p1.meta.values_idrefs())
        self.assertEqual(refiid, mapiid2(p1.meta.iteritems_idrefs()))
        self.assertEqual(refiid, mapiid2(p1.meta.items_idrefs()))
        self.assertEqual(refiid, mapiid1(p1.meta.itervalues_idrefs()))
        self.assertEqual(refiid, mapiid1(p1.meta.values_idrefs()))
        
        p1.close()

    @_make_both_tests
    def test_tag(self, exception_type):
        p1 = Package(self.url1)
        a1 = p1["a1"]
        t1 = p1["t1"]
        self.assertEquals(frozenset(("t1", "p2:t2")),
                                    frozenset(a1.iter_tags_idrefs(p1)))
        self.assertEquals(frozenset((t1, "p2:t2")),
            frozenset(a1.iter_tags(p1, yield_idrefs=True)))
        a1.iter_tags(p1).next() # no exception before the actual yield
        self.assertRaises(exception_type, list, a1.iter_tags(p1))
        self.assertEquals(frozenset(("a1", "p2:a2")),
                                    frozenset(t1.iter_elements_idrefs(p1)))
        self.assertEquals(frozenset((a1, "p2:a2")),
            frozenset(t1.iter_elements(p1, yield_idrefs=True)))
        t1.iter_elements(p1).next() # no exception before the actual yield
        self.assertRaises(exception_type, list, t1.iter_elements(p1))
        p1.close()

if __name__ == "__main__":
    main()

