from pysqlite2 import dbapi2 as sqlite
from os        import tmpnam, unlink
from os.path   import exists
from unittest  import TestCase, main
from warnings  import filterwarnings

from advene.model.backends.sqlite \
  import claims_for_create, create, claims_for_bind, bind, IN_MEMORY_URL, \
         PackageInUse, InternalError
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

    def test_claim_new_file_with_pid(self):
        self.assert_( 
            claims_for_create(self.url2)
        )

    def test_claim_existing_pid(self):
        b, i = create(P(self.url2))
        b.close(i)
        self.assert_(
            not claims_for_create("%s;foo" % self.url1)
        )

    def test_claim_new_pid(self):
        b, i = create(P(self.url2))
        b.close(i)
        self.assert_(
            claims_for_create("%s;bar" % self.url1)
        )

    def test_claim_memory(self):
        self.assert_( 
            claims_for_create(IN_MEMORY_URL)
        )

    def test_claim_memory_existing_pid(self):
        b, i = create(P(IN_MEMORY_URL+";foo"))
        self.assert_(
            not claims_for_create(IN_MEMORY_URL+";foo")
        )
        b.close(i)

    def test_create_without_pid(self):
        b, i = create(P(self.url1))
        self.assert_(
            claims_for_bind(self.url1)
        )
        b.close(i)

    def test_create_with_pid(self):
        b, i = create(P(self.url2))
        self.assert_(
            claims_for_bind(self.url2)
        )
        b.close(i)

    def test_create_new_pid(self):
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
        if self.b:
            self.b.close (self.i)
        del P._L[:] # not required, but saves memory

    def test_claim_non_existing(self):
        unlink(self.filename)
        self.assert_(
            not claims_for_bind(self.url2)
        )

    def test_claim_wrong_format(self):
        self.b.close(self.i)
        self.b = None
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

    def test_claim_wrong_pid(self):
        self.assert_(
            not claims_for_bind("%s;bar" % self.url1)
        )

    def test_claim_without_pid(self):
        self.assert_(
            claims_for_bind(self.url1)
        )
    
    def test_claim_with_pid(self):
        self.assert_(
            claims_for_bind(self.url2)
        )

    def test_claim_with_other_pid(self):
        url3 = "%s;bar" % self.url1
        b, i = create(P(url3))
        self.assert_(
            claims_for_bind(url3)
        )
        b.close(i)

    def test_bind_without_pid(self):
        b, i = bind(P(self.url1))
        b.close (i)

    def test_bind_with_pid(self):
        self.b.close (self.i)
        self.b, self.i = bind(P(self.url2))

    def test_bind_with_other_pid(self):
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

    def test_add_pid(self):
        b, i = create(P(self.url3))
        self.assertEqual(self.b, b)
        b.close(i)

    def test_different_pid(self):
        b, i = create(P(self.url3))
        b.close(i)
        b, i = bind(P(self.url3))
        self.assertEqual(self.b, b)
        b.close(i)

    def test_no_pid(self):
        b, i = bind(P(self.url1))
        self.assertEqual(self.b, b)
        b.close(i)

    def test_forget(self):
        old_id = id(self.b)
        self.b.close(self.i)
        self.b, self.i = bind(P(self.url2))
        self.assertNotEqual(old_id, id(self.b))


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

    url1 = "http://example.com/p1"
    url2 = "http://example.com/p2"

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

    def test_iter_references_with_import(self):
        self.be.update_content(self.pid1, "a2", ANNOTATION,
                               "test/plain", "", "i1:R3")
        self.be.insert_member(self.pid1, "r1", "i1:a5", 0)
        self.be.insert_item(self.pid1, "l1", "i1:a5", 0)
        self.be.associate_tag(self.pid1, "v1", "i1:t3")
        self.be.associate_tag(self.pid1, "i1:a5", "t1")
        ref = frozenset([("a1", "media", "i1:m3"),
            ("a2", "content_schema", "i1:R3"), ("r1", 0, "i1:a5"),
            ("l1", 0, "i1:a5"), ("", ":tag", "i1:t3"),
            ("", ":tagged", "i1:a5"),])

        self.assertEqual(ref,
            frozenset(self.be.iter_references_with_import(self.pid1, "i1",)))

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

    def test_iter_views(self):

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
            self.be.update_content(i[0], i[1], typ, mime, data, schema)
            self.assertEqual((mime, data, schema),
                self.be.get_content(i[0], i[1], typ))
            self.be.update_content(i[0], i[1], typ, mime, data, "")
            self.assertEqual((mime, data, ""),
                self.be.get_content(i[0], i[1], typ))
            self.be.update_content(i[0], i[1], typ, "", "", "")
            self.assertEqual(("", "", ""),
                self.be.get_content(i[0], i[1], typ))

    def test_iter_contents_with_schema(self):
        self.be.create_resource(self.pid2, "R4")
        self.be.create_resource(self.pid2, "R5")
        self.be.update_content(self.pid1, "a1", ANNOTATION,
                               "test/plain", "", "i1:R3")
        self.be.update_content(self.pid1, "a2", ANNOTATION,
                               "test/plain", "", "i2:R3") # it's a trap
        self.be.update_content(self.pid1, "r2", RELATION,
                               "test/plain", "", "i1:R3")
        self.be.update_content(self.pid1, "v1", VIEW,
                               "test/plain", "", "i1:R3")
        self.be.update_content(self.pid1, "q2", QUERY,
                               "test/plain", "", "i1:R3")
        self.be.update_content(self.pid1, "R1", RESOURCE,
                               "test/plain", "", "i1:R3")
        self.be.update_content(self.pid2, "a5", ANNOTATION,
                               "test/plain", "", "R3")
        self.be.update_content(self.pid2, "r3", RELATION,
                               "test/plain", "", "R3")
        self.be.update_content(self.pid2, "v3", VIEW,
                               "test/plain", "", "R3")
        self.be.update_content(self.pid2, "q3", QUERY,
                               "test/plain", "", "R3")
        self.be.update_content(self.pid2, "R4", RESOURCE,
                               "test/plain", "", "R3")
        self.be.update_content(self.pid2, "R5", RESOURCE,
                               "test/plain", "", "R4") # it's a trap
        ref = frozenset([(self.pid1, "a1"), (self.pid1, "r2"),
            (self.pid1, "v1"), (self.pid1, "q2"), (self.pid1, "R1"),
            (self.pid2, "a5"), (self.pid2, "r3"), (self.pid2, "v3"),
            (self.pid2, "q3"), (self.pid2, "R4"),])
        pids = (self.pid1, self.pid2)
        R3_uri = "%s#R3" % self.url2
        self.assertEqual(ref,
            frozenset(self.be.iter_contents_with_schema(pids, R3_uri)))

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


