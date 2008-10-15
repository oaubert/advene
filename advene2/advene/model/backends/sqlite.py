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
from weakref   import WeakKeyDictionary, WeakValueDictionary
import re

from advene.model import ModelError
from advene.model.backends import InternalError, PackageInUse
from advene.model.core.element \
  import MEDIA, ANNOTATION, RELATION, VIEW, RESOURCE, TAG, LIST, QUERY, IMPORT
from advene.utils.reftools import WeakValueDictWithCallback


BACKEND_VERSION = "0.1"

IN_MEMORY_URL = "sqlite::memory:"


def claims_for_create(url):
    """Is this backend able to create a package to the given URL ?

    Not that the semantics of this function is not to test whether the package
    already exists, but only to check that the given URL is compatible with
    this backend.
    """
    if not url.startswith("sqlite:"): return False

    path, pkgid = _strip_url(url)

    if path == ":memory:": return True

    # persistent (file) database
    if not exists(path):
        # check that file can be created
        path = split(path)[0]
        if not isdir(path): return False
        return True
    else:
        # check that file is a correct database (created by this backend)
        cx = _get_connection(path)
        if cx is None: return False
        # check that file does not already contains the required pkg
        # NB: in ":memory:", cx is the connection to the cached backend
        r = not _contains_package(cx, pkgid)
        cx.close()
        return r

def create(package, force=False, url=None):
    """Create a _SqliteBackend instance for the given package.

    Return the backend an the package id.
    @param package: an object with attributes url and readonly
    @param force: should the package be created even if it exists?
    @param url: backend-wise URL to be used if different for package.url
    """
    url = url or package.url
    assert(claims_for_create(url)), "url = %r" % url
    if force:
        raise NotImplementedError("This backend can not force creation of "
                                   "existing package")

    path, pkgid = _strip_url(url)
    b = _cache.get(path)
    if b is not None:
        conn = b._conn
        curs = b._curs
        already = b._bound.get(pkgid)
        if already is not None:
            raise PackageInUse(already)
        elif _contains_package(conn, pkgid):
            raise PackageInUse(pkgid)
        b._begin_transaction("EXCLUSIVE")
    else:
        # check the following *before* sqlite.connect creates the file!
        must_init = (path == ":memory:" or not exists(path))
        conn = sqlite.connect(path, isolation_level=None)
        curs = conn.cursor()
        if must_init:
            # initialize database
            f = open(join(split(__file__)[0], "sqlite_init.sql"))
            sql = f.read()
            f.close()
            try:
                curs.execute("BEGIN EXCLUSIVE")
                curs.executescript(sql)
                curs.execute("INSERT INTO Version VALUES (?)",
                             (BACKEND_VERSION,))
                curs.execute("INSERT INTO Packages VALUES (?,?,?)", 
                             (_DEFAULT_PKGID, "", "",))
            except sqlite.OperationalError, e:
                curs.execute("ROLLBACK")
                raise RuntimeError("%s - SQL:\n%s" % (e, query))
        elif _contains_package(conn, pkgid):
            raise PackageInUse(pkgid)
        b = _SqliteBackend(path, conn, force)
        _cache[path] = b

    try:
        if pkgid != _DEFAULT_PKGID:
            conn.execute("INSERT INTO Packages VALUES (?,?,?)",
                         (pkgid, "", "",))
        b._bind(pkgid, package)
    except sqlite.Error, e:
        curs.execute("ROLLBACK")
        raise InternalError("could not update", e)
    except InternalError:
        curs.execute("ROLLBACK")
        raise
    curs.execute("COMMIT")
    return b, pkgid

def claims_for_bind(url):
    """
    Is this backend able to bind to the given URL ?
    """
    if not url.startswith("sqlite:"): return False

    path, pkgid = _strip_url(url)

    if path == ":memory:":
        be = _cache.get(":memory:")
        if be is None:
            # in_memory backend is not in used, so it must be created
            return False
        else:
            # in_memory backend is in use, exitsing package can be bound
            return _contains_package(be._conn, pkgid)

    # persistent (file) database
    if not exists(path):
        return False
    else:
        # check that file is a correct database (created by this backend)
        cx = _get_connection(path)
        if cx is None: return False
        # check that file does contains the required pkg
        r = _contains_package(cx, pkgid)
        cx.close()
        return r

def bind(package, force=False, url=None):
    """Create a _SqliteBackend instance for the given package.

    Return the backend an the package id.
    @param package: an object with attributes url and readonly
    @param force: should the package be open even if it is locked?
    @param url: backend-wise URL to be used if different for package.url
    """
    url = url or package.url
    assert(claims_for_bind(url)), url
    if force:
        raise NotImplementedError("This backend can not force access to "
                                   "locked package")

    path, pkgid = _strip_url(url)
    b = _cache.get(path)
    if b is None:
        conn = sqlite.connect(path, isolation_level=None)
        b = _SqliteBackend(path, conn, force)
        _cache[path] = b
    b._begin_transaction("EXCLUSIVE")
    try:
        b._bind(pkgid, package)
    except InternalError:
        b._curs.execute("ROLLBACK")
        raise
    b._curs.execute("COMMIT")
    return b, pkgid


