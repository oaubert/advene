"""
I am the reference API for advene backends.
"""

from pysqlite2 import dbapi2 as sqlite
from os.path   import exists, isdir, join, split
from uuid      import uuid4
from weakref   import WeakValueDictionary

import re

from advene.model.core.PackageElement import MEDIA, ANNOTATION, RELATION, VIEW, RESOURCE, TAG, LIST, QUERY, IMPORT

BACKEND_VERSION = "0.1"

IN_MEMORY_URL = "sqlite::memory:"


def claims_for_create (url):
    """
    Is this backend able to create a package to the given URL ?
    """
    if url[:5] != "file:" and url[:7] != "sqlite:": return False

    path, pkgid = _strip_url (url)

    if path == ":memory:":
        be = _cache.get (":memory:")
        if be is None:
            # in_memory backend is not in used, so it will be created
            return True
        else:
            # in_memory backend is in use,
            # so existing packages can not be created
            return not _contains_package (be._conn, pkgid)

    # persistent (file) database
    if not exists (path):
        # check that file can be created
        path = split (path)[0]
        if not isdir (path): return False
        return True
    else:
        # check that file is a correct database (created by this backend)
        cx = _get_connection (path)
        if cx is None: return False
        # check that file does not already contains the required pkg
        # NB: in ":memory:", cx is the connection to the cached backend
        r = not _contains_package (cx, pkgid)
        cx.close()
        return r

def create (url):
    """
    Create a _SqliteBackend instance for a new URL which will be created.

    Return
    """
    assert (claims_for_create (url))

    path, pkgid = _strip_url (url)

    b = _cache.get (path)
    if b is None:
        # check the following *before* sqlite.connect creates the file!
        must_init = (path == ":memory:" or not exists(path))
        conn = sqlite.connect (path)
        if must_init:
            # initialize database
            f = open (join (split (__file__)[0], "init.sql"))
            sql = f.read()
            f.close()
            try:
                for query in sql.split(";"):
                    conn.execute (query)
            except sqlite.OperationalError, e:
                raise RuntimeError, "%s - SQL:\n%s" % (e, query)
            conn.execute ("INSERT INTO Version VALUES (?)", (BACKEND_VERSION,))
            conn.execute ("INSERT INTO Packages VALUES (?,?)",
                          (_DEFAULT_PKGID, str(uuid4()),))
            conn.commit()
        b = _SqliteBackend (path, conn, False, False)
        _cache[path] = b
    else:
        conn = b._conn

    if pkgid != _DEFAULT_PKGID:
        conn.execute ("INSERT INTO Packages VALUES (?,?)",
                      (pkgid, str(uuid4()),))
        conn.commit()


    return b, pkgid

def claims_for_bind (url):
    """
    Is this backend able to bind to the given URL ?
    """
    if url[:5] != "file:" and url[:7] != "sqlite:": return False

    path, pkgid = _strip_url (url)

    if path == ":memory:":
        be = _cache.get (":memory:")
        if be is None:
            # in_memory backend is not in used, so it must be created
            return False
        else:
            # in_memory backend is in use, exitsing package can be bound
            return _contains_package (be._conn, pkgid)

    # persistent (file) database
    if not exists (path):
        return False
    else:
        # check that file is a correct database (created by this backend)
        cx = _get_connection (path)
        if cx is None: return False
        # check that file does contains the required pkg
        r = _contains_package (cx, pkgid)
        cx.close()
        return r

def bind (url, readonly=False, force=False):
    """
    Create a _SqliteBackend instance from the existing URL.
    @param url: the URL to open
    @param readonly: should the package be open in read-only mode?
    @param force: should the package be open even if it is locked?
    """
    assert (claims_for_bind (url))
    if force:
        raise Exception ("This backend can not force access to locked "
                         "package")

    if url[:5] != "file:" and url[:7] != "sqlite:": return False

    path, pkgid = _strip_url (url)

    b = _cache.get (path)
    if b is None:
        conn = sqlite.connect (path)
        b = _SqliteBackend (path, conn, False, False)
        _cache[path] = b

    return b, pkgid


_cache = WeakValueDictionary()

_DEFAULT_PKGID = ""

