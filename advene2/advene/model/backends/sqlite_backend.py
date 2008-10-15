"""
I am the reference API for advene backends.
"""

#TODO: the backend does not ensure an exclusive access to the sqlite file.
#      this is contrary to the backend specification.
#      We should explore sqlite locking and use it (seems that multiple
#      read-only access is possible), but also the possibility to lock 
#      differently each package in the database.

from pysqlite2 import dbapi2 as sqlite
from os.path   import exists, isdir, join, split
from weakref   import WeakValueDictionary

import re

from advene.model import ModelError
from advene.model.backends import InternalError
from advene.model.core.PackageElement import MEDIA, ANNOTATION, RELATION, VIEW, RESOURCE, TAG, LIST, QUERY, IMPORT


BACKEND_VERSION = "0.1"

IN_MEMORY_URL = "sqlite::memory:"


def claims_for_create (url):
    """
    Is this backend able to create a package to the given URL ?
    """
    if url[:7] != "sqlite:": return False

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
    assert (claims_for_create (url)), "url = %r" % url

    path, pkgid = _strip_url (url)

    b = _cache.get (path)
    if b is None:
        # check the following *before* sqlite.connect creates the file!
        must_init = (path == ":memory:" or not exists(path))
        conn = sqlite.connect (path)
        if must_init:
            # initialize database
            f = open (join (split (__file__)[0], "sqlite_init.sql"))
            sql = f.read()
            f.close()
            try:
                for query in sql.split(";"):
                    conn.execute (query)
                conn.execute ("INSERT INTO Version VALUES (?)",
                              (BACKEND_VERSION,))
                conn.execute ("INSERT INTO Packages VALUES (?,?)",
                              (_DEFAULT_PKGID, "",))
                conn.commit()
            except sqlite.OperationalError, e:
                conn.rollback()
                raise RuntimeError, "%s - SQL:\n%s" % (e, query)
        b = _SqliteBackend (path, conn, False, False)
        _cache[path] = b
    else:
        conn = b._conn

    if pkgid != _DEFAULT_PKGID:
        conn.execute ("INSERT INTO Packages VALUES (?,?)", (pkgid, "",))
        conn.commit()


    return b, pkgid

