from unittest import TestCase, main

from pysqlite2 import dbapi2 as sqlite
from os        import tmpnam, unlink
from os.path   import exists
from warnings  import filterwarnings

from advene.model.backends.sqlite.SqliteBackend import (
    claims_for_create,
    create,
    claims_for_bind,
    bind,
    IN_MEMORY_URL,
)

filterwarnings ("ignore", "tmpnam is a potential security risk to your program")

class Test_Create (TestCase):
    def setUp (self):
        self.filename = tmpnam()
        self.url1 = "file:%s" % self.filename
        self.url2 = "%s#foo" % self.url1

    def tearDown (self):
        if exists (self.filename):
            unlink (self.filename)

    def _touch_filename (self):
        cx = sqlite.connect (self.filename)
        cx.execute ("create table a(b);")
        cx.close()

    def test_claim_wrong_scheme (self):
        self.assert_ (
            not claims_for_create ("http://example.com/advene/db")
        )

    def test_claim_wrong_path (self):
        self.assert_ (
            not claims_for_create ("%s/foo" % self.url1)
        )

    def test_claim_existing_file (self):
        self._touch_filename()
        self.assert_ (
            not claims_for_create (self.url1)
        )

    def test_claim_new_file (self):
        self.assert_ ( 
            claims_for_create (self.url1)
        )

    def test_claim_new_file_with_fragment (self):
        self.assert_ ( 
            claims_for_create (self.url2)
        )

    def test_claim_existing_fragment (self):
        create (self.url2)
        self.assert_ (
            not claims_for_create ("%s#foo" % self.url1)
        )

    def test_claim_new_fragment (self):
        create (self.url2)
        self.assert_ (
            claims_for_create ("%s#bar" % self.url1)
        )

    def test_claim_sqlite_scheme (self):
        self.assert_ ( 
            claims_for_create ("sqlite:%s" % tmpnam())
        )

    def test_claim_memory (self):
        self.assert_ ( 
            claims_for_create (IN_MEMORY_URL)
        )

    def test_create_without_fragment (self):
        create (self.url1)
        self.assert_ (
            claims_for_bind (self.url1)
        )

    def test_create_with_fragment (self):
        create (self.url2)
        self.assert_ (
            claims_for_bind (self.url2)
        )

    def test_create_new_fragment (self):
        create (self.url1)
        create (self.url2)
        self.assert_ (
            claims_for_bind (self.url2)
        )

    def test_create_sqlite_scheme (self):
        url = "sqlite:%s#foo" % self.filename
        create (url)
        self.assert_ (
            claims_for_bind (url)
        )

    def test_create_in_memory (self):
        b,p = create (IN_MEMORY_URL)
        self.assert_ (b._path, ":memory:")


class Test_Bind (TestCase):
    def setUp (self):
        self.filename = tmpnam()
        self.url1 = "file:%s" % self.filename
        self.url2 = "%s#foo" % self.url1
        create (self.url2)

    def tearDown (self):
        if exists (self.filename):
            unlink (self.filename)

    def test_claim_non_existing (self):
        unlink (self.filename)
        self.assert_ (
            not claims_for_bind (self.url2)
        )

    def test_claim_wrong_format (self):
        f = open(self.filename, 'w'); f.write("foo"); f.close()
        self.assert_ (
            not claims_for_bind (self.url2)
        )

    def test_claim_wrong_db_schema (self):
        unlink(self.filename)
        cx = sqlite.connect (self.filename)
        cx.execute("create table a(b);")
        cx.close()
        self.assert_ (
            not claims_for_bind (self.url2)
        )

    def test_claim_wrong_backend_version (self):
        cx = sqlite.connect (self.filename)
        cx.execute("update Version set version='foobar'")
        cx.commit()
        cx.close()
        self.assert_ (
            not claims_for_bind (self.url2)
        )

    def test_claim_wrong_fragment (self):
        self.assert_ (
            not claims_for_bind ("%s#bar" % self.url1)
        )

    def test_claim_without_fragment (self):
        self.assert_ (
            claims_for_bind (self.url1)
        )
    
    def test_claim_with_fragment (self):
        self.assert_ (
            claims_for_bind (self.url2)
        )

    def test_claim_with_other_fragment (self):
        url3 = "%s#bar" % self.url1
        create (url3)
        self.assert_ (
            claims_for_bind (url3)
        )

    def test_claim_sqlite_scheme (self):
        self.assert_ (
            claims_for_bind ("sqlite:%s" % self.filename)
        )

    def test_bind_without_fragment (self):
        bind (self.url1)

    def test_bind_with_fragment (self):
        bind (self.url2)

    def test_bind_with_other_fragment (self):
        url3 = "%s#bar" % self.url1
        create (url3)
        bind (url3)


class Test_Cache (TestCase):
    def setUp (self):
        self.filename = tmpnam()
        self.url1 = "file:%s" % self.filename
        self.url2 = "%s#foo" % self.url1
        self.url3 = "%s#bar" % self.url1
        self.created = create (self.url2)

    def tearDown (self):
        self.created = None
        unlink (self.filename)

    def test_same_url (self):
        bound = bind (self.url2)
        self.assertEqual (self.created, bound)

    def test_add_fragment (self):
        newly_created = create (self.url3)
        self.assertEqual (self.created[0], newly_created[0])

    def test_different_fragment (self):
        create (self.url3)
        bound = bind (self.url3)
        self.assertEqual (self.created[0], bound[0])

    def test_no_fragment (self):
        bound = bind (self.url1)
        self.assertEqual (self.created[0], bound[0])

    def test_forget (self):
        old_id = id (self.created[0])
        self.created = None
        bound = bind (self.url2)
        self.assertNotEqual (old_id, id (bound[0]))

if __name__ == "__main__":
     main()
     print list (interclass (l1, l2, l3, l4))