class TestRenameElement(TestCase):

    url1 = TestHandleElements.url1
    url2 = TestHandleElements.url2

    def setUp(self):
        # reuse the bunch of code defined in TestHandleElements:
        TestHandleElements.__dict__["setUp"](self)

    def tearDown(self):
        TestHandleElements.__dict__["tearDown"](self)

    def test_rename_media(self):
        mX_url = "file:///tmp/mX"
        self.be.create_media(self.pid1, "mX", mX_url)
        self.be.rename_element(self.pid1, "mX", MEDIA, "mY")
        self.assert_(not self.be.has_element(self.pid1, "mX"))
        self.assertEqual((MEDIA, self.pid1, "mY", mX_url),
                         self.be.get_element(self.pid1, "mY"))

    def test_rename_annotation(self):
        self.be.create_annotation(self.pid1, "aX", "m1", 1, 2)
        self.be.update_content(self.pid1, "aX", ANNOTATION,
                               "text/plain", "aX data", "")
        self.be.rename_element(self.pid1, "aX", ANNOTATION, "aY")
        self.assert_(not self.be.has_element(self.pid1, "aX"))
        self.assertEqual((ANNOTATION, self.pid1, "aY", "m1", 1, 2),
                         self.be.get_element(self.pid1, "aY"))
        self.assertEqual(("text/plain", "aX data", "",),
                         self.be.get_content(self.pid1, "aY", ANNOTATION))

    def test_rename_relation(self):
        self.be.create_relation(self.pid1, "rX")
        self.be.update_content(self.pid1, "rX", RELATION,
                               "text/plain", "rX data", "")
        self.be.insert_member(self.pid1, "rX", "a1", 0)
        self.be.rename_element(self.pid1, "rX", RELATION, "rY")
        self.assert_(not self.be.has_element(self.pid1, "rX"))
        self.assertEqual((RELATION, self.pid1, "rY",),
                         self.be.get_element(self.pid1, "rY"))
        self.assertEqual(("text/plain", "rX data", "",),
                         self.be.get_content(self.pid1, "rY", RELATION))
        self.assertEqual("a1", self.be.get_member(self.pid1, "rY", 0))
 
    def test_rename_list(self):
        self.be.create_list(self.pid1, "lX")
        self.be.insert_item(self.pid1, "lX", "r1", 0)
        self.be.rename_element(self.pid1, "lX", LIST, "lY")
        self.assert_(not self.be.has_element(self.pid1, "rX"))
        self.assertEqual((LIST, self.pid1, "lY",),
                         self.be.get_element(self.pid1, "lY"))
        self.assertEqual("r1", self.be.get_item(self.pid1, "lY", 0))

    def test_rename_tag(self):
        self.be.create_tag(self.pid1, "tX")
        self.be.rename_element(self.pid1, "tX", TAG, "tY")
        self.assert_(not self.be.has_element(self.pid1, "tX"))
        self.assertEqual((TAG, self.pid1, "tY",),
                         self.be.get_element(self.pid1, "tY"))
        # tag associations are updated by rename_references, so we do not
        # test them here

    def test_rename_import(self):
        iX_url = "file:///tmp/iX"
        self.be.create_import(self.pid1, "iX", iX_url, "")

        self.be.update_annotation(self.pid1, "a1", "iX:m", 1, 2)
        self.be.update_content(self.pid1, "a1", ANNOTATION,
                               "text/plain", "", "iX:R")
        self.be.insert_member(self.pid1, "r1", "iX:a", 0)
        self.be.insert_item(self.pid1, "l1", "iX:r", 0)
        self.be.associate_tag(self.pid1, "a1", "iX:t")
        self.be.associate_tag(self.pid1, "iX:a", "t1")

        self.be.rename_element(self.pid1, "iX", IMPORT, "iY")
        self.assert_(not self.be.has_element(self.pid1, "iX"))
        self.assertEqual((IMPORT, self.pid1, "iY", iX_url, ""),
                         self.be.get_element(self.pid1, "iY"))
        self.assertEqual((ANNOTATION, self.pid1, "a1", "iY:m", 1, 2),
                         self.be.get_element(self.pid1, "a1"))
        self.assertEqual(("text/plain", "", "iY:R",),
                         self.be.get_content(self.pid1, "a1", ANNOTATION))
        self.assertEqual("iY:a", self.be.get_member(self.pid1, "r1", 0))
        self.assertEqual("iY:r", self.be.get_item(self.pid1, "l1", 0))
        t_uri = "file:///tmp/iX#t"
        self.assertEqual([(self.pid1, "a1"),],
            list(self.be.iter_elements_with_tag((self.pid1,), t_uri)))
        t1_uri = self.url1 + "#t1"
        self.assertEqual([(self.pid1, "iY:a"),],
            list(self.be.iter_elements_with_tag((self.pid1,), t1_uri)))

    def test_rename_view(self):
        self.be.create_view(self.pid1, "vX",)
        self.be.update_content(self.pid1, "vX", VIEW,
                               "text/plain", "vX data", "")
        self.be.rename_element(self.pid1, "vX", VIEW, "vY")
        self.assert_(not self.be.has_element(self.pid1, "vX"))
        self.assertEqual((VIEW, self.pid1, "vY",),
                         self.be.get_element(self.pid1, "vY"))
        self.assertEqual(("text/plain", "vX data", "",),
                         self.be.get_content(self.pid1, "vY", VIEW))

    def test_rename_resource(self):
        self.be.create_resource(self.pid1, "RX",)
        self.be.update_content(self.pid1, "RX", RESOURCE,
                               "text/plain", "RX data", "")
        self.be.rename_element(self.pid1, "RX", RESOURCE, "RY")
        self.assert_(not self.be.has_element(self.pid1, "RX"))
        self.assertEqual((RESOURCE, self.pid1, "RY",),
                         self.be.get_element(self.pid1, "RY"))
        self.assertEqual(("text/plain", "RX data", "",),
                        self.be.get_content(self.pid1, "RY", RESOURCE))

    def test_rename_query(self):
        self.be.create_query(self.pid1, "qX",)
        self.be.update_content(self.pid1, "qX", QUERY,
                               "text/plain", "qX data", "")
        self.be.rename_element(self.pid1, "qX", QUERY, "qY")
        self.assert_(not self.be.has_element(self.pid1, "qX"))
        self.assertEqual((QUERY, self.pid1, "qY",),
                         self.be.get_element(self.pid1, "qY"))
        self.assertEqual(("text/plain", "qX data", "",),
                         self.be.get_content(self.pid1, "qY", QUERY))

    def test_rename_refs_media(self):
        self.be.create_media(self.pid2, "m4", "file:///tmp/m4")
        self.be.update_annotation(self.pid1, "a2", "i2:m3", 1, 2) #it's a trap!
        self.be.update_annotation(self.pid1, "a3", "i1:m4", 1, 2) #it's a trap!
        pids = (self.pid1, self.pid2)
        m3_uri = "%s#m3" % self.url2
        self.be.rename_element(self.pid2, "m3", MEDIA, "renamed")
        self.be.rename_references(pids, m3_uri, "renamed")
        self.assertEqual("i1:renamed", self.be.get_element(self.pid1, "a1")[3])
        self.assertEqual("renamed", self.be.get_element(self.pid2, "a5")[3])
        self.assertEqual("renamed", self.be.get_element(self.pid2, "a6")[3])
        # did you fall in the trap?
        self.assertEqual("i2:m3", self.be.get_element(self.pid1, "a2")[3])
        self.assertEqual("i1:m4", self.be.get_element(self.pid1, "a3")[3])

        # now only on one package
        m3_uri = "%s#renamed" % self.url2
        self.be.rename_element(self.pid2, "renamed", MEDIA, "foo")
        self.be.rename_references((self.pid2,), m3_uri, "foo")
        self.assertEqual("i1:renamed", self.be.get_element(self.pid1, "a1")[3])
        self.assertEqual("foo", self.be.get_element(self.pid2, "a5")[3])
        self.assertEqual("foo", self.be.get_element(self.pid2, "a6")[3])

    def test_rename_refs_schema(self):
        self.be.create_resource(self.pid2, "R4") 
        self.be.update_content(self.pid1, "a1", ANNOTATION,
                               "test/plain", "", "i1:R3")
        self.be.update_content(self.pid2, "a5", ANNOTATION,
                               "test/plain", "", "R3")
        self.be.update_content(self.pid1, "a2", ANNOTATION,
                               "test/plain", "", "i2:R3") # it's a trap!
        self.be.update_content(self.pid1, "a3", ANNOTATION,
                               "test/plain", "", "i1:R4") # it's a trap!
        pids = (self.pid1, self.pid2)
        R3_uri = "%s#R3" % self.url2
        self.be.rename_element(self.pid2, "R3", RESOURCE, "renamed")
        self.be.rename_references(pids, R3_uri, "renamed")
        self.assertEqual("i1:renamed",
                         self.be.get_content(self.pid1, "a1", ANNOTATION)[2])
        self.assertEqual("renamed",
                         self.be.get_content(self.pid2, "a5", ANNOTATION)[2])
        # did you fall in the traps?
        self.assertEqual("i2:R3",
                         self.be.get_content(self.pid1, "a2", ANNOTATION)[2])
        self.assertEqual("i1:R4",
                         self.be.get_content(self.pid1, "a3", ANNOTATION)[2])

        # now only on one package
        R3_uri = "%s#renamed" % self.url2
        self.be.rename_element(self.pid2, "renamed", RESOURCE, "foo")
        self.be.rename_references((self.pid2,), R3_uri, "foo")
        self.assertEqual("i1:renamed",
                         self.be.get_content(self.pid1, "a1", ANNOTATION)[2])
        self.assertEqual("foo",
                         self.be.get_content(self.pid2, "a5", ANNOTATION)[2])

    def test_rename_refs_member(self):
        self.be.insert_member(self.pid2, "r3", "a6", 0) # it's a trap
        self.be.insert_member(self.pid2, "r3", "a5", 1)
        self.be.insert_member(self.pid1, "r1", "i1:a5", 0)
        self.be.insert_member(self.pid1, "r1", "i2:a5", 1) # it's a trap
        pids = (self.pid1, self.pid2)
        a5_uri = "%s#a5" % self.url2
        self.be.rename_element(self.pid2, "a5", ANNOTATION, "renamed")
        self.be.rename_references(pids, a5_uri, "renamed")
        self.assertEqual("renamed", self.be.get_member(self.pid2, "r3", 1))
        self.assertEqual("i1:renamed", self.be.get_member(self.pid1, "r1", 0))
        # did you fall in the traps?
        self.assertEqual("a6", self.be.get_member(self.pid2, "r3", 0))
        self.assertEqual("i2:a5", self.be.get_member(self.pid1, "r1", 1))

        # now only on one package
        a5_uri = "%s#renamed" % self.url2
        self.be.rename_element(self.pid2, "renamed", ANNOTATION, "foo")
        self.be.rename_references((self.pid2,), a5_uri, "foo")
        self.assertEqual("foo", self.be.get_member(self.pid2, "r3", 1))
        self.assertEqual("i1:renamed", self.be.get_member(self.pid1, "r1", 0))

    def test_rename_refs_item(self):
        self.be.insert_item(self.pid2, "l3", "a6", 0) # it's a trap
        self.be.insert_item(self.pid2, "l3", "a5", 1)
        self.be.insert_item(self.pid1, "l1", "i1:a5", 0)
        self.be.insert_item(self.pid1, "l1", "i2:a5", 1) # it's a trap
        pids = (self.pid1, self.pid2)
        a5_uri = "%s#a5" % self.url2
        self.be.rename_element(self.pid2, "a5", ANNOTATION, "renamed")
        self.be.rename_references(pids, a5_uri, "renamed")
        self.assertEqual("renamed", self.be.get_item(self.pid2, "l3", 1))
        self.assertEqual("i1:renamed", self.be.get_item(self.pid1, "l1", 0))
        # did you fall in the traps?
        self.assertEqual("a6", self.be.get_item(self.pid2, "l3", 0))
        self.assertEqual("i2:a5", self.be.get_item(self.pid1, "l1", 1))

        # now only on one package
        a5_uri = "%s#renamed" % self.url2
        self.be.rename_element(self.pid2, "renamed", ANNOTATION, "foo")
        self.be.rename_references((self.pid2,), a5_uri, "foo")
        self.assertEqual("foo", self.be.get_item(self.pid2, "l3", 1))
        self.assertEqual("i1:renamed", self.be.get_item(self.pid1, "l1", 0))

    def test_rename_refs_tag(self):
        self.be.create_tag(self.pid2, "t4")
        self.be.associate_tag(self.pid2, "a5", "t3")
        self.be.associate_tag(self.pid1, "i1:a5", "i1:t3")
        self.be.associate_tag(self.pid1, "a1", "i1:t3")
        self.be.associate_tag(self.pid1, "a1", "i2:t3") # it's a trap
        self.be.associate_tag(self.pid1, "a1", "i1:t4") # it's a trap
        pids = (self.pid1, self.pid2)
        t3_uri = "%s#t3" % self.url2
        self.be.rename_element(self.pid2, "t3", TAG, "renamed")
        self.be.rename_references(pids, t3_uri, "renamed")
        a5_uri = "%s#a5" % self.url2
        self.assertEqual(
            frozenset([(self.pid1, "i1:renamed"), (self.pid2, "renamed"),]),
            frozenset(self.be.iter_tags_with_element(pids, a5_uri, ))
        )
        # did you fall in the traps?
        a1_uri = "%s#a1" % self.url1
        self.assertEqual(
            frozenset([(self.pid1, "i1:renamed"), (self.pid1, "i2:t3"),
                       (self.pid1, "i1:t4"),]),
            frozenset(self.be.iter_tags_with_element(pids, a1_uri, ))
        )

        # now only on one package
        t3_uri = "%s#renamed" % self.url2
        self.be.rename_element(self.pid2, "renamed", TAG, "foo")
        self.be.rename_references((self.pid2,), t3_uri, "foo")
        self.assertEqual(
            frozenset([(self.pid1, "i1:renamed"), (self.pid2, "foo"),]),
            frozenset(self.be.iter_tags_with_element(pids, a5_uri, ))
        )

    def test_rename_refs_tagged_elements(self):
        self.be.associate_tag(self.pid2, "a5", "t3")
        self.be.associate_tag(self.pid1, "i1:a5", "i1:t3")
        self.be.associate_tag(self.pid1, "i1:a6", "i1:t3") # it's a trap
        self.be.associate_tag(self.pid1, "i2:a5", "i1:t3") # it's a trap
        pids = (self.pid1, self.pid2)
        a5_uri = "%s#a5" % self.url2
        self.be.rename_element(self.pid2, "a5", ANNOTATION, "renamed")
        self.be.rename_references(pids, a5_uri, "renamed")
        t3_uri = "%s#t3" % self.url2
        self.assertEqual(
            frozenset([(self.pid1, "i1:renamed"), (self.pid2, "renamed"),
                       # did you fall in the traps?
                       (self.pid1, "i1:a6"), (self.pid1, "i2:a5"),]),
            frozenset(self.be.iter_elements_with_tag(pids, t3_uri, ))
        )

        # now only on one package
        a5_uri = "%s#renamed" % self.url2
        self.be.rename_element(self.pid2, "renamed", ANNOTATION, "foo")
        self.be.rename_references((self.pid2,), a5_uri, "foo")
        self.assertEqual(
            frozenset([(self.pid1, "i1:renamed"), (self.pid2, "foo"),
                       (self.pid1, "i1:a6"), (self.pid1, "i2:a5"),]),
            frozenset(self.be.iter_elements_with_tag(pids, t3_uri, ))
        )