def claims_for_bind (url):
    """
    Is this backend able to bind to the given URL ?
    """
    if url[:7] != "sqlite:": return False

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
    assert (claims_for_bind (url)), url
    if force:
        raise NotImplementedError ("This backend can not force access to "
                                   "locked package")

    if url[:7] != "sqlite:": return False

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
    Strip URL from its scheme ("sqlite:") and separate path and
    fragment.
    """
    scheme = 7
    semicolon = url.find(';')
    if semicolon != -1:
        return url[scheme:semicolon], url[semicolon:]
    else:
        return url[scheme:], _DEFAULT_PKGID

def _get_connection (path):
    try:
        cx = sqlite.connect (path)
        c = cx.execute ("SELECT version FROM Version")
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
    c = cx.execute ("SELECT id FROM Packages WHERE id = ?", (pkgid,))
    for i in c:
        return True
    return False

def _split_id_ref (id_ref):
    """
    Split an id_ref into a prefix and a suffix.
    Return None prefix if id_ref is a plain id.
    Raise an AssertionError if id_ref has length > 2.
    """
    colon = id_ref.find (":")
    if colon <= 0:
        return "", id_ref
    prefix, suffix = id_ref[:colon], id_ref[colon+1:]
    colon = suffix.find (":")
    assert colon <= 0, "id-path has length > 2"
    return prefix, suffix

def _split_uri_ref (uri_ref):
    """
    Split a uri_ref into a URI and a fragment.
    """
    sharp = uri_ref.find("#")
    return uri_ref[:sharp], uri_ref[sharp+1:]


class _SqliteBackend (object):

    def __init__ (self, path, conn, readonly, force):
        """
        Is not part of the interface. Instances must be created either with
        the L{create} or the L{bind} static methods.

        Create a backend, and bind it to the given URL.
        """

        self._path = path
        self._conn = conn
        conn.create_function ("join_id_ref", 2,
                              lambda p,s: p and "%s:%s" % (p,s) or s)
        conn.create_function ("regexp", 2,
                              lambda r,l: re.search(r,l) is not None )
        # NB: for a reason I don't know, the defined function receives the
        # righthand operand first, then the lefthand operand...
        # hence the lambda function above
        self._readonly = readonly

    def close (self):
        """
        Close the backend. Has the effect of closing, for example, underlying
        connections to other services. As a consequence, this method should not
        be invoked by individual packages, for a backend instance may be shared
        by several packages. A package should rather ensure that it maintains
        no reference to the backend instance, so that the garbage collector
        can delete it, which will invoke the close method (see __del__ below).
        """
        #print "DEBUG:", __file__, "about to close SqliteBackend", self._path
        self._conn.close()

    def __del__ (self):
        #print "DEBUG:", __file__, "about to close SqliteBackend", self._path
        try:
            self.close()
        except sqlite.OperationalError:
            pass

    # package uri

    def get_uri (self, package_id):
        q = "SELECT uri FROM Packages WHERE id = ?"
        return self._conn.execute (q, (package_id,)).fetchone()[0]

    def update_uri (self, package_id, uri):
        q = "UPDATE Packages SET uri = ? WHERE id = ?"
        try:
            self._conn.execute (q, (uri, package_id,))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not update", e)

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
            raise ModelError, "id in use: %i", id
        c.execute ("INSERT INTO Elements VALUES (?,?,?)",
                   (package_id, id, element_type))
        return c

    def create_media (self, package_id, id, url):
        try:
            c = self._create_element_cursor (package_id, id, MEDIA)
            c.execute ("INSERT INTO Medias VALUES (?,?,?)",
                       (package_id, id, url))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not insert", e)

    def create_annotation (self, package_id, id, media, begin, end):
        """
        ``media`` is the id-ref of an own or directly imported media.
        """
        assert (isinstance (begin, int) and begin >= 0), begin
        assert (isinstance (  end, int) and   end >= begin), (begin, end)

        p,s = _split_id_ref (media) # also assert that media has len<=2
        assert p != "" or self.has_element(package_id, s, MEDIA), media

        try:
            c = self._create_element_cursor (package_id, id, ANNOTATION)
            c.execute ("INSERT INTO Annotations VALUES (?,?,?,?,?,?)",
                       (package_id, id, p, s, begin, end))
            c.execute ("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                       (package_id, id, "text/plain", "", "",""))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not insert", e)

    def create_relation (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, RELATION)
            c.execute ("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                       (package_id, id, "", "", "", ""))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in creating", e)

    def create_view (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, VIEW)
            c.execute ("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                       (package_id, id, "text/plain", "", "", ""))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in creating", e)

    def create_resource (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, RESOURCE)
            c.execute ("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                       (package_id, id, "text/plain", "", "", ""))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in creating", e)

    def create_tag (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, TAG)
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in creating", e)

    def create_list (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, LIST)
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in creating", e)

    def create_query (self, package_id, id):
        try:
            c = self._create_element_cursor (package_id, id, QUERY)
            c.execute ("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                       (package_id, id, "text/plain", "", "", ""))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in creating",e)
        
    def create_import (self, package_id, id, url, uri):
        try:
            c = self._create_element_cursor (package_id, id, IMPORT)
            c.execute ("INSERT INTO Imports VALUES (?,?,?,?)",
                       (package_id, id, url, uri))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in creating", e)

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
        r = self._conn.execute (q, (package_id, id,)).fetchone()
        if r is None:
            return None
        t = r[0]
        if t == MEDIA:
            return self.get_medias ((package_id,), id=id).next()
        elif t == ANNOTATION:
            return self.get_annotations ((package_id,), id=id).next()
        elif t == IMPORT:
            return self.get_imports ((package_id,), id=id).next()
        else:
            return (t, package_id, id)

    def get_medias (self, package_ids,
                     id=None,  id_alt=None,
                    url=None, url_alt=None,
                   ):
        """
        Yield tuples of the form (MEDIA, package_id, id, url,).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"
        assert ( id is None  or   id_alt is None), ( id,  id_alt)
        assert (url is None  or  url_alt is None), (url, url_alt)

        q = "SELECT ?, package, id, url FROM Medias WHERE package in ("
        args = [MEDIA,]

        for p in package_ids:
            q += "?,"
            args.append (p)
        q += ")"

        if id is not None:
            q += " AND id = ?"
            args.append (id)
        if id_alt is not None:
            q += " AND id IN ("
            for i in id_alt:
                q += "?,"
                args.append(i)
            q += ")"
        if url is not None:
            q += " AND url = ?"
            args.append (url)
        if url_alt is not None:
            q += " AND url IN ("
            for i in url_alt:
                q += "?,"
                args.append(i)
            q += ")"

        return self._conn.execute (q, args)

    def get_annotations (self, package_ids,
                            id=None,    id_alt=None,
                         media=None, media_alt=None,
                         begin=None,    begin_min=None, begin_max=None,
                           end=None,      end_min=None,   end_max=None,
                        ):
        """
        Yield tuples of the form
        (ANNOTATION, package_id, id, media, begin, end,), ordered by begin,
        end and media id-ref.

        ``media`` is the uri-ref of a media ;
        ``media_alt`` is an iterable of uri-refs.
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"
        assert (   id is None  or     id_alt is None)
        assert (media is None  or  media_alt is None)
        assert (begin is None  or  begin_min is None and begin_max is None)
        assert (  end is None  or    end_min is None and   end_max is None)

        if media is not None:
            media_alt = (media,)

        q = "SELECT ?, a.package, a.id, " \
            "       join_id_ref(media_p,media_i) as media, " \
            "       fbegin, fend " \
            "FROM Annotations a %s " \
            "WHERE a.package in ("

        if media_alt is not None:
            q %= "JOIN Packages p ON a.package = p.id "\
                 "LEFT JOIN Imports i " \
                 "  ON a.package = i.package AND a.media_p = i.id"
        else:
            q %= ""

        args = [ANNOTATION,]

        for p in package_ids:
            q += "?,"
            args.append (p)
        q += ")"

        if id is not None:
            q += " AND a.id = ?"
            args.append (id)
        if id_alt is not None:
            q += " AND a.id IN ("
            for i in id_alt:
                q += "?,"
                args.append(i)
            q += ")"
        # NB: media is managed as media_alt (cf. above)
        if media_alt is not None:
            p_url = "sqlite:%s" % self._path
            q += "AND ("
            for m in media_alt:
                media_u, media_i = _split_uri_ref (m)
                q += "(media_i = ? " \
                     " AND (" \
                     "  (media_p = ''   AND  ? IN (p.uri, ?||a.package)) OR " \
                     "  (media_p = i.id AND  ? IN (i.uri, i.url)) ) ) OR "
                args.append (media_i)
                args.append (media_u)
                args.append (p_url)
                args.append (media_u)
            q += "0) "
        if begin is not None:
            q += " AND a.fbegin = ?"
            args.append (begin)
        if begin_min is not None:
            q += " AND a.fbegin >= ?"
            args.append (begin_min)
        if begin_max is not None:
            q += " AND a.fbegin <= ?"
            args.append (begin_max)
        if end is not None:
            q += " AND a.fend = ?"
            args.append (end)
        if end_min is not None:
            q += " AND a.fend >= ?"
            args.append (end_min)
        if end_max is not None:
            q += " AND a.fend <= ?"
            args.append (end_max)

        q += " ORDER BY fbegin, fend, media_p, media_i"

        return self._conn.execute (q, args)

    def get_relations (self, package_ids,
                       id=None, id_alt=None):
        """
        Yield tuples of the form (RELATION, package_id, id,).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        selectfrom, where, args = \
            self._make_element_query (package_ids, RELATION, id, id_alt)
        return self._conn.execute (selectfrom+where, args)

    def get_views (self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (VIEW, package_id, id,).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        selectfrom, where, args = \
            self._make_element_query (package_ids, VIEW, id, id_alt)
        return self._conn.execute (selectfrom+where, args)

    def get_resources (self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (RESOURCE, package_id, id,).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        selectfrom, where, args = \
            self._make_element_query (package_ids, RESOURCE, id, id_alt)
        return self._conn.execute (selectfrom+where, args)

    def get_tags (self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (TAG, package_id, id,).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        selectfrom, where, args = \
            self._make_element_query (package_ids, TAG, id, id_alt)
        return self._conn.execute (selectfrom+where, args)

    def get_lists (self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (LIST, package_id, id,).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        selectfrom, where, args = \
            self._make_element_query (package_ids, LIST, id, id_alt)
        return self._conn.execute (selectfrom+where, args)

    def get_queries (self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (QUERY, package_id, id,).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        selectfrom, where, args = \
            self._make_element_query (package_ids, QUERY, id, id_alt)
        return self._conn.execute (selectfrom+where, args)

    def get_imports (self, package_ids,
                       id=None,   id_alt=None,
                      url=None,  url_alt=None,
                      uri=None,  uri_alt=None,
                    ):
        """
        Yield tuples of the form (IMPORT, package_id, id, url, uri).
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"
        assert ( id is None  or   id_alt is None)
        assert (url is None  or  url_alt is None)
        assert (uri is None  or  uri_alt is None)

        q = "SELECT ?, package, id, url, uri FROM Imports " \
            "WHERE package in ("
        args = [IMPORT,]

        for p in package_ids:
            q += "?,"
            args.append (p)
        q += ")"

        if id is not None:
            q += " AND id = ?"
            args.append (id)
        if id_alt is not None:
            q += " AND id IN ("
            for i in id_alt:
                q += "?,"
                args.append(i)
            q += ")"
        if url is not None:
            q += " AND url = ?"
            args.append (url)
        if url_alt is not None:
            q += " AND url IN ("
            for i in url_alt:
                q += "?,"
                args.append(i)
            q += ")"
        if uri is not None:
            q += " AND uri = ?"
            args.append (uri)
        if uri_alt is not None:
            q += " AND uri IN ("
            for i in uri_alt:
                q += "?,"
                args.append(i)
            q += ")"

        return self._conn.execute (q, args)

    def _make_element_query (self, package_ids, element_type,
                              id=None, id_alt=None):
        """
        Return the selectfrom part of the query, the where part of the query,
        and the argument list, of a query returning all the elements 
        matching the parameters.
        """
        assert (id is None or id_alt is None)

        s = "SELECT typ, package, id FROM Elements"
        w = " WHERE package in ("
        args = []

        for p in package_ids:
            w += "?,"
            args.append (p)
        w += ")"

        w += " AND typ = ?"
        args.append (element_type)

        if id is not None:
            w += " AND id = ?"
            args.append (id)
        if id_alt is not None:
            w += " AND id IN ("
            for i in id_alt:
                w += "?,"
                args.append(i)
            w += ")"

        return s,w,args

    # updating

    def update_media (self, package_id, id, url):
        try:
            self._conn.execute ("UPDATE Medias SET url = ? "
                                "WHERE package = ? AND id = ?",
                                (url, package_id, id,))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not update", e)

    def update_annotation (self, package_id, id, media, begin, end):
        """
        ``media`` is the id-ref of an own or directly imported media.
        """
        assert (isinstance (begin, int) and begin >= 0), begin
        assert (isinstance (  end, int) and   end >= begin), (begin, end)

        p,s = _split_id_ref (media) # also assert that media has len<=2
        assert p != "" or self.has_element(package_id, s, MEDIA), media

        try:
            self._conn.execute ("UPDATE Annotations SET media_p = ?, "
                                "media_i = ?, fbegin = ?, fend = ? "
                                "WHERE package = ? and id = ?",
                                (p, s, begin, end, package_id, id,))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not update", e)

    def update_import (self, package_id, id, url, uri):
        try:
            self._conn.execute ("UPDATE Imports SET url = ?, uri = ? "
                                "WHERE package = ? and id = ?",
                                (url, uri, package_id, id,))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("error in updating", e)

    # content

    def get_content (self, package_id, id, element_type):
        """
        Return a tuple (mimetype, data, schema_idref).
        In this implementation, element_type will always be ignored.
        Note that ``schema_idref`` will be an empty string if no schema is
        specified (never None).
        """
        q = "SELECT mimetype, data, join_id_ref(schema_p,schema_i) as schema " \
            "FROM Contents " \
            "WHERE package = ? AND element = ?"
        cur = self._conn.execute (q, (package_id, id,))
        return cur.fetchone() or None

    def update_content (self, package_id, id, mimetype, data, schema):
        """
        Update the content of the identified element.
        ``schema`` is the id-ref of an own or directly imported resource,
        or an empty string to specify no schema (not None).
        """
        if schema:
            p,s = _split_id_ref (schema) # also assert that schema has len<=2
            assert p == "" or self.has_element(package_id,p,IMPORT), p
            assert p != "" or self.has_element(package_id,s,RESOURCE), schema
        else:
            p,s = "",""

        q = "UPDATE Contents "\
            "SET mimetype = ?, data = ?, schema_p = ?, schema_i = ? "\
            "WHERE package = ? AND element = ?"
        args = ( mimetype, data, p, s, package_id, id,)
        cur = self._conn.execute (q, args)
        self._conn.commit()

    # meta-data

    def iter_meta (self, package_id, id, element_type):
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
        Return the given metadata of the identified element.
        id should be an empty string if package metadata is required,
        and element_type will be ignored.

        In this implementation, element_type will always be ignored.
        """
        q = """SELECT value FROM Meta
               WHERE package = ? AND element = ? AND KEY = ?"""
        c = self._conn.execute (q, (package_id, id, key,))
        d = c.fetchone()
        if d is None:
            return None
        else:
            return d[0]

    def set_meta (self, package_id, id, element_type, key, val):
        """
        Return the given metadata of the identified element.
        id should be an empty string if package metadata is required,
        and element_type will be ignored.
        id should be an empty string if package metadata is targetted,
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

    # relation members

    def insert_member (self, package_id, id, member, pos):
        """
        Insert a member at the given position.
        ``member`` is the id-ref of an own or directly imported member.
        ``pos`` may be any value between -1 and n (inclusive), where n is the
        current number of members.
        If -1, the member will be appended at the end (**note** that this is
        not the same behaviour as ``list.insert`` in python2.5).
        If non-negative, the member will be inserted at that position.
        """
        n = self.count_members (package_id, id)
        assert -1 <= pos <= n, pos
        p,s = _split_id_ref (member) # also assert that member has len<=2
        assert p != "" or self.has_element(package_id, s, ANNOTATION), member
        if pos == -1:
            pos = n
        try:
            c = self._conn.cursor()
            # sqlite does not seem to be able to do the following updates in
            # one query (unicity constraint breaks), so...
            for i in xrange(n, pos-1, -1):
                c.execute ("UPDATE RelationMembers SET ord=ord+1 "
                           "WHERE package = ? AND relation = ? AND ord = ?",
                           (package_id, id, i))
            c.execute ("INSERT INTO RelationMembers VALUES (?,?,?,?,?)",
                       (package_id, id, pos, p, s))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not update or insert", e)

    def update_member (self, package_id, id, member, pos):
        """
        Remobv the member at the given position in the identified relation.
        ``member`` is the id-ref of an own or directly imported member.
        """
        assert 0 <= pos < self.count_members (package_id, id), pos

        p,s = _split_id_ref (member) # also assert that member has len<=2
        assert p != "" or self.has_element(package_id, s, ANNOTATION), member

        try:
            c = self._conn.cursor()
            c.execute ("UPDATE RelationMembers SET member_p = ?, member_i = ? "
                       "WHERE package = ? AND relation = ? AND ord = ?",
                       (p, s, package_id, id, pos))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not update", e)

    def count_members (self, package_id, id):
        """
        Count the members of the identified relations.
        """
        q = "SELECT count(ord) FROM RelationMembers "\
            "WHERE package = ? AND relation = ?"
        return self._conn.execute (q, (package_id, id)).fetchone()[0]

    def get_member (self, package_id, id, pos):
        """
        Return the id-ref of the member at the given position in the identified
        relation.
        """
        if __debug__:
            c = self.count_members (package_id, id)
            assert -c <= pos < c, pos

        if pos < 0:
            c = self.count_members (package_id, id)
            pos += c

        q = "SELECT join_id_ref(member_p,member_i) AS member " \
            "FROM RelationMembers "\
            "WHERE package = ? AND relation = ? AND ord = ?"
        return self._conn.execute (q, (package_id, id, pos)).fetchone()[0]

    def iter_members (self, package_id, id):
        """
        Iter over all the members of the identified relation.
        """
        q = "SELECT join_id_ref(member_p,member_i) AS member " \
            "FROM RelationMembers " \
            "WHERE package = ? AND relation = ? ORDER BY ord"
        for r in self._conn.execute (q, (package_id, id)):
            yield r[0]

    def remove_member (self, package_id, id, pos):
        """
        Remobv the member at the given position in the identified relation.
        """
        assert 0 <= pos < self.count_members (package_id, id), pos

        try:
            c = self._conn.cursor()
            c.execute ("DELETE FROM RelationMembers "
                       "WHERE package = ? AND relation = ? AND ord = ?",
                       (package_id, id, pos))
            c.execute ("UPDATE RelationMembers SET ord=ord-1 "
                       "WHERE package = ? AND relation = ? AND ord > ?",
                       (package_id, id, pos))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not delete or update", e)

    def get_relations_with_member (self, member, package_ids, pos=None):
        """
        Return tuples of the form (RELATION, package_id, id) of all the 
        relations having the given member, at the given position if given.
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        member_u, member_i = _split_uri_ref (member)

        q = "SELECT DISTINCT ?, e.package, e.id FROM Elements e " \
            "JOIN Packages p ON e.package = p.id "\
            "JOIN RelationMembers m " \
              "ON e.package = m.package and e.id = m.relation " \
            "LEFT JOIN Imports i ON m.member_p = i.id " \
            "WHERE member_i = ? AND ("\
              "(member_p = ''   AND  ? IN (p.uri, ?||e.package)) OR " \
              "(member_p = i.id AND  ? IN (i.uri, i.url)))"

        p_url = "sqlite:%s" % self._path
        args = [RELATION, member_i, member_u, p_url, member_u]

        if pos is not None:
            q += " AND ord = ?"
            args.append (pos)

        return self._conn.execute (q, args)

    # list items

    def insert_item (self, package_id, id, item, pos):
        """
        Insert an item at the given position.
        ``item`` is the id-ref of an own or directly imported item.
        ``pos`` may be any value between -1 and n (inclusive), where n is the
        current number of items.
        If -1, the item will be appended at the end (**note** that this is
        not the same behaviour as ``list.insert`` in python2.5).
        If non-negative, the item will be inserted at that position.
        """
        n = self.count_items (package_id, id)
        assert -1 <= pos <= n, pos
        p,s = _split_id_ref (item) # also assert that item has len<=2
        assert p != "" or self.has_element(package_id, s), item
        if pos == -1:
            pos = n
        try:
            c = self._conn.cursor()
            # sqlite does not seem to be able to do the following updates in
            # one query (unicity constraint breaks), so...
            for i in xrange(n, pos-1, -1):
                c.execute ("UPDATE ListItems SET ord=ord+1 "
                           "WHERE package = ? AND list = ? AND ord = ?",
                           (package_id, id, i))
            c.execute ("INSERT INTO ListItems VALUES (?,?,?,?,?)",
                       (package_id, id, pos, p, s))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not update or insert", e)

    def update_item (self, package_id, id, item, pos):
        """
        Remobv the item at the given position in the identified list.
        ``item`` is the id-ref of an own or directly imported item.
        """
        assert 0 <= pos < self.count_items (package_id, id), pos

        p,s = _split_id_ref (item) # also assert that item has len<=2
        assert p != "" or self.has_element(package_id, s), item

        try:
            c = self._conn.cursor()
            c.execute ("UPDATE ListItems SET item_p = ?, item_i = ? "
                       "WHERE package = ? AND list = ? AND ord = ?",
                       (p, s, package_id, id, pos))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not update", e)

    def count_items (self, package_id, id):
        """
        Count the items of the identified lists.
        """
        q = "SELECT count(ord) FROM ListItems "\
            "WHERE package = ? AND list = ?"
        return self._conn.execute (q, (package_id, id)).fetchone()[0]

    def get_item (self, package_id, id, pos):
        """
        Return the id-ref of the item at the given position in the identified
        list.
        """
        if __debug__:
            c = self.count_items (package_id, id)
            assert -c <= pos < c, pos

        if pos < 0:
            c = self.count_items (package_id, id)
            pos += c

        q = "SELECT join_id_ref(item_p,item_i) AS item " \
            "FROM ListItems "\
            "WHERE package = ? AND list = ? AND ord = ?"
        return self._conn.execute (q, (package_id, id, pos)).fetchone()[0]

    def iter_items (self, package_id, id):
        """
        Iter over all the items of the identified list.
        """
        q = "SELECT join_id_ref(item_p,item_i) AS item " \
            "FROM ListItems " \
            "WHERE package = ? AND list = ? ORDER BY ord"
        for r in self._conn.execute (q, (package_id, id)):
            yield r[0]

    def remove_item (self, package_id, id, pos):
        """
        Remobv the item at the given position in the identified list.
        """
        assert 0 <= pos < self.count_items (package_id, id), pos

        try:
            c = self._conn.cursor()
            c.execute ("DELETE FROM ListItems "
                       "WHERE package = ? AND list = ? AND ord = ?",
                       (package_id, id, pos))
            c.execute ("UPDATE ListItems SET ord=ord-1 "
                       "WHERE package = ? AND list = ? AND ord > ?",
                       (package_id, id, pos))
            self._conn.commit()
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError ("could not delete or update", e)

    def get_lists_with_item (self, item, package_ids, pos=None):
        """
        Return tuples of the form (LIST, package_id, id) of all the 
        lists having the given item, at the given position if given.
        """
        assert not isinstance (package_ids, basestring), "*iterable* of package_ids expected"

        item_u, item_i = _split_uri_ref (item)

        q = "SELECT DISTINCT ?, e.package, e.id FROM Elements e " \
            "JOIN Packages p ON e.package = p.id "\
            "JOIN ListItems m " \
              "ON e.package = m.package and e.id = m.list " \
            "LEFT JOIN Imports i ON m.item_p = i.id " \
            "WHERE item_i = ? AND ("\
              "(item_p = ''   AND  ? IN (p.uri, ?||e.package)) OR " \
              "(item_p = i.id AND  ? IN (i.uri, i.url)))"

        p_url = "sqlite:%s" % self._path
        args = [LIST, item_i, item_u, p_url, item_u]

        if pos is not None:
            q += " AND ord = ?"
            args.append (pos)

        return self._conn.execute (q, args)

    # end of the class