_cache = WeakValueDictionary()

_DEFAULT_PKGID = ""

def _strip_url(url):
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

def _get_connection(path):
    try:
        cx = sqlite.connect(path)
        c = cx.execute("SELECT version FROM Version")
        for v in c:
            if v[0] != BACKEND_VERSION: return None
        return cx
        
    except sqlite.DatabaseError:
        return None
    except sqlite.OperationalError:
        return None

def _contains_package(cx, pkgid):
    c = cx.execute("SELECT id FROM Packages WHERE id = ?", (pkgid,))
    for i in c:
        return True
    return False

def _split_id_ref(id_ref):
    """
    Split an id_ref into a prefix and a suffix.
    Return None prefix if id_ref is a plain id.
    Raise an AssertionError if id_ref has length > 2.
    """
    colon = id_ref.find(":")
    if colon <= 0:
        return "", id_ref
    prefix, suffix = id_ref[:colon], id_ref[colon+1:]
    colon = suffix.find(":")
    assert colon <= 0, "id-path has length > 2"
    return prefix, suffix

def _split_uri_ref(uri_ref):
    """
    Split a uri_ref into a URI and a fragment.
    """
    sharp = uri_ref.find("#")
    return uri_ref[:sharp], uri_ref[sharp+1:]



class _FlushableIterator(object):
    __slots__ = ["_cursor", "__weakref__",]
    def __init__ (self, cursor, backend):
        self._cursor = cursor
        backend._iterators[self] = True
    def __iter__ (self):
        return self
    def flush(self):
        """Flush the underlying cursor."""
        self._cursor = iter(list(self._cursor))
    def next(self):
        return self._cursor.next()


