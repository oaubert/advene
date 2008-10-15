"""
I am the reference API for advene backends.
"""

from pysqlite2 import dbapi2 as sqlite
from os.path   import exists, isdir, join, split

from advene.model.core.PackageElement import STREAM, ANNOTATION, RELATION, VIEW, RESOURCE, BAG, FILTER, IMPORT

class SqliteBackend (object):
    @staticmethod
    def claims_for_create (url):
        """
        Is this backend able to create a package to the given URL ?
        """
        if url[:7] != "sqlite:": return False
        url = url[7:]

        if url == ":memory:": return True

        if exists (url): return False
        url = split (url)[0]
        if not isdir (url): return False
        return True

    @staticmethod
    def create (url):
        """
        Create a SqliteBackend instance for a new URL which will be created.
        """
        assert (SqliteBackend.claims_for_create (url))

        conn = sqlite.connect (url[7:])
        f = open (join (split (__file__)[0], "init.sql"))
        sql = f.read()
        f.close()
        for query in sql.split(";"):
            conn.execute (query)
        return SqliteBackend (conn, False, False)

    @staticmethod
    def claims_for_bind (url):
        """
        Is this backend able to bind to the given URL ?
        """
        if url[:7] != "sqlite:": return False
        url = url[7:]

        if url == ":memory:": return False

        try:
            conn = sqlite.connect (url)
            conn.close()
        except sqlite.OperationalError:
            return False
        return True

    @staticmethod
    def bind (url, readonly=False, force=False):
        """
        Create a SqliteBackend instance from the existing URL.
        @param url: the URL to open
        @param readonly: should the package be open in read-only mode?
        @param force: should the package be open even if it is locked?
        """
        assert (SqliteBackend.claims_for_bind (url))
        if force:
            raise Exception ("This backend can not force access to locked "
                             "package")
        conn = sqlite.connect (url[7:])
        return SqliteBackend (conn, readonly, force)

    def __init__ (self, conn, readonly, force):
        """
        Is not part of the interface. Instances must be created either with
        the L{create} or the L{bind} static methods.

        Create a backend, and bind it to the given URL.
        """

        self._conn = conn
        self._readonly = readonly

    def close (self):
        self._conn.close()


    def get_annotation_ids (self):
        "Guarantees that annotations are sorted by begin, end, stream"
        c = self._conn.execute ("select id from Annotations order by fbegin, fend, stream")
        for a in c: yield a[0]

    def get_relation_ids (self):
        c = self._conn.execute ("select id from Relations")
        for a in c: yield a[0]

    def get_view_ids (self):
        c = self._conn.execute ("select id from Views")
        for a in c: yield a[0]

    def get_resource_ids (self):
        c = self._conn.execute ("select id from Resources")
        for a in c: yield a[0]

    def get_filter_ids (self):
        c = self._conn.execute ("select id from Filters")
        for a in c: yield a[0]

    def get_bag_ids (self):
        c = self._conn.execute ("select id from Bags")
        for a in c: yield a[0]

    def get_import_ids (self):
        c = self._conn.execute ("select id from Imports")
        for a in c: yield a[0]

    def construct_imports_dict (self):
        c = self._conn.execute ("select id, url from Imports")
        return dict (c)

    def _create_element_cursor (self, id):
        """
        Makes common control and return the cursor to be used.
        Starts a transaction that must be commited by caller.
        """
        c = self._conn.cursor()
        # check that the id is not in use
        c.execute ("select id from Elements where id=?", (id,))
        assert (c.fetchone() is None)
        try:
            c.execute ("insert into Elements(id) values (?)", (id,))
            return c
        except sqlite.Error:
            self._conn.rollback()

    def create_stream (self, id, uri):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Streams(id,url) values (?,?)", (id, uri))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()

    def create_annotation (self, id, sid, begin, end):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Annotations(id,stream,fbegin,fend) values (?,?,?,?)",
                       (id, sid, begin, end))
            c.execute ("insert into Contents(element,mimetype,data) values (?,?,?)",
                       (id, "text/plain", ""))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()

    def create_relation (self, id):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Relations(id) values (?)", (id,))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()

    def create_view (self, id):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Views(id) values (?)", (id,))
            c.execute ("insert into Contents(element,mimetype,data) values (?,?,?)", (id, "text/plain", ""))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()

    def create_resource (self, id):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Resources(id) values (?)", (id,))
            c.execute ("insert into Contents(element,mimetype,data) values (?,?,?)", (id, "text/plain", ""))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()

    def create_bag (self, id):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Bags(id) values (?)", (id,))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()

    def create_filter (self, id):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Filters(id) values (?)", (id,))
            c.execute ("insert into Contents(element,mimetype,data) values (?,?,?)",
                       (id, "text/plain", ""))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()

    def create_import (self, id, uri):
        try:
            c = self._create_element_cursor (id)
            c.execute ("insert into Streams(id,url) values (?,?)", (id, uri))
        except sqlite.Error:
            self._conn.rollback()
        self._conn.commit()


    def construct_element (self, id):
        # TODO would it be better to let the caller specify the type of element
        # or would it be wise to store in table Elements the type of element?

        # TODO adjuts parameters (filters on views and bags, etc.)

        c = self._conn.cursor()
        c.execute ("select id, url from Streams where id = ?", (id,))
        d = c.fetchone ()
        if d is not None: return STREAM, (d[1],)

        c.execute (
            "select id,stream,fbegin,fend from Annotations where id = ?",
            (id,),
        )
        d = c.fetchone ()
        if d is not None: return ANNOTATION, (d[1], d[2], d[3])

        c.execute ("select id from Relations where id = ?", (id,))
        d = c.fetchone ()
        if d is not None: return RELATION, ()

        c.execute ("select id from Views where id = ?", (id,))
        d = c.fetchone ()
        if d is not None: return VIEW, ()

        c.execute ("select id from Resources where id = ?", (id,))
        d = c.fetchone ()
        if d is not None: return RESOURCE, ()

        c.execute ("select id from Filters where id = ?", (id,))
        d = c.fetchone ()
        if d is not None: return FILTER, ()

        c.execute ("select id from Bags where id = ?", (id,))
        d = c.fetchone ()
        if d is not None: return BAG, ()

        c.execute ("select id,url from Imports where id = ?", (id,))
        d = c.fetchone ()
        if d is not None: return IMPORT, (d[1],)


    def get_content (self, id, element_type):
        """
        In this implementation, element_type will always be ignored.
        """
        # TODO manage schema and url
        cur = self._conn.execute (
            "select mimetype,data from Contents where element = ?",
            (id,),
        )
        return cur.fetchone() or (None, None)


    def update_content (self, content):
        # TODO manage schema and url
        cur = self._conn.execute (
            "update Contents set mimetype=?, data=? where element=?",
            (content.mimetype, content.data, content.owner_element.id),
        )
        self._conn.commit()

    def get_meta (self, id, element_type, key):
        """
        id should be an empty string if package metadata is required, and element_type will be ignored.

        In this implementation, element_type will always be ignored.
        """
        c = self._conn.execute ("select value from Meta where element = ? and key = ?", (id, key))
        d = c.fetchone()
        if d is None: return None
        else:         return d[0]

    def set_meta (self, id, element_type, key, val):
        """
        id should be an empty string if package metadata is required, and element_type will be ignored.

        In this implementation, element_type will always be ignored.
        """
        c = self._conn.execute ("select value from Meta where element = ? and key = ?", (id, key))
        d = c.fetchone()

        if d is None:
            if val is not None:
                self._conn.execute ("insert into Meta (element, key, value) values (?,?,?)",
                                    (id, key, val))
        else:
            if val is not None:
                self._conn.execute ("update Meta set value=? where element=? and key=?", (val, id, key))
            else:
                self._conn.execute ("delete from Meta where element=? and key=?", (id, key))
        self._conn.commit()
