from pysqlite2 import dbapi2 as sqlite
from os        import tmpnam, unlink
from os.path   import exists
from unittest  import TestCase, main
from warnings  import filterwarnings

from advene.model.backends.sqlite \
  import claims_for_create, create, claims_for_bind, bind, IN_MEMORY_URL, \
         PackageInUse
from advene.model.core.content import Content
from advene.model.core.element \
  import MEDIA, ANNOTATION, RELATION, VIEW, RESOURCE, TAG, LIST, QUERY, IMPORT

# the following may seem redundant, but we do not want the tests to be
# dependant on the actual values of the type constants
T = {
  "m": MEDIA,
  "a": ANNOTATION,
  "r": RELATION,
  "v": VIEW,
  "R": RESOURCE,
  "t": TAG,
  "l": LIST,
  "q": QUERY,
  "i": IMPORT,
}

filterwarnings("ignore", "tmpnam is a potential security risk to your program")

class P:
    """A dummy package class for testing purpose

    They emulate the required attributes, and are artificially kepts referenced
    to fool the WeakValueDict in _SqliteBackend.
    """
    _L = []
    def __init__ (self, url, readonly=False):
        self.url = url
        self.readonly = readonly
        P._L.append (self)


class TestCreateBackend(TestCase):
    def setUp(self):
        self.filename = tmpnam()
        self.url1 = "sqlite:%s" % self.filename
        self.url2 = "%s;foo" % self.url1

    def tearDown(self):
        if exists(self.filename):
            unlink(self.filename)
        del P._L[:] # not required, but saves memory

    def _touch_filename(self):
        cx = sqlite.connect(self.filename)
        cx.execute("create table a(b);")
        cx.close()

    def test_claim_wrong_scheme(self):
        self.assert_(
            not claims_for_create("http://example.com/advene/db")
        )

    def test_claim_wrong_path(self):
        self.assert_(
            not claims_for_create("%s/foo" % self.url1)
        )

    def test_claim_existing_file(self):
        self._touch_filename()
        self.assert_(
            not claims_for_create(self.url1)
        )

    def test_claim_new_file(self):
        self.assert_( 
            claims_for_create(self.url1)
        )

    def test_claim_new_file_with_fragment(self):
        self.assert_( 
            claims_for_create(self.url2)
        )

    def test_claim_existing_fragment(self):
        b, i = create(P(self.url2))
        self.assert_(
            not claims_for_create("%s;foo" % self.url1)
        )
        b.close(i)

    def test_claim_new_fragment(self):
        b, i = create(P(self.url2))
        self.assert_(
            claims_for_create("%s;bar" % self.url1)
        )
        b.close(i)

    def test_claim_memory(self):
        self.assert_( 
            claims_for_create(IN_MEMORY_URL)
        )

    def test_create_without_fragment(self):
        b, i = create(P(self.url1))
        self.assert_(
            claims_for_bind(self.url1)
        )
        b.close(i)

    def test_create_with_fragment(self):
        b, i = create(P(self.url2))
        self.assert_(
            claims_for_bind(self.url2)
        )
        b.close(i)

    def test_create_new_fragment(self):
        b, i = create(P(self.url1))
        create(P(self.url2))
        self.assert_(
            claims_for_bind(self.url2)
        )
        b.close(i)

    def test_create_in_memory(self):
        b,p = create(P(IN_MEMORY_URL))
        self.assert_(b._path, ":memory:")
        b.close(p)

    def test_create_with_other_url(self):
        b,p = create(P("http://example.com/a_package"), url=IN_MEMORY_URL)
        self.assert_(b._path, ":memory:")
        b.close(p)


class TestBindBackend(TestCase):
    def setUp(self):
        self.filename = tmpnam()
        self.url1 = "sqlite:%s" % self.filename
        self.url2 = "%s;foo" % self.url1
        self.b, self.i = create(P(self.url2))

    def tearDown(self):
        if exists(self.filename):
            unlink(self.filename)
        self.b.close (self.i)
        del P._L[:] # not required, but saves memory

    def test_claim_non_existing(self):
        unlink(self.filename)
        self.assert_(
            not claims_for_bind(self.url2)
        )

    def test_claim_wrong_format(self):
        self.b.close(self.i)
        f = open(self.filename, 'w'); f.write("foo"); f.close()
        self.assert_(
            not claims_for_bind(self.url2)
        )

    def test_claim_wrong_db_schema(self):
        unlink(self.filename)
        cx = sqlite.connect(self.filename)
        cx.execute("create table a(b);")
        cx.close()
        self.assert_(
            not claims_for_bind(self.url2)
        )

    def test_claim_wrong_backend_version(self):
        cx = sqlite.connect(self.filename)
        cx.execute("update Version set version='foobar'")
        cx.commit()
        cx.close()
        self.assert_(
            not claims_for_bind(self.url2)
        )

    def test_claim_wrong_fragment(self):
        self.assert_(
            not claims_for_bind("%s;bar" % self.url1)
        )

    def test_claim_without_fragment(self):
        self.assert_(
            claims_for_bind(self.url1)
        )
    
    def test_claim_with_fragment(self):
        self.assert_(
            claims_for_bind(self.url2)
        )

    def test_claim_with_other_fragment(self):
        url3 = "%s;bar" % self.url1
        b, i = create(P(url3))
        self.assert_(
            claims_for_bind(url3)
        )
        b.close(i)

    def test_bind_without_fragment(self):
        b, i = bind(P(self.url1))
        b.close (i)

    def test_bind_with_fragment(self):
        self.b.close (self.i)
        self.b, self.i = bind(P(self.url2))

    def test_bind_with_other_fragment(self):
        url3 = "%s;bar" % self.url1
        b, i = create(P(url3))
        b.close(i)
        b, i = bind(P(url3))
        b.close(i)

    def test_bind_with_other_url(self):
        self.b.close (self.i)
        self.b, self.i = bind(P("http://example.com/a_package"), url=self.url2)