def _strip_url (url):
    """
    Strip URL from its scheme ("file:" or "sqlite:") and separate path and
    fragment.
    """
    if url[0] == "f": # file:
        scheme = 5
    else: # sqlite:
        scheme = 7
    sharp = url.find('#')
    if sharp != -1:
        return url[scheme:sharp], url[sharp+1:]
    else:
        return url[scheme:], _DEFAULT_PKGID

def _get_connection (path):
    try:
        cx = sqlite.connect (path)
        c = cx.execute ("select version from Version")
        for v in c:
            if v[0] != BACKEND_VERSION: return None
        return cx
        
    except sqlite.DatabaseError:
        return None
    except sqlite.OperationalError:
        return None

def _contains_package (cx, pkgid):
    if pkgid == _DEFAULT_PKGID:
        return True
    c = cx.execute ("select id from Packages where id = ?", (pkgid,))
    for i in c:
        return True
    return False


class _SqliteBackend (object):

    def __init__ (self, path, conn, readonly, force):
        """
        Is not part of the interface. Instances must be created either with
        the L{create} or the L{bind} static methods.

        Create a backend, and bind it to the given URL.
        """

        self._path = path
        self._conn = conn
        conn.create_function ("regexp", 2,
                              lambda l,r: re.search(r,l) is not None )
        self._readonly = readonly

    def __del__ (self):
        #print "=== About to collect SqliteBackend", self._path
        try:
            self._conn.close()
        except sqlite.OperationalError:
            pass

    def close (self):
        self._conn.close()

     # retrieval

    def has_element (self, package_id, id, element_type=None):
        """
        Return True if the given package has an element with the given id.
        If element_type is provided, only return true if the element has the
        the given type.
        """
        q = "SELECT typ FROM Elements WHERE package = ? and id = ?"
        for i in self._conn.execute (q, (package_id, id,)):
            return element_type is None or i[0] == element_type
        return False

    def get_element (self, package_id, id):
        """
        Return the tuple describing a given element, None if that element does
        not exist.
        """

        q = "SELECT typ FROM Elements WHERE package = ? AND id = ?"
        l = list (self._conn.execute (q, (package_id, id,)))
        if len (l) == 0:
            return None
        t = l[0][0]
        if t == MEDIA:
            return get_medias (id=id).next()
        elif t == ANNOTATION:
            return get_annotations (id=id).next()
        elif t == IMPORT:
            return get_imports (id=id).next()
        else:
            return (t, id)

    def get_medias (self, package_ids,
                     id=None,  id_regexp=None,
                    url=None, url_regexp=None,
                   ):
        """
        Yield tuples of the form (MEDIA, id, url;).
        """
        assert ( id is None  or   id_regexp is None)
        assert (url is None  or  url_regexp is None)

        q = "SELECT ?, id, url FROM Medias WHERE package in ("
        args = [MEDIA,]

        for p in package_ids:
            q += "?,"
            args.append (p)
        q += ")"

        if id is not None:
            q += " AND id = ?"
            args.append (id)
        if id_regexp is not None:
            q += " AND id REGEXP ?"
            args.append (id_regexp)
        if url is not None:
            q += " AND url = ?"
            args.append (url)
        if url_regexp is not None:
            q += " AND url REGEXP ?"
            args.append (url_regexp)

        for i in self._conn.execute (q, args): yield i

    def get_annotations (self, package_ids,
                            id=None,    id_regexp=None,
                         media=None, media_regexp=None,
                         begin=None,    begin_min=None, begin_max=None,
                           end=None,      end_min=None,   end_max=None,
                        ):
        """
        Yield tuples of the form (ANNOTATION, id, media, begin, end,).
        """
        assert (   id is None  or     id_regexp is None)
        assert (media is None  or  media_regexp is None)
        assert (begin is None  or  begin_min is None and begin_max is None)
        assert (  end is None  or    end_min is None and   end_max is None)

        q = """SELECT ?, id, media, fbegin, fend FROM Annotations
               WHERE package in ("""
        args = [ANNOTATION,]

        for p in package_ids:
            q += "?,"
            args.append (p)
        q += ")"

        if id is not None:
            q += " AND id = ?"
            args.append (id)
        if id_regexp is not None:
            q += " AND id REGEXP ?"
            args.append (id_regexp)
        if media is not None:
            q += " AND media = ?"
            args.append (media)
        if media_regexp is not None:
            q += " AND media regexp = ?"
            args.append (media_regexp)
        if begin is not None:
            q += " AND fbegin = ?"
            args.append (begin)
        if begin_min is not None:
            q += " AND fbegin >= ?"
            args.append (begin_min)
        if begin_max is not None:
            q += " AND fbegin <= ?"
            args.append (begin_max)
        if end is not None:
            q += " AND fend = ?"
            args.append (end)
        if end_min is not None:
            q += " AND fend >= ?"
            args.append (end_min)
        if end_max is not None:
            q += " AND fend <= ?"
            args.append (end_max)

        for i in self._conn.execute (q, args): yield i

    def get_relations (self, package_ids, id=None, id_regexp=None):
        """
        Yield tuples of the form (RELATION, id,).
        """
        return self._get_simple_elements (package_ids, RELATION, id, id_regexp)

    def get_views (self, package_ids, id=None, id_regexp=None):
        """
        Yield tuples of the form (VIEW, id,).
        """
        return self._get_simple_elements (package_ids, VIEW, id, id_regexp)

    def get_resources (self, package_ids, id=None, id_regexp=None):
        """
        Yield tuples of the form (RESOURCE, id,).
        """
        return self._get_simple_elements (package_ids, RESOURCE, id, id_regexp)

    def get_tags (self, package_ids, id=None, id_regexp=None):
        """
        Yield tuples of the form (TAG, id,).
        """
        return self._get_simple_elements (package_ids, TAG, id, id_regexp)

    def get_lists (self, package_ids, id=None, id_regexp=None):
        """
        Yield tuples of the form (LIST, id,).
        """
        return self._get_simple_elements (package_ids, LIST, id, id_regexp)

    def get_querys (self, package_ids, id=None, id_regexp=None):
        """
        Yield tuples of the form (QUERY, id,).
        """
        return self._get_simple_elements (package_ids, QUERY, id, id_regexp)

    def get_imports (self, package_ids,
                       id=None,  id_regexp=None,
                      url=None, url_regexp=None,
                     uuid=None,
                    ):
        """
        Yield tuples of the form (IMPORT, id, url, uuid).
        """
        assert ( id is None  or   id_regexp is None)
        assert (url is None  or  url_regexp is None)

        q = "SELECT ?, id, url, uuid FROM Imports WHERE package in ("
        args = [IMPORT,]

        for p in package_ids:
            q += "?,"
            args.append (p)
        q += ")"

        if id is not None:
            q += " AND id = ?"
            args.append (id)
        if id_regexp is not None:
            q += " AND id REGEXP ?"
            args.append (id_regexp)
        if url is not None:
            q += " AND url = ?"
            args.append (url)
        if url_regexp is not None:
            q += " AND url REGEXP ?"
            args.append (url_regexp)
        if uuid is not None:
            q += " AND uuid = ?"
            args.append (uuid)

        for i in self._conn.execute (q, args): yield i

    def _get_simple_elements (self, package_ids, element_type,
                              id=None, id_regexp=None):
        """
        Yield tuples of the form (element_type, id,).
        Useful for all elements that have that form of tuple.
        """
        assert (id is None  or  id_regexp is None)

        q = "SELECT typ, id FROM Elements WHERE package in ("
        args = []

        for p in package_ids:
            q += "?,"
            args.append (p)
        q += ")"

        q += " AND typ = ?"
        args.append (element_type)

        if id is not None:
            q += " AND id = ?"
            args.append (id)
        if id_regexp is not None:
            q += " AND id REGEXP ?"
            args.append (id_regexp)

        for i in self._conn.execute (q, args): yield i

    # content

    def get_content (self, package_id, id, element_type):
        """
        In this implementation, element_type will always be ignored.
        """
        # TODO manage schema and url
        q = """SELECT mimetype, data FROM Contents
               WHERE package = ? AND element = ?"""
        cur = self._conn.execute (q, (package_id, id,))
        return cur.fetchone() or (None, None)

    def update_content (self, package_id, content):
        # TODO manage schema and url
        q = """UPDATE Contents SET mimetype = ?, data = ?
               WHERE package = ? AND element = ?"""
        args = (
            content.mimetype,
            content.data,
            package_id,
            content.owner_element.id,
        )
        cur = self._conn.execute (q, args)
        self._conn.commit()

    # meta-data

    def iter_meta (self, package_id, id, element_type, key):
        """
        Iter over the metadata, sorting keys in alphabetical order.

        In this implementation, element_type will always be ignored.
        """
        q = """SELECT key, value FROM Meta
               WHERE package = ? AND element = ? ORDER BY key"""
        c = self._conn.execute (q, (package_id, id))
        d = c.fetchone()
        while d is not None:
            yield d[0],d[1]
            d = c.fetchone()

    def get_meta (self, package_id, id, element_type, key):
        """
        id should be an empty string if package metadata is required,
        and element_type will be ignored.

        In this implementation, element_type will always be ignored.
        """
        q = """SELECT value FROM Meta
               WHERE package = ? AND element = ? AND KEY = ?"""
        c = self._conn.execute (q, (package_id, id, key,))
        d = c.fetchone()
        if d is None: return None
        else:         return d[0]

    def set_meta (self, package_id, id, element_type, key, val):
        """
        id should be an empty string if package metadata is required,
        and element_type will be ignored.

        In this implementation, element_type will always be ignored.
        """
        q = """SELECT value FROM Meta
               WHERE package = ? AND element = ? and key = ?"""
        c = self._conn.execute (q, (package_id, id, key))
        d = c.fetchone()

        if d is None:
            if val is not None:
                q = """INSERT INTO Meta (package, element, key, value)
                       VALUES (?,?,?,?)"""
                self._conn.execute (q, (package_id, id, key, val))
        else:
            if val is not None:
                q = """UPDATE Meta SET value = ?
                       WHERE package = ? AND element = ? AND key = ?"""
                self._conn.execute (q, (val, package_id, id, key))
            else:
                q = """DELETE FROM Meta
                       WHERE package = ? AND element = ? AND key = ?"""
                self._conn.execute (q, (package_id, id, key))
        self._conn.commit()

   # creation

    def _create_element_cursor (self, package_id, id, element_type):
        """
        Makes common control and return the cursor to be used.
        Starts a transaction that must be commited by caller.
        """
        c = self._conn.cursor()
        # check that the id is not in use
        c.execute ("SELECT id FROM Elements WHERE package = ? AND id = ?",
                   (package_id, id,))
        if c.fetchone() is not None:
            raise Exception, "id in use"
            # TODO use a specific Exception class
        c.execute ("INSERT INTO Elements VALUES (?,?,?)",
                   (package_id, id, element_type))
        return c

    def create_media (self, package_id, id, uri):
        try:
            c = self._create_element_cursor (package_id, id, MEDIA)
            c.execute ("INSERT INTO Medias VALUES (?,?,?)",
                       (package_id, id, uri))
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "could not insert"
            # TODO use a specific Exception class

    def create_annotation (self, package_id, id, media, begin, end):
        try:
            c = self._create_element_cursor (package_id, id, ANNOTATION)
            c.execute ("INSERT INTO Annotations VALUES (?,?,?,?,?)",
                       (package_id, id, media, begin, end))
            c.execute ("INSERT INTO Contents VALUES (?,?,?,?)",
                       (package_id, id, "text/plain", ""))
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "could not insert"
            # TODO use a specific Exception class

    def create_relation (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, RELATION)
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "error in creating"
            # TODO use a specific class of Exception

    def create_view (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, VIEW)
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "error in creating"
            # TODO use a specific class of Exception

    def create_resource (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, RESOURCE)
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "error in creating"
            # TODO use a specific class of Exception

    def create_tag (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, TAG)
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "error in creating"
            # TODO use a specific class of Exception

    def create_list (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, LIST)
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "error in creating"
            # TODO use a specific class of Exception

    def create_query (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, QUERY)
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "error in creating"
            # TODO use a specific class of Exception

    def create_import (self, package_id, id, uri, uuid):
        try:
            c = self._create_element_cursor (package_id, id, IMPORT)
            c.execute ("INSERT INTO Imports VALUES (?,?,?,?)",
                       (package_id, id, uri, uuid))
            self._conn.commit()
        except sqlite.Error:
            self._conn.rollback()
            raise Exception, "error in creating"
            # TODO use a specific class of Exception

