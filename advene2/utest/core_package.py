from os import rmdir, unlink
from os.path import join
from tempfile import mkdtemp
from unittest import TestCase, main
from urllib import pathname2url

from advene.model.consts import DC_NS_PREFIX
from advene.model.core.package import Package
from advene.model.backends.sqlite import _set_module_debug

_set_module_debug(True) # enable all asserts in backend_sqlite


class TestCreation(TestCase):
    # TODO this is not complete

    def test_create_transient(self):
        # use invalid URL scheme to force the package to be transient
        p = Package("x-invalid-scheme:xyz", create=True)
        p.close()
        # if the second times works (with create=True), then transient works
        p = Package("x-invalid-scheme:xyz", create=True)
        p.close()


class TestImports(TestCase):
    def setUp(self):
        self.dirname = mkdtemp()
        self.db = join(self.dirname, "db")
        self.url = "sqlite:%s" % pathname2url(self.db)
        self.p1 = Package(self.url+";p1", create=True)
        self.p2 = Package(self.url+";p2", create=True)
        self.p3 = Package(self.url+";p3", create=True)
        self.p4 = Package(self.url+";p4", create=True)

        self.d1 = frozenset(((self.p1._backend, self.p1._id),))
        self.d2 = frozenset(((self.p2._backend, self.p2._id),))
        self.d3 = frozenset(((self.p3._backend, self.p3._id),))
        self.d4 = frozenset(((self.p4._backend, self.p4._id),))

    def _dependencies(self, p):
        return frozenset(
            (be, pid) for be, pdict in p._backends_dict.items()
                      for pid in pdict
        )

    def test_dependancies(self):
        p1, p2, p3, p4 = self.p1, self.p2, self.p3, self.p4
        d1, d2, d3, d4 = self.d1, self.d2, self.d3, self.d4
        dall = d1.union(d2).union(d3).union(d4)
        _dependencies = self._dependencies

        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2, _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p2.create_import("p4", self.p4)
        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1.create_import("p2", self.p2)
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p3.create_import("p4", self.p4)
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1.create_import("p3", self.p3)
        self.assertEqual(dall, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p4.create_import("p1", self.p1)
        self.assertEqual(dall, _dependencies(p1))
        self.assertEqual(dall, _dependencies(p2))
        self.assertEqual(dall, _dependencies(p3))
        self.assertEqual(dall, _dependencies(p4))

        self.p4["p1"].delete()
        self.assertEqual(dall, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1["p3"].delete()
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p3["p4"].delete()
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1["p2"].delete()
        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p2["p4"].delete()
        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2, _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

    def test_close_unimported(self):
        self.p1.create_import("p2", self.p2)
        self.p1.close()
        self.assert_(self.p1.closed)
        self.assert_(not self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_simply_imported(self):
        self.p1.create_import("p2", self.p2)
        self.assertRaises(ValueError, self.p2.close)
        self.assert_(not self.p1.closed)
        self.assert_(not self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_cycle(self):
        self.p1.create_import("p2", self.p2)
        self.p2.create_import("p1", self.p1)
        self.p1.create_import("p3", self.p3)
        self.p2.create_import("p4", self.p4)
        self.p1.close()
        self.assert_(self.p1.closed)
        self.assert_(self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_imported_cycle(self):
        self.p1.create_import("p2", self.p2)
        self.p2.create_import("p1", self.p1)
        self.p3.create_import("p1", self.p1)
        self.assertRaises(ValueError, self.p1.close)
        self.assert_(not self.p1.closed)
        self.assert_(not self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_multiple_cycles(self):
        self.p1.create_import("p2", self.p2)
        self.p1.create_import("p3", self.p3)
        self.p2.create_import("p4", self.p4)
        self.p3.create_import("p4", self.p4)
        self.p4.create_import("p1", self.p1)
        self.p2.close()
        self.assert_(self.p1.closed)
        self.assert_(self.p2.closed)
        self.assert_(self.p3.closed)
        self.assert_(self.p4.closed)

    def tearDown(self):
        try:
            if self.p1 and not self.p1.closed: self.p1.close()
            if self.p2 and not self.p2.closed: self.p2.close()
            if self.p3 and not self.p3.closed: self.p3.close()
            if self.p4 and not self.p4.closed: self.p4.close()
        except ValueError:
            pass
        unlink(self.db)
        rmdir(self.dirname)


class TestEvents(TestCase):
    def setUp(self):
        self.dirname = mkdtemp()
        self.db = join(self.dirname, "db")
        self.url = "sqlite:%s" % pathname2url(self.db)
        self.p1 = Package(self.url+";p1", create=True)
        self.p2 = Package(self.url+";p2", create=True)
        self.p3 = Package(self.url+";p3", create=True)
        self.buf = []
        self.callback_errors = []

    def tearDown(self):
        try:
            if self.p1 and not self.p1.closed: self.p1.close()
            if self.p2 and not self.p2.closed: self.p2.close()
            if self.p3 and not self.p3.closed: self.p3.close()
        except ValueError:
            pass
        unlink(self.db)
        rmdir(self.dirname)

    def default_handler(self, *args):
        self.buf.append(args)

    def attr_handler(self, obj, attr, val, pre=None):
        actual_val = getattr(obj, attr)
        if pre:
            if actual_val == val:
                self.callback_errors.append("%s should not be %r yet" %
                                            (attr, val))
        else:
            if actual_val != val:
                self.callback_errors.append("%s = %r, should be %r" %
                                            (attr, actual_val, val))
        self.default_handler(obj, attr, val)

    def meta_handler(self, obj, key, val, pre=None):
        actual_val = obj.get_meta(key, None)
        if pre:
            if actual_val == val:
                self.callback_errors.append("%s should not be %r yet" %
                                            (key, val))
        else:
            if actual_val != val:
                self.callback_errors.append("%s : %r, should be %r" %
                                            (key, actual_val, val))
        self.default_handler(obj, key, val)

    def elt_handler(self, pkg, elt, signal, params):
        self.default_handler(pkg, elt, signal, params)

    def test_create_media(self):
        hid = self.p1.connect("created::media", self.default_handler)
        m = self.p2.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        a = self.p2.create_annotation("a", m, 10, 20, "text/plain")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [(self.p1, m,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        m = self.p1.create_media("m2", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])

    def test_create_annotation(self):
        hid = self.p1.connect("created::annotation", self.default_handler)
        m = self.p2.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        a = self.p2.create_annotation("a", m, 10, 20, "text/plain")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        a = self.p1.create_annotation("a", m, 10, 20, "text/plain")
        self.assertEqual(self.buf, [(self.p1, a,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        a = self.p1.create_annotation("a2", m, 10, 20, "text/plain")
        self.assertEqual(self.buf, [])

    def test_create_relation(self):
        hid = self.p1.connect("created::relation", self.default_handler)
        r = self.p2.create_relation("r")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        r = self.p1.create_relation("r")
        self.assertEqual(self.buf, [(self.p1, r,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        r = self.p1.create_relation("r2")
        self.assertEqual(self.buf, [])

    def test_create_list(self):
        hid = self.p1.connect("created::list", self.default_handler)
        L = self.p2.create_list("L")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        L = self.p1.create_list("L")
        self.assertEqual(self.buf, [(self.p1, L,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        r = self.p1.create_relation("L2")
        self.assertEqual(self.buf, [])

    def test_create_tag(self):
        hid = self.p1.connect("created::tag", self.default_handler)
        t = self.p2.create_tag("t")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        t = self.p1.create_tag("t")
        self.assertEqual(self.buf, [(self.p1, t,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        t = self.p1.create_tag("t2")
        self.assertEqual(self.buf, [])

    def test_create_query(self):
        hid = self.p1.connect("created::query", self.default_handler)
        q = self.p2.create_query("q", "text/plain")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        q = self.p1.create_query("q", "text/plain")
        self.assertEqual(self.buf, [(self.p1, q,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        q = self.p1.create_query("q2", "text/plain")
        self.assertEqual(self.buf, [])

    def test_create_view(self):
        hid = self.p1.connect("created::view", self.default_handler)
        v = self.p2.create_view("v", "text/plain")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        v = self.p1.create_view("v", "text/plain")
        self.assertEqual(self.buf, [(self.p1, v,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        v = self.p1.create_view("v2", "text/plain")
        self.assertEqual(self.buf, [])

    def test_create_resource(self):
        hid = self.p1.connect("created::resource", self.default_handler)
        r = self.p2.create_resource("r", "text/plain")
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        r = self.p1.create_resource("r", "text/plain")
        self.assertEqual(self.buf, [(self.p1, r,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        r = self.p1.create_resource("r2", "text/plain")
        self.assertEqual(self.buf, [])

    def test_create_import(self):
        hid = self.p1.connect("created::import", self.default_handler)
        i = self.p2.create_import("i", self.p1)
        self.assertEqual(self.buf, [])
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        i = self.p1.create_import("i", self.p2)
        self.assertEqual(self.buf, [(self.p1, i,),])
        del self.buf[:]
        self.p1.disconnect(hid)
        i = self.p1.create_import("i2", self.p3)
        self.assertEqual(self.buf, [])

    def test_create_any(self):
        self.p1.connect("created", self.default_handler)
        m = self.p2.create_media("m", "file:/tmp/foo.avi")
        self.assertEqual(self.buf, [])
        a = self.p2.create_annotation("a", m, 10, 20, "text/plain")
        self.assertEqual(self.buf, [])
        r = self.p2.create_relation("r")
        self.assertEqual(self.buf, [])
        L = self.p2.create_list("L")
        self.assertEqual(self.buf, [])
        t = self.p2.create_tag("t")
        self.assertEqual(self.buf, [])
        q = self.p2.create_query("q", "text/plain")
        self.assertEqual(self.buf, [])
        v = self.p2.create_view("v", "text/plain")
        self.assertEqual(self.buf, [])
        R = self.p2.create_resource("R", "text/plain")
        self.assertEqual(self.buf, [])
        i = self.p2.create_import("i", self.p1)
        self.assertEqual(self.buf, [])

        ref = []
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        ref += [(self.p1, m),]
        self.assertEqual(self.buf, ref)
        a = self.p1.create_annotation("a", m, 10, 20, "text/plain")
        ref += [(self.p1, a),]
        self.assertEqual(self.buf, ref)
        r = self.p1.create_relation("r")
        ref += [(self.p1, r),]
        self.assertEqual(self.buf, ref)
        L = self.p1.create_list("L")
        ref += [(self.p1, L),]
        self.assertEqual(self.buf, ref)
        t = self.p1.create_tag("t")
        ref += [(self.p1, t),]
        self.assertEqual(self.buf, ref)
        q = self.p1.create_query("q", "text/plain")
        ref += [(self.p1, q),]
        self.assertEqual(self.buf, ref)
        v = self.p1.create_view("v", "text/plain")
        ref += [(self.p1, v),]
        self.assertEqual(self.buf, ref)
        R = self.p1.create_resource("R", "text/plain")
        ref += [(self.p1, R),]
        self.assertEqual(self.buf, ref)
        i = self.p1.create_import("i", self.p2)
        ref += [(self.p1, i),]
        self.assertEqual(self.buf, ref)

    def test_closed(self):
        self.p1.connect("closed", self.default_handler)
        self.p2.close()
        self.assertEqual(self.buf, [])
        ref = [(self.p1, self.p1.url, self.p1.uri)]
        self.p1.close()
        self.assertEqual(self.buf, ref)

    def test_closed_disconnected(self):
        hid = self.p1.connect("closed", self.default_handler)
        self.p1.disconnect(hid)
        self.p1.close()
        self.assertEqual(self.buf, [])

    def test_changed_uri(self):
        hid1 = self.p1.connect("changed::uri", self.attr_handler)
        hid2 = self.p1.connect("pre-changed::uri", self.attr_handler, "pre")
        self.p2.uri = "urn:12345"
        self.assertEqual(self.buf, [])
        self.p1.uri = "urn:67890"
        self.assertEqual(self.buf, [(self.p1, "uri", "urn:67890"),]*2)
        self.assertEqual(self.callback_errors, [])
        del self.buf[:]
        self.p1.disconnect(hid1)
        self.p1.disconnect(hid2)
        self.p1.uri = "urn:abcdef"
        self.assertEqual(self.buf, [])

    def test_changed_any(self):
        hid1 = self.p1.connect("changed", self.attr_handler)
        hid2 = self.p1.connect("pre-changed", self.attr_handler, "pre")
        self.p2.uri = "urn:12345"
        self.assertEqual(self.buf, [])
        self.p1.uri = "urn:67890"
        self.assertEqual(self.buf, [(self.p1, "uri", "urn:67890"),]*2)
        self.assertEqual(self.callback_errors, [])
        del self.buf[:]
        self.p1.disconnect(hid1)
        self.p1.disconnect(hid2)
        self.p1.uri = "urn:abcdef"
        self.assertEqual(self.buf, [])

    def test_changed_meta(self):
        k = DC_NS_PREFIX + "creator"
        k2 = DC_NS_PREFIX + "title"
        hid1 = self.p1.connect("changed-meta::" + k, self.meta_handler)
        hid2 = self.p1.connect("pre-changed-meta::" + k, self.meta_handler, 1)
        self.p1.set_meta(k2, "hello world")
        self.assertEqual(self.buf, [])
        self.p2.set_meta(k, "pchampin")
        self.assertEqual(self.buf, [])
        self.p1.set_meta(k, "pchampin")
        self.assertEqual(self.buf, [(self.p1, k, "pchampin"),]*2)
        self.assertEqual(self.callback_errors, [])
        del self.buf[:]
        self.p1.del_meta(k2)
        self.assertEqual(self.buf, [])
        self.p2.del_meta(k)
        self.assertEqual(self.buf, [])
        self.p1.del_meta(k)
        self.assertEqual(self.buf, [(self.p1, k, None)]*2)
        self.assertEqual(self.callback_errors, [])
        del self.buf[:]
        self.p1.disconnect(hid1)
        self.p1.disconnect(hid2)
        self.p1.set_meta(k, "oaubert")
        self.assertEqual(self.buf, [])

    def test_changed_meta_any(self):
        k = DC_NS_PREFIX + "creator"
        hid1 = self.p1.connect("changed-meta", self.meta_handler)
        hid2 = self.p1.connect("pre-changed-meta", self.meta_handler, "pre")
        self.p2.set_meta(k, "pchampin")
        self.assertEqual(self.buf, [])
        self.p1.set_meta(k, "pchampin")
        self.assertEqual(self.buf, [(self.p1, k, "pchampin"),]*2)
        self.assertEqual(self.callback_errors, [])
        del self.buf[:]
        self.p2.del_meta(k)
        self.assertEqual(self.buf, [])
        self.p1.del_meta(k)
        self.assertEqual(self.buf, [(self.p1, k, None)]*2)
        self.assertEqual(self.callback_errors, [])
        del self.buf[:]
        self.p1.disconnect(hid1)
        self.p1.disconnect(hid2)
        self.p1.set_meta(k, "oaubert")
        self.assertEqual(self.buf, [])

    def test_modify_media(self):
        k = DC_NS_PREFIX + "creator"
        hid = self.p1.connect("media::changed", self.elt_handler)
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        m2 = self.p2.create_media("m", "file:/tmp/foo.avi")
        a = self.p1.create_annotation("a", m, 10, 20, "text/plain")
        self.assertEqual(self.buf, [])
        def do_changes(_=[1]):
            i = _[0] = _[0] + 1
            m.url = "file:/tmp/foo%s.avi" % i
            m2.url = "file:/tmp/foo%s.avi" % i
            m.set_meta(k, "creator%s" % i)
            a.end = 100 + i
            a.set_meta(k, "creator%s" % i)

        do_changes()
        self.assertEqual(self.buf, [(self.p1, m, "changed", ("url", m.url,)),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("media::pre-changed", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
                         [(self.p1, m, "pre-changed", ("url", m.url,)),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("media::changed-meta", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
                         [(self.p1, m, "changed-meta", (k, m.get_meta(k))),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("media::pre-changed-meta", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
            [(self.p1, m, "pre-changed-meta", (k, m.get_meta(k))),])
        del self.buf[:]
        self.p1.disconnect(hid)

        do_changes()
        self.assertEqual(self.buf, [])

    def test_modify_annotation(self):
        k = DC_NS_PREFIX + "creator"
        hid = self.p1.connect("annotation::changed", self.elt_handler)
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        m2 = self.p2.create_media("m", "file:/tmp/foo.avi")
        a = self.p1.create_annotation("a", m, 10, 20, "text/plain")
        a2 = self.p2.create_annotation("a", m2, 10, 20, "text/plain")
        self.assertEqual(self.buf, [])
        def do_changes(_=[1]):
            i = _[0] = _[0] + 1
            m.url = "file:/tmp/foo%s.avi" % i
            m2.url = "file:/tmp/foo%s.avi" % i
            m.set_meta(k, "creator%s" % i)
            a.end = 100 + i
            a.set_meta(k, "creator%s" % i)

        do_changes()
        self.assertEqual(self.buf, [(self.p1, a, "changed", ("end", a.end,)),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("annotation::pre-changed", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
                         [(self.p1, a, "pre-changed", ("end", a.end,)),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("annotation::changed-meta", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
                         [(self.p1, a, "changed-meta", (k, a.get_meta(k))),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("annotation::pre-changed-meta", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
            [(self.p1, a, "pre-changed-meta", (k, a.get_meta(k))),])
        del self.buf[:]
        self.p1.disconnect(hid)

        do_changes()
        self.assertEqual(self.buf, [])

    def test_modify_relation(self):
        assert(False) # TODO
        k = DC_NS_PREFIX + "creator"
        hid = self.p1.connect("annotation::changed", self.elt_handler)
        m = self.p1.create_media("m", "file:/tmp/foo.avi")
        m2 = self.p2.create_media("m", "file:/tmp/foo.avi")
        a = self.p1.create_annotation("a", m, 10, 20, "text/plain")
        a2 = self.p2.create_annotation("a", m2, 10, 20, "text/plain")
        self.assertEqual(self.buf, [])
        def do_changes(_=[1]):
            i = _[0] = _[0] + 1
            m.url = "file:/tmp/foo%s.avi" % i
            m2.url = "file:/tmp/foo%s.avi" % i
            m.set_meta(k, "creator%s" % i)
            a.end = 100 + i
            a.set_meta(k, "creator%s" % i)

        do_changes()
        self.assertEqual(self.buf, [(self.p1, a, "changed", ("end", a.end,)),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("annotation::pre-changed", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
                         [(self.p1, a, "pre-changed", ("end", a.end,)),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("annotation::changed-meta", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
                         [(self.p1, a, "changed-meta", (k, a.get_meta(k))),])
        del self.buf[:]
        self.p1.disconnect(hid)

        hid = self.p1.connect("annotation::pre-changed-meta", self.elt_handler)
        do_changes()
        self.assertEqual(self.buf,
            [(self.p1, a, "pre-changed-meta", (k, a.get_meta(k))),])
        del self.buf[:]
        self.p1.disconnect(hid)

        do_changes()
        self.assertEqual(self.buf, [])


    # TODO other element types

if __name__ == "__main__":
    main()