class TestPackageUri(TestCase):
    def test_uri(self):
        be, pid1 = create(P(IN_MEMORY_URL))
        _ , pid2 = create(P("%s;foo" % IN_MEMORY_URL))
        for pid in(pid1, pid2,):
            be.update_uri(pid, "urn:foobar")
            self.assertEqual("urn:foobar", be.get_uri(pid))
            be.update_uri(pid, "urn:toto")
            self.assertEqual("urn:toto", be.get_uri(pid))
            be.update_uri(pid, "")
            self.assertEqual("", be.get_uri(pid))
        be.close(pid1)
        be.close(pid2)

    def tearDown(self):
        del P._L[:] # not required, but saves memory


class TestCache(TestCase):
    def setUp(self):
        self.filename = tmpnam()
        self.url1 = "sqlite:%s" % self.filename
        self.url2 = "%s;foo" % self.url1
        self.url3 = "%s;bar" % self.url1
        self.b, self.i = create(P(self.url2))

    def tearDown(self):
        if self.b:
            self.b.close(self.i)
        unlink(self.filename)
        del P._L[:] # not required, but saves memory

    def test_same_url(self):
        self.assertRaises(PackageInUse, bind, P(self.url2))

    def test_add_fragment(self):
        b, i = create(P(self.url3))
        self.assertEqual(self.b, b)
        b.close(i)

    def test_different_fragment(self):
        b, i = create(P(self.url3))
        b.close(i)
        b, i = bind(P(self.url3))
        self.assertEqual(self.b, b)
        b.close(i)

    def test_no_fragment(self):
        b, i = bind(P(self.url1))
        self.assertEqual(self.b, b)
        b.close(i)

    def test_forget(self):
        old_id = id(self.b)
        self.b.close(self.i)
        b, i = bind(P(self.url2))
        self.assertNotEqual(old_id, id(b))


class TestCreateElement(TestCase):
    def setUp(self):
        self.url1 = IN_MEMORY_URL
        self.url2 = "%s;foo" % self.url1
        self.be, self.pid = create(P(self.url2))

    def tearDown(self):
        self.be.close(self.pid)
        del P._L[:] # not required, but saves memory

    def test_create_media(self):
        try:
            self.be.create_media(self.pid, "m1", "http://example.com/m1.avi")
        except Exception, e:
            self.fail(e) # raised by create_media
        self.assert_(self.be.has_element(self.pid, "m1"))
        self.assert_(self.be.has_element(self.pid, "m1", MEDIA))
        self.assertEquals((MEDIA, self.pid, "m1", "http://example.com/m1.avi"),
                           self.be.get_element(self.pid, "m1"))
        # check that it has no content
        self.assertEqual(self.be.get_content(self.pid, "m1", MEDIA),
                          None) 

    def test_create_annotation(self):
        self.be.create_media(self.pid, "m1", "http://example.com/m1.avi")
        try:
            self.be.create_annotation(self.pid, "a4", "m1", 10, 20)
        except Exception, e:
            self.fail(e) # raised by create_annotation
        self.assert_(self.be.has_element(self.pid, "a4"))
        self.assert_(self.be.has_element(self.pid, "a4", ANNOTATION))
        self.assertEquals((ANNOTATION, self.pid, "a4", "m1", 10, 20),
                           self.be.get_element(self.pid, "a4"))
        # check that it has a content
        self.assertNotEqual(self.be.get_content(self.pid, "a4", ANNOTATION),
                             None)

    def test_create_relation(self):
        try:
            self.be.create_relation(self.pid, "r1")
        except Exception, e:
            self.fail(e) # raised by create_relation
        self.assert_(self.be.has_element(self.pid, "r1"))
        self.assert_(self.be.has_element(self.pid, "r1", RELATION))
        # check that it has a content
        self.assertNotEqual(self.be.get_content(self.pid, "r1", RELATION),
                             None)

    def test_create_view(self):
        try:
            self.be.create_view(self.pid, "v1")
        except Exception, e:
            self.fail(e) # raised by create_view
        self.assert_(self.be.has_element(self.pid, "v1"))
        self.assert_(self.be.has_element(self.pid, "v1", VIEW))
        # check that it has a content
        self.assertNotEqual(self.be.get_content(self.pid, "v1", VIEW),
                             None)

    def test_create_resource(self):
        try:
            self.be.create_resource(self.pid, "R1")
        except Exception, e:
            self.fail(e) # raised by create_resource
        self.assert_(self.be.has_element(self.pid, "R1"))
        self.assert_(self.be.has_element(self.pid, "R1", RESOURCE))
        # check that it has a content
        self.assertNotEqual(self.be.get_content(self.pid, "R1", RESOURCE),
                             None)

    def test_create_tag(self):
        try:
            self.be.create_tag(self.pid, "t1")
        except Exception, e:
            self.fail(e) # raised by create_tag
        self.assert_(self.be.has_element(self.pid, "t1"))
        self.assert_(self.be.has_element(self.pid, "t1", TAG))
        # check that it has no content
        self.assertEqual(self.be.get_content(self.pid, "t1", TAG),
                          None)

    def test_create_list(self):
        try:
            self.be.create_list(self.pid, "l1")
        except Exception, e:
            self.fail(e) # raised by create_list
        self.assert_(self.be.has_element(self.pid, "l1"))
        self.assert_(self.be.has_element(self.pid, "l1", LIST))
        # check that it has no content
        self.assertEqual(self.be.get_content(self.pid, "l1", LIST),
                          None)

    def test_create_query(self):
        try:
            self.be.create_query(self.pid, "q1")
        except Exception, e:
            self.fail(e) # raised by create_query
        self.assert_(self.be.has_element(self.pid, "q1"))
        self.assert_(self.be.has_element(self.pid, "q1", QUERY))
        # check that it has a content
        self.assertNotEqual(self.be.get_content(self.pid, "q1", QUERY),
                             None)

    def test_create_import(self):
        try:
            self.be.create_import(self.pid, "i1",
                                   "http://example.com/advene/db", "",)
        except Exception, e:
            self.fail(e) # raised by create_import
        self.assert_(self.be.has_element(self.pid, "i1"))
        self.assert_(self.be.has_element(self.pid, "i1", IMPORT))
        self.assertEquals((IMPORT, self.pid, "i1",
                            "http://example.com/advene/db", ""),
                           self.be.get_element(self.pid, "i1"))
        # check that it has no content
        self.assertEqual(self.be.get_content(self.pid, "i1", IMPORT),
                          None)