class TestDeleteElement(TestCase):
    def setUp(self):
        self.url1 = IN_MEMORY_URL
        self.url2 = "%s;foo" % self.url1
        self.be, self.pid = create(P(self.url2))

    def tearDown(self):
        self.be.close(self.pid)
        del P._L[:] # not required, but saves memory

    def test_delete_media(self):
        self.be.create_media(self.pid, "m1", "http://example.com/m1.avi")
        try:
            self.be.delete_element(self.pid, "m1", MEDIA)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "m1"))
        self.assert_(not self.be.has_element(self.pid, "m1", MEDIA))

    def test_delete_annotation(self):
        self.be.create_media(self.pid, "m1", "http://example.com/m1.avi")
        self.be.create_annotation(self.pid, "a4", "m1", 10, 20)
        try:
            self.be.delete_element(self.pid, "a4", ANNOTATION)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "a4"))
        self.assert_(not self.be.has_element(self.pid, "a4", ANNOTATION))
        self.assertEqual(None, self.be.get_content(self.pid, "a4", ANNOTATION))

    def test_delete_relation(self):
        self.be.create_relation(self.pid, "r1")
        try:
            self.be.delete_element(self.pid, "r1", RELATION)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "r1"))
        self.assert_(not self.be.has_element(self.pid, "r1", RELATION))
        self.assertEqual(None, self.be.get_content(self.pid, "r1", RELATION))
        self.assertEqual(0, self.be.count_members(self.pid, "r1"))

    def test_delete_view(self):
        self.be.create_view(self.pid, "v1")
        try:
            self.be.delete_element(self.pid, "v1", VIEW)
        except Exception, e:
            raise
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "v1"))
        self.assert_(not self.be.has_element(self.pid, "v1", VIEW))
        self.assertEqual(None, self.be.get_content(self.pid, "v1", VIEW))

    def test_delete_resource(self):
        self.be.create_resource(self.pid, "R1")
        try:
            self.be.delete_element(self.pid, "R1", RESOURCE)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "R1"))
        self.assert_(not self.be.has_element(self.pid, "R1", RESOURCE))
        self.assertEqual(None, self.be.get_content(self.pid, "R1", RESOURCE))

    def test_delete_tag(self):
        self.be.create_tag(self.pid, "t1")
        try:
            self.be.delete_element(self.pid, "t1", TAG)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "t1"))
        self.assert_(not self.be.has_element(self.pid, "t1", TAG))

    def test_delete_list(self):
        self.be.create_list(self.pid, "l1")
        try:
            self.be.delete_element(self.pid, "l1", LIST)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "l1"))
        self.assert_(not self.be.has_element(self.pid, "l1", LIST))
        self.assertEqual(0, self.be.count_items(self.pid, "l1"))

    def test_delete_query(self):
        self.be.create_query(self.pid, "q1")
        try:
            self.be.delete_element(self.pid, "q1", QUERY)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "q1"))
        self.assert_(not self.be.has_element(self.pid, "q1", QUERY))
        self.assertEqual(None, self.be.get_content(self.pid, "q1", QUERY))

    def test_delete_import(self):
        self.be.create_import(self.pid, "i1",
                              "http://example.com/advene/db", "",)
        try:
            self.be.delete_element(self.pid, "i1", IMPORT)
        except Exception, e:
            self.fail(e) # raised by delete_element
        self.assert_(not self.be.has_element(self.pid, "i1"))
        self.assert_(not self.be.has_element(self.pid, "i1", IMPORT))