class _SqliteBackend(object):

    def __init__(self, path, conn, force):
        """
        Is not part of the interface. Instances must be created either with
        the L{create} or the L{bind} module functions.

        Create a backend, and bind it to the given URL.
        """

        self._path = path
        self._conn = conn
        self._curs = conn.cursor()
        # NB: self._curs is to be used for any *internal* operations
        # Iterators intended for *external* use must be based on a new cursor.
        conn.create_function("join_id_ref", 2,
                              lambda p,s: p and "%s:%s" % (p,s) or s)
        conn.create_function("regexp", 2,
                              lambda r,l: re.search(r,l) is not None )
        # NB: for a reason I don't know, the defined function receives the
        # righthand operand first, then the lefthand operand...
        # hence the lambda function above
        self._bound = WeakValueDictWithCallback(self._check_unused)
        # NB: the callback ensures that even if packages "forget" to close
        # themselves, once they are garbage collected, we check if the
        # connexion to sqlite can be closed.
        self._iterators = WeakKeyDictionary()
        # _iterators is used to store all the iterators returned by iter_*
        # methods, and force them to flush their underlying cursor anytime
        # an modification of the database is about to happen

    def _bind(self, package_id, package):
        d = self._bound
        old = d.get(package_id)
        if old is not None:
            raise PackageInUse(old)
        try:
            self._curs.execute("UPDATE Packages SET url = ? WHERE id = ?",
                               (package.url, package_id,))
        except sqlite.Error, e:
            raise InternalError("could not update", e)
        d[package_id] = package

    def close(self, package_id):
        """Inform the backend that a given package will no longer be used.

        NB: this implementation is robust to packages forgetting to close
        themselves, i.e. when packages are garbage collected, this is detected
        and they are automatically unbound.
        """
        d = self._bound
        m = d.get(package_id) # keeping a ref on it prevents it to disappear
        if m is not None:     # in the meantime...
            try:
                self._curs.execute("UPDATE Packages SET url = ? WHERE id = ?",
                                   ("", package_id,))
            except sqlite.Error, e:
                raise InternalError("could not update", e)
            del d[package_id]
        self._check_unused(package_id)

    def _check_unused(self, package_id):
        conn = self._conn
        if conn is not None and len(self._bound) == 0:
            #print "DEBUG:", __file__, \
            #      "about to close SqliteBackend", self._path
            try:
                self._curs.execute("UPDATE Packages SET url = ?", ("",))
            finally:
                conn.close()
            self._conn = None
            self._curs = None
            # the following is necessary to break a cyclic reference:
            # self._bound references self._check_unused, which, as a bound
            # method, references self
            self._bound = None
            # the following is not stricly necessary, but does no harm ;)
            if self._path in _cache: del _cache[self._path]

    def _begin_transaction(self, mode=""):
        for i in self._iterators.iterkeys():
            i.flush()
        self._curs.execute("BEGIN %s" % mode)
        
    # package uri

    def get_uri(self, package_id):
        q = "SELECT uri FROM Packages WHERE id = ?"
        return self._curs.execute(q, (package_id,)).fetchone()[0]

    def update_uri(self, package_id, uri):
        q = "UPDATE Packages SET uri = ? WHERE id = ?"
        execute = self._curs.execute
        try:
            execute(q, (uri, package_id,))
        except sqlite.Error, e:
            raise InternalError("could not update", e)

    # creation

    def _create_element(self, execute, package_id, id, element_type):
        """Perform controls and insertions common to all elements.

        NB: This starts a transaction that must be commited by caller.
        """
        # check that the id is not in use
        self._begin_transaction("IMMEDIATE")
        c = execute("SELECT id FROM Elements WHERE package = ? AND id = ?",
                    (package_id, id,))
        if c.fetchone() is not None:
            raise ModelError("id in use: %s" % id)
        execute("INSERT INTO Elements VALUES (?,?,?)",
                (package_id, id, element_type))

    def create_media(self, package_id, id, url):
        c = self._curs
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, MEDIA)
            execute("INSERT INTO Medias VALUES (?,?,?)",
                    (package_id, id, url))
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("could not insert", e)

    def create_annotation(self, package_id, id, media, begin, end):
        """
        ``media`` is the id-ref of an own or directly imported media.
        """
        assert(isinstance(begin, int) and begin >= 0), begin
        assert(isinstance(  end, int) and   end >= begin), (begin, end)

        p,s = _split_id_ref(media) # also assert that media has depth < 2
        assert p != "" or self.has_element(package_id, s, MEDIA), media

        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, ANNOTATION)
            execute("INSERT INTO Annotations VALUES (?,?,?,?,?,?)",
                    (package_id, id, p, s, begin, end))
            execute("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                    (package_id, id, "text/plain", "", "",""))
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("could not insert", e)

    def create_relation(self, package_id, id):
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, RELATION)
            execute("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                    (package_id, id, "", "", "", ""))
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("error in creating", e)

    def create_view(self, package_id, id):
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, VIEW)
            execute("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                    (package_id, id, "text/plain", "", "", ""))
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("error in creating", e)

    def create_resource(self, package_id, id):
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, RESOURCE)
            execute("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                    (package_id, id, "text/plain", "", "", ""))
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("error in creating", e)

    def create_tag(self, package_id, id):
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, TAG)
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("error in creating", e)

    def create_list(self, package_id, id):
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, LIST)
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("error in creating", e)

    def create_query(self, package_id, id):
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, QUERY)
            execute("INSERT INTO Contents VALUES (?,?,?,?,?,?)",
                    (package_id, id, "text/plain", "", "", ""))
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("error in creating",e)
        
    def create_import(self, package_id, id, url, uri):
        _create_element = self._create_element
        execute = self._curs.execute
        try:
            _create_element(execute, package_id, id, IMPORT)
            execute("INSERT INTO Imports VALUES (?,?,?,?)",
                    (package_id, id, url, uri))
            execute("COMMIT")
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("error in creating", e)

    # retrieval

    def has_element(self, package_id, id, element_type=None):
        """
        Return True if the given package has an element with the given id.
        If element_type is provided, only return true if the element has the
        the given type.
        """
        q = "SELECT typ FROM Elements WHERE package = ? and id = ?"
        for i in self._curs.execute(q, (package_id, id,)):
            return element_type is None or i[0] == element_type
        return False

    def get_element(self, package_id, id):
        """
        Return the tuple describing a given element, None if that element does
        not exist.
        """

        q = "SELECT typ FROM Elements WHERE package = ? AND id = ?"
        r = self._curs.execute(q, (package_id, id,)).fetchone()
        if r is None:
            return None
        t = r[0]
        if t == MEDIA:
            return self.iter_medias((package_id,), id=id).next()
        elif t == ANNOTATION:
            return self.iter_annotations((package_id,), id=id).next()
        elif t == IMPORT:
            return self.iter_imports((package_id,), id=id).next()
        else:
            return(t, package_id, id)

    def iter_medias(self, package_ids,
                    id=None,  id_alt=None,
                    url=None, url_alt=None,
                   ):
        """
        Yield tuples of the form(MEDIA, package_id, id, url,).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"
        assert( id is None  or   id_alt is None), ( id,  id_alt)
        assert(url is None  or  url_alt is None), (url, url_alt)

        q = "SELECT ?, package, id, url FROM Medias " \
            "WHERE package in (" + "?," * len(package_ids) + ")"
        args = [MEDIA,] + list(package_ids)
        if id is not None:
            q += " AND id = ?"
            args.append(id)
        if id_alt is not None:
            q += " AND id IN ("
            for i in id_alt:
                q += "?,"
                args.append(i)
            q += ")"
        if url is not None:
            q += " AND url = ?"
            args.append(url)
        if url_alt is not None:
            q += " AND url IN ("
            for i in url_alt:
                q += "?,"
                args.append(i)
            q += ")"

        r = self._conn.execute(q, args)
        return _FlushableIterator(r, self)

    def iter_annotations(self, package_ids,
                         id=None,    id_alt=None,
                         media=None, media_alt=None,
                         begin=None, begin_min=None, begin_max=None,
                         end=None,   end_min=None,   end_max=None,
                        ):
        """
        Yield tuples of the form
        (ANNOTATION, package_id, id, media, begin, end,), ordered by begin,
        end and media id-ref.

        ``media`` is the uri-ref of a media ;
        ``media_alt`` is an iterable of uri-refs.
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"
        assert(   id is None  or     id_alt is None)
        assert(media is None  or  media_alt is None)
        assert(begin is None  or  begin_min is None and begin_max is None)
        assert(  end is None  or    end_min is None and   end_max is None)

        if media is not None:
            media_alt = (media,)

        q = "SELECT ?, a.package, a.id, " \
            "       join_id_ref(media_p,media_i) as media, " \
            "       fbegin, fend " \
            "FROM Annotations a %s " \
            "WHERE a.package in (" + "?," * len(package_ids) + ")"
        args = [ANNOTATION,] + list(package_ids)
        if media_alt is not None:
            q %= "JOIN Packages p ON a.package = p.id "\
                 "LEFT JOIN Imports i " \
                 "  ON a.package = i.package AND a.media_p = i.id"
        else:
            q %= ""
        if id is not None:
            q += " AND a.id = ?"
            args.append(id)
        if id_alt is not None:
            q += " AND a.id IN ("
            for i in id_alt:
                q += "?,"
                args.append(i)
            q += ")"
        # NB: media is managed as media_alt (cf. above)
        if media_alt is not None:
            q += "AND ("
            for m in media_alt:
                media_u, media_i = _split_uri_ref(m)
                q += "(media_i = ? " \
                     " AND (" \
                     "  (media_p = ''   AND  ? IN (p.uri, p.url)) OR " \
                     "  (media_p = i.id AND  ? IN (i.uri, i.url)) ) ) OR "
                args.append(media_i)
                args.append(media_u)
                args.append(media_u)
            q += "0) "
        if begin is not None:
            q += " AND a.fbegin = ?"
            args.append(begin)
        if begin_min is not None:
            q += " AND a.fbegin >= ?"
            args.append(begin_min)
        if begin_max is not None:
            q += " AND a.fbegin <= ?"
            args.append(begin_max)
        if end is not None:
            q += " AND a.fend = ?"
            args.append(end)
        if end_min is not None:
            q += " AND a.fend >= ?"
            args.append(end_min)
        if end_max is not None:
            q += " AND a.fend <= ?"
            args.append(end_max)

        q += " ORDER BY fbegin, fend, media_p, media_i"

        r = self._conn.execute(q, args)
        return _FlushableIterator(r, self)

    def iter_relations(self, package_ids,
                       id=None, id_alt=None):
        """
        Yield tuples of the form (RELATION, package_id, id,).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        selectfrom, where, args = \
            self._make_element_query(package_ids, RELATION, id, id_alt)
        r = self._conn.execute(selectfrom+where, args)
        return _FlushableIterator(r, self)

    def iter_views(self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (VIEW, package_id, id,).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        selectfrom, where, args = \
            self._make_element_query(package_ids, VIEW, id, id_alt)
        r = self._conn.execute(selectfrom+where, args)
        return _FlushableIterator(r, self)

    def iter_resources(self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (RESOURCE, package_id, id,).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        selectfrom, where, args = \
            self._make_element_query(package_ids, RESOURCE, id, id_alt)
        r = self._conn.execute(selectfrom+where, args)
        return _FlushableIterator(r, self)

    def iter_tags(self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (TAG, package_id, id,).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        selectfrom, where, args = \
            self._make_element_query(package_ids, TAG, id, id_alt)
        r = self._conn.execute(selectfrom+where, args)
        return _FlushableIterator(r, self)

    def iter_lists(self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (LIST, package_id, id,).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        selectfrom, where, args = \
            self._make_element_query(package_ids, LIST, id, id_alt)
        r = self._conn.execute(selectfrom+where, args)
        return _FlushableIterator(r, self)

    def iter_queries(self, package_ids, id=None, id_alt=None):
        """
        Yield tuples of the form (QUERY, package_id, id,).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        selectfrom, where, args = \
            self._make_element_query(package_ids, QUERY, id, id_alt)
        r = self._conn.execute(selectfrom+where, args)
        return _FlushableIterator(r, self)

    def iter_imports(self, package_ids,
                      id=None,   id_alt=None,
                      url=None,  url_alt=None,
                      uri=None,  uri_alt=None,
                    ):
        """
        Yield tuples of the form (IMPORT, package_id, id, url, uri).
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"
        assert( id is None  or   id_alt is None)
        assert(url is None  or  url_alt is None)
        assert(uri is None  or  uri_alt is None)

        q = "SELECT ?, package, id, url, uri FROM Imports " \
            "WHERE package in (" + "?," * len(package_ids) + ")"
        args = [IMPORT,] + list(package_ids)
        if id is not None:
            q += " AND id = ?"
            args.append(id)
        if id_alt is not None:
            q += " AND id IN ("
            for i in id_alt:
                q += "?,"
                args.append(i)
            q += ")"
        if url is not None:
            q += " AND url = ?"
            args.append(url)
        if url_alt is not None:
            q += " AND url IN ("
            for i in url_alt:
                q += "?,"
                args.append(i)
            q += ")"
        if uri is not None:
            q += " AND uri = ?"
            args.append(uri)
        if uri_alt is not None:
            q += " AND uri IN ("
            for i in uri_alt:
                q += "?,"
                args.append(i)
            q += ")"

        r = self._conn.execute(q, args)
        return _FlushableIterator(r, self)

    def _make_element_query(self, package_ids, element_type,
                              id=None, id_alt=None):
        """
        Return the selectfrom part of the query, the where part of the query,
        and the argument list, of a query returning all the elements 
        matching the parameters.
        """
        assert(id is None or id_alt is None)

        s = "SELECT typ, package, id FROM Elements"
        w = " WHERE package in (" + "?," * len(package_ids) + ") "\
            " AND typ = ?"
        args = list(package_ids) + [element_type,]
        if id is not None:
            w += " AND id = ?"
            args.append(id)
        if id_alt is not None:
            w += " AND id IN ("
            for i in id_alt:
                w += "?,"
                args.append(i)
            w += ")"

        return s,w,args

    # updating

    def update_media(self, package_id, id, url):
        execute = self._curs.execute
        try:
            execute("UPDATE Medias SET url = ? "
                     "WHERE package = ? AND id = ?",
                    (url, package_id, id,))
        except sqlite.Error, e:
            raise InternalError("could not update", e)

    def update_annotation(self, package_id, id, media, begin, end):
        """
        ``media`` is the id-ref of an own or directly imported media.
        """
        assert(isinstance(begin, int) and begin >= 0), begin
        assert(isinstance(  end, int) and   end >= begin), (begin, end)

        p,s = _split_id_ref(media) # also assert that media has depth < 2
        assert p != "" or self.has_element(package_id, s, MEDIA), media

        execute = self._curs.execute
        try:
            execute("UPDATE Annotations SET media_p = ?, "
                     "media_i = ?, fbegin = ?, fend = ? "
                     "WHERE package = ? and id = ?",
                    (p, s, begin, end, package_id, id,))
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError("could not update", e)

    def update_import(self, package_id, id, url, uri):
        execute = self._curs.execute
        try:
            execute("UPDATE Imports SET url = ?, uri = ? "
                     "WHERE package = ? and id = ?",
                    (url, uri, package_id, id,))
        except sqlite.Error, e:
            self._conn.rollback()
            raise InternalError("error in updating", e)

    # reference finding

    # TODO

    # renaming

    # TODO

    # deletion

    # TODO

    # content

    def get_content(self, package_id, id, element_type):
        """
        Return a tuple(mimetype, data, schema_idref).
        In this implementation, element_type will always be ignored.
        Note that ``schema_idref`` will be an empty string if no schema is
        specified (never None).
        """
        q = "SELECT mimetype, data, join_id_ref(schema_p,schema_i) as schema " \
            "FROM Contents " \
            "WHERE package = ? AND element = ?"
        return self._curs.execute(q, (package_id, id,)).fetchone() or None

    def update_content(self, package_id, id, mimetype, data, schema):
        """
        Update the content of the identified element.
        ``schema`` is the id-ref of an own or directly imported resource,
        or an empty string to specify no schema (not None).
        """
        if schema:
            p,s = _split_id_ref(schema) # also assert that schema has depth < 2
            assert p == "" or self.has_element(package_id,p,IMPORT), p
            assert p != "" or self.has_element(package_id,s,RESOURCE), schema
        else:
            p,s = "",""

        q = "UPDATE Contents "\
            "SET mimetype = ?, data = ?, schema_p = ?, schema_i = ? "\
            "WHERE package = ? AND element = ?"
        args = (mimetype, data, p, s, package_id, id,)
        execute = self._curs.execute
        try:
            execute(q, args)
        except sqlite.Error, e:
            raise InternalError("could not update", e)

    # meta-data

    def iter_meta(self, package_id, id, element_type):
        """
        Iter over the metadata, sorting keys in alphabetical order.

        In this implementation, element_type will always be ignored.
        """
        q = """SELECT key, value FROM Meta
               WHERE package = ? AND element = ? ORDER BY key"""
        r = ( (d[0], d[1])
               for d in self._conn.execute(q, (package_id, id)) )
        return _FlushableIterator(r, self)

    def get_meta(self, package_id, id, element_type, key):
        """
        Return the given metadata of the identified element.
        id should be an empty string if package metadata is required,
        and element_type will be ignored.

        In this implementation, element_type will always be ignored.
        """
        q = """SELECT value FROM Meta
               WHERE package = ? AND element = ? AND KEY = ?"""
        d = self._curs.execute(q, (package_id, id, key,)).fetchone()
        if d is None:
            return None
        else:
            return d[0]

    def set_meta(self, package_id, id, element_type, key, val):
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
        c = self._curs.execute(q, (package_id, id, key))
        d = c.fetchone()

        if d is None:
            if val is not None:
                q = """INSERT INTO Meta (package, element, key, value)
                       VALUES (?,?,?,?)"""
                args = (package_id, id, key, val)
        else:
            if val is not None:
                q = """UPDATE Meta SET value = ?
                       WHERE package = ? AND element = ? AND key = ?"""
                args = (val, package_id, id, key)
            else:
                q = """DELETE FROM Meta
                       WHERE package = ? AND element = ? AND key = ?"""
                args = (package_id, id, key)
        execute = self._curs.execute
        try:
            execute(q, args)
        except sqlite.Error, e:
            raise InternalError("could not %s" % q[:6], e)

    # relation members

    def insert_member(self, package_id, id, member, pos, n=-1):
        """
        Insert a member at the given position.
        ``member`` is the id-ref of an own or directly imported member.
        ``pos`` may be any value between -1 and n (inclusive), where n is the
        current number of members.
        If -1, the member will be appended at the end (**note** that this is
        not the same behaviour as ``list.insert`` in python2.5).
        If non-negative, the member will be inserted at that position.

        NB: the total number of members, n, if known, may be provided, as an
        optimization.
        """
        if n < 0:
            n = self.count_members(package_id, id)
        assert -1 <= pos <= n, pos
        p,s = _split_id_ref(member) # also assert that member has depth < 2
        assert p != "" or self.has_element(package_id, s, ANNOTATION), member
        if pos == -1:
            pos = n
        execute = self._curs.execute
        executemany = self._curs.executemany
        updates = ((package_id, id, i) for i in xrange(n, pos-1, -1))
        self._begin_transaction()
        try:
            # sqlite does not seem to be able to do the following updates in
            # one query (unicity constraint breaks), so...
            executemany("UPDATE RelationMembers SET ord=ord+1 "
                         "WHERE package = ? AND relation = ? AND ord = ?",
                        updates)
            execute("INSERT INTO RelationMembers VALUES (?,?,?,?,?)",
                    (package_id, id, pos, p, s))
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("could not update or insert", e)
        execute("COMMIT")

    def update_member(self, package_id, id, member, pos):
        """
        Remobv the member at the given position in the identified relation.
        ``member`` is the id-ref of an own or directly imported member.
        """
        assert 0 <= pos < self.count_members(package_id, id), pos

        p,s = _split_id_ref(member) # also assert that member has depth < 2
        assert p != "" or self.has_element(package_id, s, ANNOTATION), member

        execute = self._curs.execute
        try:
            execute("UPDATE RelationMembers SET member_p = ?, member_i = ? "
                     "WHERE package = ? AND relation = ? AND ord = ?",
                    (p, s, package_id, id, pos))
        except sqlite.Error, e:
            raise InternalError("could not update", e)

    def count_members(self, package_id, id):
        """
        Count the members of the identified relations.
        """
        q = "SELECT count(ord) FROM RelationMembers "\
            "WHERE package = ? AND relation = ?"
        return self._curs.execute(q, (package_id, id)).fetchone()[0]

    def get_member(self, package_id, id, pos, n=-1):
        """
        Return the id-ref of the member at the given position in the identified
        relation.

        NB: the total number of members, n, if known, may be provided, as an
        optimization.
        """
        if __debug__:
            n = self.count_members(package_id, id)
            assert -n <= pos < n, pos

        if pos < 0:
            if n < 0:
                n = self.count_members(package_id, id)
            pos += n

        q = "SELECT join_id_ref(member_p,member_i) AS member " \
            "FROM RelationMembers "\
            "WHERE package = ? AND relation = ? AND ord = ?"
        return self._curs.execute(q, (package_id, id, pos)).fetchone()[0]

    def iter_members(self, package_id, id):
        """
        Iter over all the members of the identified relation.
        """
        q = "SELECT join_id_ref(member_p,member_i) AS member " \
            "FROM RelationMembers " \
            "WHERE package = ? AND relation = ? ORDER BY ord"
        for r in self._conn.execute(q, (package_id, id)):
            yield r[0]

    def remove_member(self, package_id, id, pos):
        """
        Remove the member at the given position in the identified relation.
        """
        assert 0 <= pos < self.count_members(package_id, id), pos

        execute = self._curs.execute
        self._begin_transaction()
        try:
            execute("DELETE FROM RelationMembers "
                     "WHERE package = ? AND relation = ? AND ord = ?",
                    (package_id, id, pos))
            execute("UPDATE RelationMembers SET ord=ord-1 "
                     "WHERE package = ? AND relation = ? AND ord > ?",
                    (package_id, id, pos))
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("could not delete or update", e)
        execute("COMMIT")

    def iter_relations_with_member(self, package_ids, member, pos=None):
        """
        Return tuples of the form (RELATION, package_id, id) of all the 
        relations having the given member, at the given position if given.

        @param member the uri-ref of an annotation
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        member_u, member_i = _split_uri_ref(member)

        q = "SELECT DISTINCT ?, e.package, e.id FROM Elements e " \
            "JOIN Packages p ON e.package = p.id "\
            "JOIN RelationMembers m " \
              "ON e.package = m.package and e.id = m.relation " \
            "LEFT JOIN Imports i ON m.member_p = i.id " \
            " WHERE e.package in (" + "?," * len(package_ids) + ")" \
            " AND member_i = ? AND ("\
            "  (member_p = ''   AND  ? IN (p.uri, p.url)) OR " \
            "  (member_p = i.id AND  ? IN (i.uri, i.url)))"
        args = [RELATION,] + list(package_ids) \
                           + [member_i, member_u, member_u,]
        if pos is not None:
            q += " AND ord = ?"
            args.append(pos)
        r = self._conn.execute(q, args)
        return _FlushableIterator(r, self)

    # list items

    def insert_item(self, package_id, id, item, pos, n=-1):
        """
        Insert an item at the given position.
        ``item`` is the id-ref of an own or directly imported item.
        ``pos`` may be any value between -1 and n (inclusive), where n is the
        current number of items.
        If -1, the item will be appended at the end (**note** that this is
        not the same behaviour as ``list.insert`` in python2.5).
        If non-negative, the item will be inserted at that position.

        NB: the total number of members, n, if known, may be provided, as an
        optimization.
        """
        if n < 0:
            n = self.count_items(package_id, id)
        assert -1 <= pos <= n, pos
        p,s = _split_id_ref(item) # also assert that item has depth < 2
        assert p != "" or self.has_element(package_id, s), item
        if pos == -1:
            pos = n
        execute = self._curs.execute
        executemany = self._curs.executemany
        updates = ((package_id, id, i) for i in xrange(n, pos-1, -1))
        self._begin_transaction()
        try:
            # sqlite does not seem to be able to do the following updates in
            # one query (unicity constraint breaks), so...
            executemany("UPDATE ListItems SET ord=ord+1 "
                           "WHERE package = ? AND list = ? AND ord = ?",
                        updates)
            execute("INSERT INTO ListItems VALUES (?,?,?,?,?)",
                    (package_id, id, pos, p, s))
        except sqlite.Error, e:
            execute("ROLLBACK")
            raise InternalError("could not update or insert", e)
        execute("COMMIT")

    def update_item(self, package_id, id, item, pos):
        """
        Remobv the item at the given position in the identified list.
        ``item`` is the id-ref of an own or directly imported item.
        """
        assert 0 <= pos < self.count_items(package_id, id), pos

        p,s = _split_id_ref(item) # also assert that item has depth < 2
        assert p != "" or self.has_element(package_id, s), item

        execute = self._curs.execute
        try:
            execute("UPDATE ListItems SET item_p = ?, item_i = ? "
                       "WHERE package = ? AND list = ? AND ord = ?",
                      (p, s, package_id, id, pos))
        except sqlite.Error, e:
            raise InternalError("could not update", e)

    def count_items(self, package_id, id):
        """
        Count the items of the identified lists.
        """
        q = "SELECT count(ord) FROM ListItems "\
            "WHERE package = ? AND list = ?"
        return self._curs.execute(q, (package_id, id)).fetchone()[0]

    def get_item(self, package_id, id, pos, n=-1):
        """
        Return the id-ref of the item at the given position in the identified
        list.

        NB: the total number of members, n, if known, may be provided, as an
        optimization.
        """
        if __debug__:
            n = self.count_items(package_id, id)
            assert -n <= pos < n, pos

        if pos < 0:
            if n < 0:
                n = self.count_items(package_id, id)
            pos += n

        q = "SELECT join_id_ref(item_p,item_i) AS item " \
            "FROM ListItems "\
            "WHERE package = ? AND list = ? AND ord = ?"
        return self._curs.execute(q, (package_id, id, pos)).fetchone()[0]

    def iter_items(self, package_id, id):
        """
        Iter over all the items of the identified list.
        """
        q = "SELECT join_id_ref(item_p,item_i) AS item " \
            "FROM ListItems " \
            "WHERE package = ? AND list = ? ORDER BY ord"
        for r in self._conn.execute(q, (package_id, id)):
            yield r[0]

    def remove_item(self, package_id, id, pos):
        """
        Remove the item at the given position in the identified list.
        """
        assert 0 <= pos < self.count_items(package_id, id), pos

        execute = self._curs.execute
        self._begin_transaction()
        try:
            execute("DELETE FROM ListItems "
                     "WHERE package = ? AND list = ? AND ord = ?",
                    (package_id, id, pos))
            execute("UPDATE ListItems SET ord=ord-1 "
                     "WHERE package = ? AND list = ? AND ord > ?",
                    (package_id, id, pos))
        except sqlite.Error, e:
            execute("ROLLBACK")
            self._conn.rollback()
            raise InternalError("could not delete or update", e)
        execute("COMMIT")

    def iter_lists_with_item(self, package_ids, item, pos=None):
        """
        Return tuples of the form (LIST, package_id, id) of all the 
        lists having the given item, at the given position if given.

        @param item the uri-ref of an element
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        item_u, item_i = _split_uri_ref(item)

        q = "SELECT DISTINCT ?, e.package, e.id FROM Elements e " \
            "JOIN Packages p ON e.package = p.id "\
            "JOIN ListItems m " \
              "ON e.package = m.package and e.id = m.list " \
            "LEFT JOIN Imports i ON m.item_p = i.id " \
            "WHERE e.package in (" + "?," * len(package_ids) + ")" \
            " AND item_i = ? AND ("\
            "  (item_p = ''   AND  ? IN (p.uri, p.url)) OR " \
            "  (item_p = i.id AND  ? IN (i.uri, i.url)))"
        args = [LIST,] + list(package_ids) + [item_i, item_u, item_u,]
        if pos is not None:
            q += " AND ord = ?"
            args.append(pos)
        r = self._conn.execute(q, args)
        return _FlushableIterator(r, self)

    # tagged elements

    def associate_tag(self, package_id, element, tag):
        """Associate a tag to an element.

        @param element the id-ref of an own or directly imported element
        @param tag the id-ref of an own or directly imported tag
        """
        eltp, elts = _split_id_ref(element) # also assert that it has depth < 2
        tagp, tags = _split_id_ref(tag) # also assert that tag has depth < 2

        execute = self._curs.execute
        try:
            execute("INSERT OR IGNORE INTO Tagged VALUES (?,?,?,?,?)",
                    (package_id, eltp, elts, tagp, tags))
        except sqlite.Error, e:
            raise InternalError("could not insert", e)

    def dissociate_tag(self, package_id, element, tag):
        """Dissociate a tag from an element.

        @param element the id-ref of an own or directly imported element
        @param tag the id-ref of an own or directly imported tag
        """
        eltp, elts = _split_id_ref(element) # also assert that it has depth < 2
        tagp, tags = _split_id_ref(tag) # also assert that tag has depth < 2

        execute = self._curs.execute
        try:
            execute("DELETE FROM Tagged WHERE package = ? "
                     "AND element_p = ? AND element_i = ? "
                     "AND tag_p = ? AND tag_i = ?",
                    (package_id, eltp, elts, tagp, tags))
        except sqlite.Error, e:
            raise InternalError("could not delete", e)

    def iter_tags_with_element(self, package_ids, element):
        """Iter over all the tags associated to element in the given packages.

        @param element the uri-ref of an element
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        element_u, element_i = _split_uri_ref(element)
        q = "SELECT t.package, join_id_ref(tag_p, tag_i) " \
            "FROM Tagged t " \
            "JOIN Packages p ON t.package = p.id " \
            "LEFT JOIN Imports i ON t.element_p = i.id " \
            "WHERE t.package in (" + "?," * len(package_ids) + ")" \
            " AND element_i = ? AND ("\
            "  (element_p = ''   AND  ? IN (p.uri, p.url)) OR " \
            "  (element_p = i.id AND  ? IN (i.uri, i.url)))"
        args = list(package_ids) + [element_i, element_u, element_u]

        r = self._conn.execute(q, args)
        return _FlushableIterator(r, self)

    def iter_elements_with_tag(self, package_ids, tag):
        """Iter over all the elements associated to tag in the given packages.

        @param tag the uri-ref of a tag
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        tag_u, tag_i = _split_uri_ref(tag)
        q = "SELECT t.package, join_id_ref(element_p, element_i) " \
            "FROM Tagged t " \
            "JOIN Packages p ON t.package = p.id " \
            "LEFT JOIN Imports i ON t.tag_p = i.id " \
            "WHERE t.package in (" + "?," * len(package_ids) + ")" \
            " AND tag_i = ? AND ("\
            "  (tag_p = ''   AND  ? IN (p.uri, p.url)) OR " \
            "  (tag_p = i.id AND  ? IN (i.uri, i.url)))"
        args = list(package_ids) + [tag_i, tag_u, tag_u]

        r = self._conn.execute(q, args)
        return _FlushableIterator(r, self)

    def iter_tagging(self, package_ids, element, tag):
        """Iter over all the packages associating element to tag.

        @param element the uri-ref of an element
        @param tag the uri-ref of a tag
        """
        assert not isinstance(package_ids, basestring), "list if ids expected"

        element_u, element_i = _split_uri_ref(element)
        tag_u, tag_i = _split_uri_ref(tag)
        q = "SELECT t.package " \
            "FROM Tagged t " \
            "JOIN Packages p ON t.package = p.id " \
            "LEFT JOIN Imports ie ON t.element_p = ie.id " \
            "LEFT JOIN Imports it ON t.tag_p = it.id " \
            "WHERE t.package in (" + "?," * len(package_ids) + ")" \
            " AND element_i = ? AND ("\
            "  (element_p = ''    AND  ? IN (p.uri,  p.url)) OR " \
            "  (element_p = ie.id AND  ? IN (ie.uri, ie.url)))" \
            " AND tag_i = ? AND ("\
            "  (tag_p = ''    AND  ? IN (p.uri,  p.url)) OR " \
            "  (tag_p = it.id AND  ? IN (it.uri, it.url)))"
        args = list(package_ids) \
             + [element_i, element_u, element_u, tag_i, tag_u, tag_u,]

        r = ( i[0] for i in self._conn.execute(q, args) )
        return _FlushableIterator(r, self)


    # end of the class

# NB: all iter_* functions must return a _FlushableIterator which stores itself 
# in the _iterators attribute of the backend.
# all methods modifying the DB must use _begin_transaction to start a 
# transaction, in order to flush the iterators stored in _iterators (or the commit will fail).
# both behaviour could have been implemented as decorators for the
# corresponding methods, but
#  - "classical" (i.e. wrapping) decorators have a high overhead
#  - "smart" (i.e. code-modifying) decorators are hard to write
# so for the moment, we opt for old-school copy/paste...