class TestHandleElements(TestCase):
    def setUp(self):
        try:
            self.url1 = "http://example.com/p1"
            self.url2 = "http://example.com/p2"
            self.be, self.pid1 = create(P(self.url1), url=IN_MEMORY_URL)
            _,       self.pid2 = create(P(self.url2), url=IN_MEMORY_URL+";foo")

            self.m1_url = "http://example.com/m1.avi"
            self.m2_url = "http://example.com/m2.avi"
            self.m3_url = "http://example.com/m3.avi"
            self.i1_uri = "urn:xyz-abc"
            self.i2_url = "http://example.com/advene/db2"

            self.m1 = (self.pid1, "m1", self.m1_url)
            self.m2 = (self.pid1, "m2", self.m2_url)
            self.a1 = (self.pid1, "a1", "i1:m3", 15, 20)
            self.a2 = (self.pid1, "a2", "m1", 10, 30)
            self.a3 = (self.pid1, "a3", "m2", 10, 20)
            self.a4 = (self.pid1, "a4", "m1", 10, 20)
            self.r1 = (self.pid1, "r1",)
            self.r2 = (self.pid1, "r2",)
            self.v1 = (self.pid1, "v1",)
            self.v2 = (self.pid1, "v2",)
            self.R1 = (self.pid1, "R1",)
            self.R2 = (self.pid1, "R2",)
            self.t1 = (self.pid1, "t1",)
            self.t2 = (self.pid1, "t2",)
            self.l1 = (self.pid1, "l1",)
            self.l2 = (self.pid1, "l2",)
            self.q1 = (self.pid1, "q1",)
            self.q2 = (self.pid1, "q2",)
            self.i1 = (self.pid1, "i1", self.url2, self.i1_uri)
            self.i2 = (self.pid1, "i2", self.i2_url, "")

            self.own = [ self.m1, self.m2, self.a4, self.a3, self.a2, self.a1,
                         self.r1, self.r2, self.v1, self.v2, self.t1, self.t2,
                         self.l1, self.l2, self.i1, self.i2, ]

            self.be.create_import(*self.i1)
            self.be.create_import(*self.i2)
            self.be.create_media(*self.m1)
            self.be.create_media(*self.m2)
            self.be.create_annotation(*self.a1) 
            self.be.create_annotation(*self.a2)
            self.be.create_annotation(*self.a3)
            self.be.create_annotation(*self.a4)
            self.be.create_relation(*self.r1)
            self.be.create_relation(*self.r2)
            self.be.create_view(*self.v1)
            self.be.create_view(*self.v2)
            self.be.create_resource(*self.R1)
            self.be.create_resource(*self.R2)
            self.be.create_tag(*self.t1)
            self.be.create_tag(*self.t2)
            self.be.create_list(*self.l1)
            self.be.create_list(*self.l2)
            self.be.create_query(*self.q1)
            self.be.create_query(*self.q2)

            self.be.update_uri(self.pid2, self.i1_uri)

            self.m3 = (self.pid2, "m3", self.m3_url)
            self.a5 = (self.pid2, "a5", "m3", 25, 30)
            self.a6 = (self.pid2, "a6", "m3", 35, 45)
            self.r3 = (self.pid2, "r3",)
            self.v3 = (self.pid2, "v3",)
            self.R3 = (self.pid2, "R3",)
            self.t3 = (self.pid2, "t3",)
            self.l3 = (self.pid2, "l3",)
            self.q3 = (self.pid2, "q3",)
            self.i3 = (self.pid2, "i3", self.i2_url, "")

            self.imported = [ self.m3, self.a5, self.a6, self.r3, self.v3,
                              self.R3, self.t3, self.l3, self.q3, self.i3, ]

            self.be.create_import(*self.i3)
            self.be.create_media(*self.m3)
            self.be.create_annotation(*self.a5)
            self.be.create_annotation(*self.a6)
            self.be.create_relation(*self.r3)
            self.be.create_view(*self.v3)
            self.be.create_resource(*self.R3)
            self.be.create_tag(*self.t3)
            self.be.create_list(*self.l3)
            self.be.create_query(*self.q3)
            self.be.update_uri(self.pid2, self.i1_uri)
        except:
            self.tearDown()
            raise

    def tearDown(self):
        self.be.close(self.pid1)
        self.be.close(self.pid2)
        del P._L[:] # not required, but saves memory

    def test_has_element(self):
        for i in self.own + self.imported:
            self.assert_(self.be.has_element(*i[:2]), msg=i)
            t = T[i[1][0]]
            self.assert_(self.be.has_element(i[0], i[1], t), msg=i)
        for i in self.own:
            self.assert_(not self.be.has_element(self.pid2, i[1]), msg=i)
            t = T[i[1][0]]
            self.assert_(not self.be.has_element(self.pid2, i[1], t), msg=i)
        for i in self.imported:
            self.assert_(not self.be.has_element(self.pid1, i[1]), msg=i)
            t = T[i[1][0]]
            self.assert_(not self.be.has_element(self.pid1, i[1], t), msg=i)
        self.assert_(not self.be.has_element(self.pid1, "foobar"))
        self.assert_(not self.be.has_element(self.pid2, "foobar"))

    def test_get_element(self):
        for i in self.own + self.imported:
            self.assertEqual(self.be.get_element(*i[:2])[1:], i)

    def test_iter_medias(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_medias(*a, **k) ) 

        ref = frozenset([self.m1, self.m2, self.m3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.m1, self.m2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.m3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.m1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="m1",))

        ref = frozenset([self.m1, self.m3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("m1","m3"),))

        ref = frozenset([self.m1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), url=self.m1_url,))

        ref = frozenset([self.m1, self.m3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2), url_alt=(self.m1_url, self.m3_url),))

        # mixing several criteria

        ref = frozenset([])
        self.assertEqual(ref,
            get((self.pid1, self.pid2), id="m1", url=self.m2_url,))

    def test_iter_annotations(self):

        # NB: annotations are ordered, so we compare lists
        # NB: it is IMPORTANT that the identifiers of annotations do not
        # exactly match their chronological order, for the tests to be
        # really significant

        # the following function makes assert expression fit in one line...

        def get(*a, **k):
            return [ i[1:] for i in self.be.iter_annotations(*a, **k) ]

        ref = [self.a4, self.a3, self.a2, self.a1, self.a5, self.a6,]
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = [self.a4, self.a3, self.a2, self.a1,]
        self.assertEqual(ref, get((self.pid1,),))

        ref = [self.a5, self.a6,]
        self.assertEqual(ref, get((self.pid2,),))

        ref = [self.a4,]
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="a4",))

        ref = [self.a3, self.a1, self.a6]
        self.assertEqual(ref,
            get((self.pid1, self.pid2), id_alt=("a6", "a1", "a3",),))

        media2 = "%s#m3" % self.i1_uri
        ref = [self.a1, self.a5, self.a6]
        self.assertEqual(ref,
            get((self.pid1, self.pid2), media=media2,))

        media4_or_3 = ("%s#m1" % self.url1, media2)
        ref = [self.a4, self.a2, self.a1, self.a5, self.a6,]
        self.assertEqual(ref,
            get((self.pid1, self.pid2), media_alt=media4_or_3,))

        ref = [self.a4, self.a3, self.a2,]
        self.assertEqual(ref, get((self.pid1, self.pid2), begin=10,))

        ref = [self.a1, self.a5, self.a6,]
        self.assertEqual(ref, get((self.pid1, self.pid2), begin_min=15,))

        ref = [self.a4, self.a3, self.a2, self.a1,]
        self.assertEqual(ref, get((self.pid1, self.pid2), begin_max=15,))

        ref = [self.a2, self.a5,]
        self.assertEqual(ref, get((self.pid1, self.pid2), end=30,))

        ref = [self.a2, self.a5, self.a6]
        self.assertEqual(ref, get((self.pid1, self.pid2), end_min=30,))

        ref = [self.a4, self.a3, self.a2, self.a1, self.a5]
        self.assertEqual(ref, get((self.pid1, self.pid2), end_max=30,))

        # mixing several criteria

        ref = [self.a2, self.a5,]
        self.assertEqual(ref,
            get((self.pid1, self.pid2), begin_max=27, end_min=27,))

        ref = [self.a2, self.a5,]
        self.assertEqual(ref,
            get((self.pid1, self.pid2), begin_max=27, end_min=27,))

        ref = [self.a5,]
        self.assertEqual(ref, get((self.pid2,), begin_max=27, end_min=27,))

        ref = [self.a1, self.a5,]
        self.assertEqual(ref,
            get((self.pid1, self.pid2), media=media2, end_max=30,))

    def test_iter_relations(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_relations(*a, **k) ) 

        ref = frozenset([self.r1, self.r2, self.r3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.r1, self.r2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.r3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.r1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="r1",))

        ref = frozenset([self.r1, self.r3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("r1","r3"),))

    def test_get_view(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_views(*a, **k) ) 

        ref = frozenset([self.v1, self.v2, self.v3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.v1, self.v2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.v3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.v1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="v1",))

        ref = frozenset([self.v1, self.v3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("v1","v3"),))

    def test_iter_resources(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_resources(*a, **k) ) 

        ref = frozenset([self.R1, self.R2, self.R3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.R1, self.R2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.R3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.R1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="R1",))

        ref = frozenset([self.R1, self.R3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("R1","R3"),))

    def test_iter_tags(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_tags(*a, **k) ) 

        ref = frozenset([self.t1, self.t2, self.t3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.t1, self.t2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.t3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.t1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="t1",))

        ref = frozenset([self.t1, self.t3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("t1","t3"),))

    def test_iter_lists(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_lists(*a, **k) ) 

        ref = frozenset([self.l1, self.l2, self.l3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.l1, self.l2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.l3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.l1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="l1",))

        ref = frozenset([self.l1, self.l3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("l1","l3"),))

    def test_iter_queries(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_queries(*a, **k) ) 

        ref = frozenset([self.q1, self.q2, self.q3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.q1, self.q2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.q3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.q1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="q1",))

        ref = frozenset([self.q1, self.q3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("q1","q3"),))

    def test_iter_imports(self):

        # the following function makes assert expression fit in one line...
        def get(*a, **k):
            return frozenset( i[1:] for i in self.be.iter_imports(*a, **k) ) 

        ref = frozenset([self.i1, self.i2, self.i3,])
        self.assertEqual(ref, get((self.pid1, self.pid2,),))

        ref = frozenset([self.i1, self.i2,])
        self.assertEqual(ref, get((self.pid1,),))

        ref = frozenset([self.i3,])
        self.assertEqual(ref, get((self.pid2,),))

        ref = frozenset([self.i1,])
        self.assertEqual(ref, get((self.pid1, self.pid2,), id="i1",))

        ref = frozenset([self.i1, self.i3,])
        self.assertEqual(ref,
            get((self.pid1, self.pid2,), id_alt=("i1","i3"),))

        ref = frozenset([self.i2, self.i3,])
        self.assertEqual(ref, get((self.pid1, self.pid2), url=self.i2_url,))

        ref = frozenset([self.i1, self.i2, self.i3,])
        self.assertEqual(ref,
            get((self.pid1, self.pid2), url_alt=(self.url2, self.i2_url),))

        ref = frozenset([self.i1,])
        self.assertEqual(ref, get((self.pid1, self.pid2), uri=self.i1_uri,))

        ref = frozenset([self.i1, self.i2, self.i3])
        self.assertEqual(ref,
            get((self.pid1, self.pid2), uri_alt=("", self.i1_uri)))

    def test_update_media(self):
        self.be.update_media(self.pid1, "m1", "http://foo.com/m1.avi")
        self.assertEqual(('m', self.pid1, "m1", "http://foo.com/m1.avi"),
                         self.be.get_element(self.pid1, "m1"))

    def test_update_annotation(self):
        self.be.update_annotation(self.pid1, "a1", "m1", 25, 30)
        self.assertEqual(('a', self.pid1, "a1", "m1", 25, 30),
                         self.be.get_element(self.pid1, "a1"))

    def test_update_import(self):
        self.be.update_import(self.pid1, "i1", "http://foo.com/advene/db",
                                                "urn:xyz")
        self.assertEqual(('i', self.pid1, "i1",
                          "http://foo.com/advene/db", "urn:xyz"),
                         self.be.get_element(self.pid1, "i1"))

    def test_content(self):
        mime = "text/html"
        data = "<em>hello</em> world"

        for i in [self.a4, self.r1, self.v1, self.R1, self.q1,
                  self.a5, self.r3, self.v3, self.q3,]:
            typ = T[i[1][0]]
            if i[0] is self.pid1: schema = "i1:R3"
            else:              schema = "R3"
            self.be.update_content(i[0], i[1], mime, data, schema)
            self.assertEqual((mime, data, schema),
                self.be.get_content(i[0], i[1], typ))
            self.be.update_content(i[0], i[1], mime, data, "")
            self.assertEqual((mime, data, ""),
                self.be.get_content(i[0], i[1], typ))
            self.be.update_content(i[0], i[1], "", "", "")
            self.assertEqual(("", "", ""),
                self.be.get_content(i[0], i[1], typ))

    def test_metadata(self):
        dc_creator = "http://purl.org/dc/elements/1.1/creator"
        value1 = "pchampin"
        value2 = "oaubert"
        for i in self.own + self.imported:
            typ = T[i[1][0]]
            self.be.set_meta(i[0], i[1], typ, dc_creator, value1)
            self.assertEqual(value1,
                self.be.get_meta(i[0], i[1], typ, dc_creator))
            self.be.set_meta(i[0], i[1], typ, dc_creator, value2)
            self.assertEqual(value2,
                self.be.get_meta(i[0], i[1], typ, dc_creator))
            self.be.set_meta(i[0], i[1], typ, dc_creator, None)
            self.assertEqual(None,
                self.be.get_meta(i[0], i[1], typ, dc_creator))

    def test_iter_metadata(self):
        props_random = [
            "http://purl.org/dc/elements/1.1/description",
            "http://purl.org/dc/elements/1.1/creator",
            "http://purl.org/dc/elements/1.1/date",
        ]
        items_sorted = zip(props_random, ["xxx"]*3)
        items_sorted.sort()

        for i in self.own + self.imported:
            typ = T[i[1][0]]
            for p in props_random:
                self.be.set_meta(i[0], i[1], typ, p, "xxx")
            self.assertEqual(items_sorted, list(
                self.be.iter_meta(i[0], i[1], typ)))

    def test_members(self):

        def compare_to_list(L, pid, rid):
            self.assertEqual(len(L), self.be.count_members(pid, rid))
            for i in xrange(len(L)):
                self.assertEqual(L[i], self.be.get_member(pid, rid, i))
            self.assertEqual(L, list(self.be.iter_members(pid, rid)))

        self.be.insert_member(self.pid1, "r1", "a4", -1)
        compare_to_list(["a4",], self.pid1, "r1")

        self.be.insert_member(self.pid1, "r1", "a3", -1)
        compare_to_list(["a4", "a3",], self.pid1, "r1")

        self.be.insert_member(self.pid1, "r1", "i1:a5", 1)
        compare_to_list(["a4", "i1:a5", "a3",], self.pid1, "r1")
            
        self.be.insert_member(self.pid1, "r1", "a2", 1)
        compare_to_list(["a4", "a2", "i1:a5", "a3",], self.pid1, "r1")
            
        self.be.update_member(self.pid1, "r1", "i1:a6", 0)
        compare_to_list(["i1:a6", "a2", "i1:a5", "a3",], self.pid1, "r1")

        self.be.remove_member(self.pid1, "r1", 0)
        compare_to_list(["a2", "i1:a5", "a3",], self.pid1, "r1")

        self.be.insert_member(self.pid1, "r2", "a4", -1)
        self.be.insert_member(self.pid2, "r3", "a5", -1)
        self.be.insert_member(self.pid2, "r3", "a6", -1)
        rel_w_member = self.be.iter_relations_with_member
        pids = (self.pid1, self.pid2,)
        # with url in uri-ref
        a5_uri_ref = "%s#a5" % self.url2
        self.assertEqual(frozenset((RELATION,)+i for i in [self.r1, self.r3]),
                          frozenset(rel_w_member(pids, a5_uri_ref,)))
        self.assertEqual(frozenset([(RELATION,)+self.r1,]),
                          frozenset(rel_w_member(pids, a5_uri_ref, 1)))
        # with uri in uri-ref
        a5_uri_ref = "%s#a5" % self.i1_uri
        self.assertEqual(frozenset((RELATION,)+i for i in [self.r1, self.r3]),
                          frozenset(rel_w_member(pids, a5_uri_ref,)))
        self.assertEqual(frozenset([(RELATION,)+self.r1,]),
                          frozenset(rel_w_member(pids, a5_uri_ref, 1)))
        # with not all packages
        self.assertEqual(frozenset([(RELATION,)+self.r3,]),
                          frozenset(rel_w_member((self.pid2,), a5_uri_ref)))

    def test_items(self):

        def compare_to_list(L, pid, rid):
            self.assertEqual(len(L), self.be.count_items(pid, rid))
            for i in xrange(len(L)):
                self.assertEqual(L[i], self.be.get_item(pid, rid, i))
            self.assertEqual(L, list(self.be.iter_items(pid, rid)))

        self.be.insert_item(self.pid1, "l1", "a4", -1)
        compare_to_list(["a4",], self.pid1, "l1")

        self.be.insert_item(self.pid1, "l1", "a3", -1)
        compare_to_list(["a4", "a3",], self.pid1, "l1")

        self.be.insert_item(self.pid1, "l1", "i1:r3", 1)
        compare_to_list(["a4", "i1:r3", "a3",], self.pid1, "l1")
            
        self.be.insert_item(self.pid1, "l1", "r2", 1)
        compare_to_list(["a4", "r2", "i1:r3", "a3",], self.pid1, "l1")
            
        self.be.update_item(self.pid1, "l1", "i1:a6", 0)
        compare_to_list(["i1:a6", "r2", "i1:r3", "a3",], self.pid1, "l1")

        self.be.remove_item(self.pid1, "l1", 0)
        compare_to_list(["r2", "i1:r3", "a3",], self.pid1, "l1")

        self.be.insert_item(self.pid1, "l2", "a4", -1)
        self.be.insert_item(self.pid2, "l3", "r3", -1)
        self.be.insert_item(self.pid2, "l3", "a6", -1)
        lst_w_item = self.be.iter_lists_with_item
        pids = (self.pid1, self.pid2,)
        # with url in uri-ref
        r3_uri_ref = "%s#r3" % self.url2
        self.assertEqual(frozenset((LIST,)+i for i in [self.l1, self.l3]),
                          frozenset(lst_w_item(pids, r3_uri_ref,)))
        self.assertEqual(frozenset([(LIST,)+self.l1,]),
                          frozenset(lst_w_item(pids, r3_uri_ref, 1)))
        # with uri in uri-ref
        r3_uri_ref = "%s#r3" % self.i1_uri
        self.assertEqual(frozenset((LIST,)+i for i in [self.l1, self.l3]),
                          frozenset(lst_w_item(pids, r3_uri_ref,)))
        self.assertEqual(frozenset([(LIST,)+self.l1,]),
                          frozenset(lst_w_item(pids, r3_uri_ref, 1)))
        # with not all packages
        self.assertEqual(frozenset([(LIST,)+self.l3,]),
                          frozenset(lst_w_item((self.pid2,), r3_uri_ref)))

    def test_tagged(self):
        self.be.associate_tag(self.pid1, "a1",    "t1")
        self.be.associate_tag(self.pid1, "i1:a5", "t1")
        self.be.associate_tag(self.pid1, "a2",    "i1:t3")
        self.be.associate_tag(self.pid1, "i1:a5", "i1:t3")
        self.be.associate_tag(self.pid2, "a6",    "t3")

        a1 = frozenset(((self.pid1, "a1"),))
        a2 = frozenset(((self.pid1, "a2"),))
        a5i = frozenset(((self.pid1, "i1:a5"),))
        a5 = frozenset(((self.pid2, "a5"),))
        a6 = frozenset(((self.pid2, "a6"),))
        pids = (self.pid1, self.pid2,)
        elts_w_tag = self.be.iter_elements_with_tag

        self.assertEqual( a1.union(a5i),
            frozenset(elts_w_tag(pids, "%s#t1" % self.url1))
        )

        self.assertEqual( a2.union(a5i).union(a6),
            frozenset(elts_w_tag(pids, "%s#t3" % self.url2))
        )

        self.assertEqual( a2.union(a5i).union(a6),
            frozenset(elts_w_tag(pids, "%s#t3" % self.i1_uri))
        )

        self.assertEqual( a2.union(a5i),
            frozenset(elts_w_tag((self.pid1,), "%s#t3" % self.i1_uri))
        )

        t1 = frozenset(((self.pid1, "t1"),))
        t3i = frozenset(((self.pid1, "i1:t3"),))
        t3 = frozenset(((self.pid2, "t3"),))
        tags_w_elt = self.be.iter_tags_with_element

        self.assertEquals( t1,
            frozenset(tags_w_elt(pids, "%s#a1" % self.url1))
        )

        self.assertEquals( t1.union(t3i),
            frozenset(tags_w_elt(pids, "%s#a5" % self.url2))
        )

        self.assertEquals( t1.union(t3i),
            frozenset(tags_w_elt(pids, "%s#a5" % self.i1_uri))
        )

        self.be.associate_tag(self.pid2, "a5", "t3")

        self.assertEquals( t1.union(t3i).union(t3),
            frozenset(tags_w_elt(pids, "%s#a5" % self.i1_uri))
        )

        self.assertEquals( t3,
            frozenset(tags_w_elt((self.pid2,), "%s#a5" % self.i1_uri))
        )

        self.assertEquals( frozenset((self.pid1, self.pid2)), frozenset(self.
         be.iter_tagging(pids, "%s#a5" % self.url2, "%s#t3" % self.i1_uri))
        )

        self.assertEquals( frozenset((self.pid1, self.pid2)), frozenset(self.
         be.iter_tagging(pids, "%s#a5" % self.i1_uri, "%s#t3" % self.url2))
        )

        self.assertEquals( frozenset(), frozenset(self.be.
         iter_tagging((self.pid1,), "%s#a3" % self.i1_uri, "%s#t6" % self.url2))
        )

        self.be.dissociate_tag(self.pid1, "a1",    "t1")
        self.be.dissociate_tag(self.pid1, "i1:a5", "t1")
        self.be.dissociate_tag(self.pid1, "a2",    "i1:t3")
        self.be.dissociate_tag(self.pid1, "i1:a5", "i1:t3")
        self.be.dissociate_tag(self.pid2, "a5",    "t3")
        self.be.dissociate_tag(self.pid2, "a6",    "t3")