class TestRobustIterations(TestCase):

    pid1 = ""
    pid2 = ";foo"
    pid3 = ";bar"
    url1 = TestHandleElements.url1
    url2 = TestHandleElements.url2
    url3 = IN_MEMORY_URL + pid3
    pids = (pid1, pid2)
    i2_url = "http://example.com/advene/db2#R5"

    iter_methods = {
        "iter_references_with_import": [pid1, "i1",],
        "iter_medias": [pids,],
        "iter_annotations": [pids,],
        "iter_relations": [pids,],
        "iter_views": [pids,],
        "iter_resources": [pids,],
        "iter_tags": [pids,],
        "iter_lists": [pids,],
        "iter_queries": [pids,],
        "iter_imports": [pids,],
        "iter_contents_with_schema": [pids, "%s#R3" % url2,],
        "iter_meta": [pid1, "", ""],
        "iter_members": [pid1, "r1",],
        "iter_relations_with_member": [pids, "%s#a1" % url1,],
        "iter_items": [pid1, "l1",],
        "iter_lists_with_item": [pids, "%s#r1" % url1,],
        "iter_tags_with_element": [pids, "%s#a1" % url1,],
        "iter_elements_with_tag": [pids, "%s#t1" % url1,],
        "iter_tagging": [pids, "%s#a1" % url1, "%s#t1" % url1,],
    }

    update_methods = {
        "update_uri": [pid1, "urn:1234",],
        "close": None, # rather tested with bind and create
        "create_media": [pid1, "mX", "file:///tmp/mX.ogm",],
        "create_annotation": [pid1, "aX", "m1", 0, 10,],
        "create_relation": [pid1, "rX",],
        "create_view": [pid1, "vX",],
        "create_resource": [pid1, "RX",],
        "create_tag": [pid1, "tX",],
        "create_list": [pid1, "lX",],
        "create_query": [pid1, "qX",],
        "create_import": [pid1, "iX", "file:///tmp/pkg", ""],
        "update_media": [pid1, "m1", "file:///tmp/mX.ogm",],
        "update_annotation": [pid1, "a1", "m1", 0, 666,],
        "update_import": [pid1, "i1", "file:///tmp/pkg", ""],
        "rename_element": [pid1, "i1", IMPORT, "renamed",],
        "rename_references": [pids, "%s#R5" % i2_url, "renamed",],
        "delete_element": [pid2, "q3", QUERY,],
        "update_content": [pid1, "a1", ANNOTATION, "test/html", "", "",],
        "set_meta": [pid1, "", "", "pac#test2", "bar",],
        "insert_member": [pid1, "r1", "a3", -1],
        "update_member": [pid1, "r1", "a4", 0],
        "remove_member": [pid1, "r1", 0],
        "insert_item": [pid1, "l1", "r2", -1],
        "update_item": [pid1, "l1", "r2", 0],
        "remove_item": [pid1, "l1", 0],
        "associate_tag": [pid1, "a2", "t1",],
        "dissociate_tag": [pid1, "t1", "t1",],
    }

    def setUp(self):
        # reuse the bunch of code defined in TestHandleElements:
        TestHandleElements.__dict__["setUp"](self)
        try:
            b = self.be
            # populate package to get non empty lists
            b.set_meta(self.pid1, "", "", "pac#test", "foo")
            b.insert_member(self.pid1, "r1", "a1", -1)
            b.insert_member(self.pid1, "r1", "i1:a5", -1)
            b.insert_item(self.pid1, "l1", "r1", -1)
            b.insert_item(self.pid1, "l1", "i1:r3", -1)
            b.insert_item(self.pid1, "l1", "i2:R5", -1)
            b.associate_tag(self.pid1, "a1",    "t1")
            b.associate_tag(self.pid1, "a1",    "i1:t3")
            b.associate_tag(self.pid1, "i1:a5", "t1")
            b.update_content(self.pid1, "a1", ANNOTATION,
                             "text/plain", "", "i1:R3",)
            b.update_content(self.pid2, "r3", RELATION,
                             "text/plain", "", "R3",)
            b.update_content(self.pid2, "a5", ANNOTATION,
                             "text/plain", "", "i3:R5",)
        except:
            self.tearDown()
            raise

    def tearDown(self):
        TestHandleElements.__dict__["tearDown"](self)

    def test_all_update_during_iter(self):
        # This method actually performs several tests and call setUp and 
        # tearDown between each; this is a bit dirty, but was the fastest way
        # to do it...
        # (beside, meta-programming would not have been very legible... ;)

        for n, args in self.iter_methods.iteritems():
            b = self.be
            m = getattr(b, n)
            ref = list(m(*args))
            assert ref, n # lists should be non-empty
            test = []
            for i in m(*args):
                if len(test) == 1:
                    for n2, args2 in self.update_methods.iteritems():
                        if args2 is None: continue # special case for close
                        try:
                            getattr(b, n2)(*args2)
                        except InternalError, e:
                            self.fail("%s during %s raise:\n %s" % (n2, n, e))
                        except sqlite.Error, e:
                            self.fail("%s during %s raise:\n %s" % (n2, n, e))
                    create(P(IN_MEMORY_URL+";bar")); self.be.close(";bar")
                    bind(P(IN_MEMORY_URL+";bar")); self.be.close(";bar")
                test.append(i)
            self.assertEquals(ref, test, n)
            self.tearDown()
            self.setUp()

    def test_independant_iterations(self):
        for n, args in self.iter_methods.iteritems():
            b = self.be
            m = getattr(b, n)
            ref = list(m(*args))
            assert ref, n # lists should be non-empty
            for n2, args2 in self.iter_methods.iteritems():
                test = []
                for i in m(*args):
                    if len(test) == 1:
                       m2 = getattr(b, n2)
                       list(m2(*args2)) # try to parasit enclosing iteration
                    test.append(i)
                self.assertEquals(ref, test, n)


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