class TestRetrieveDataWithSameId(TestCase):
    def setUp(self):
        try:
            self.url1 = IN_MEMORY_URL
            self.url2 = "%s;foo" % self.url1
            self.be, self.pid1 = create(P(self.url1))
            _,       self.pid2 = create(P(self.url2))

            self.m_url = "http://example.com/m1.avi"

            self.m = ("m", self.m_url)
            self.a = ("a", "m", 10, 20)
            self.r = ("r",)
            self.v = ("v",)
            self.R = ("R",)
            self.t = ("t",)
            self.l = ("l",)
            self.q = ("q",)
            self.i1 = (self.pid1, "i", self.url2, "")
            self.i2 = (self.pid2, "i", self.url1, "")

            self.generic = [self.m, self.a, self.r, self.v, self.R, self.t,
                            self.l, self.q]
            self.ids = list("marvRtlqi")

            self.be.create_media(self.pid1, *self.m)
            self.be.create_media(self.pid2, *self.m)
            self.be.create_annotation(self.pid1, *self.a)
            self.be.create_annotation(self.pid2, *self.a)
            self.be.create_relation(self.pid1, *self.r)
            self.be.create_relation(self.pid2, *self.r)
            self.be.create_view(self.pid1, *self.v)
            self.be.create_view(self.pid2, *self.v)
            self.be.create_resource(self.pid1, *self.R)
            self.be.create_resource(self.pid2, *self.R)
            self.be.create_tag(self.pid1, *self.t)
            self.be.create_tag(self.pid2, *self.t)
            self.be.create_list(self.pid1, *self.l)
            self.be.create_list(self.pid2, *self.l)
            self.be.create_query(self.pid1, *self.q)
            self.be.create_query(self.pid2, *self.q)
            self.be.create_import(*self.i1)
            self.be.create_import(*self.i2)
        except:
            self.tearDown()
            raise

    def tearDown(self):
        if hasattr(self, "be") and self.be:
            self.be.close(self.pid1)
            self.be.close(self.pid2)
        del P._L[:] # not required, but saves memory

    def test_has_element(self):
        for i in self.ids:
            self.assert_(self.be.has_element(self.pid1, i), msg=i)
            self.assert_(self.be.has_element(self.pid2, i), msg=i)
            self.assert_(self.be.has_element(self.pid1, i, T[i]), msg=i)
            self.assert_(self.be.has_element(self.pid2, i, T[i]), msg=i)

    def test_get_element(self):
        for i in self.generic:
            self.assertEqual(self.be.get_element(self.pid1, i[0])[2:], i)
            self.assertEqual(self.be.get_element(self.pid2, i[0])[2:], i)
        self.assertEqual(self.be.get_element(self.pid1, "i")[1:], self.i1)
        self.assertEqual(self.be.get_element(self.pid2, "i")[1:], self.i2)

    def test_iter_medias(self):
        self.assertEqual(2, len(list(
            self.be.iter_medias((self.pid1, self.pid2), id="m",))))
        self.assertEqual(1, len(list(
            self.be.iter_medias((self.pid1,), id="m",))))
        self.assertEqual(1, len(list(
            self.be.iter_medias((self.pid2,), id="m",))))

    def test_iter_annotations(self):
        self.assertEqual(2, len(list(
            self.be.iter_annotations((self.pid1, self.pid2), id="a",))))
        self.assertEqual(1, len(list(
            self.be.iter_annotations((self.pid1,), id="a",))))
        self.assertEqual(1, len(list(
            self.be.iter_annotations((self.pid2,), id="a",))))

    def test_iter_relations(self):
        self.assertEqual(2, len(list(
            self.be.iter_relations((self.pid1, self.pid2), id="r",))))
        self.assertEqual(1, len(list(
            self.be.iter_relations((self.pid1,), id="r",))))
        self.assertEqual(1, len(list(
            self.be.iter_relations((self.pid2,), id="r",))))

    def test_iter_views(self):
        self.assertEqual(2, len(list(
            self.be.iter_views((self.pid1, self.pid2), id="v",))))
        self.assertEqual(1, len(list(
            self.be.iter_views((self.pid1,), id="v",))))
        self.assertEqual(1, len(list(
            self.be.iter_views((self.pid2,), id="v",))))

    def test_iter_resources(self):
        self.assertEqual(2, len(list(
            self.be.iter_resources((self.pid1, self.pid2), id="R",))))
        self.assertEqual(1, len(list(
            self.be.iter_resources((self.pid1,), id="R",))))
        self.assertEqual(1, len(list(
            self.be.iter_resources((self.pid2,), id="R",))))

    def test_iter_tags(self):
        self.assertEqual(2, len(list(
            self.be.iter_tags((self.pid1, self.pid2), id="t",))))
        self.assertEqual(1, len(list(
            self.be.iter_tags((self.pid1,), id="t",))))
        self.assertEqual(1, len(list(
            self.be.iter_tags((self.pid2,), id="t",))))

    def test_iter_lists(self):
        self.assertEqual(2, len(list(
            self.be.iter_lists((self.pid1, self.pid2), id="l",))))
        self.assertEqual(1, len(list(
            self.be.iter_lists((self.pid1,), id="l",))))
        self.assertEqual(1, len(list(
            self.be.iter_lists((self.pid2,), id="l",))))

    def test_iter_queries(self):
        self.assertEqual(2, len(list(
            self.be.iter_queries((self.pid1, self.pid2), id="q",))))
        self.assertEqual(1, len(list(
            self.be.iter_queries((self.pid1,), id="q",))))
        self.assertEqual(1, len(list(
            self.be.iter_queries((self.pid2,), id="q",))))

    def test_iter_imports(self):
        self.assertEqual(2, len(list(
            self.be.iter_imports((self.pid1, self.pid2), id="i",))))
        self.assertEqual(1, len(list(
            self.be.iter_imports((self.pid1,), id="i",))))
        self.assertEqual(1, len(list(
            self.be.iter_imports((self.pid2,), id="i",))))


if __name__ == "__main__":
     main()
