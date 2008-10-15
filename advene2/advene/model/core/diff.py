"""I provide functions to compare elements and packages."""

from advene.model.core.element import PackageElement, MEDIA, ANNOTATION, \
  RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE

def diff_medias(m1, m2):
    return _diff_attr(m1, m2, "url") \
         + _diff_attr(m1, m2, "frame_of_reference") \
         + _diff_tags(m1, m2) \
         + _diff_meta(m1, m2)

def diff_annotations(a1, a2):
    return _diff_attr(a1, a2, "media_id") \
         + _diff_attr(a1, a2, "begin") \
         + _diff_attr(a1, a2, "end") \
         + _diff_contents(a1, a2) \
         + _diff_tags(a1, a2) \
         + _diff_meta(a1, a2)

def diff_relations(r1, r2):
    return _diff_members(r1, r2) \
         + _diff_contents(r1, r2) \
         + _diff_tags(r1, r2) \
         + _diff_meta(r1, r2)

def diff_lists(l1, l2):
    return _diff_items(l1, l2) \
         + _diff_tags(l1, l2) \
         + _diff_meta(l1, l2)

def diff_tags(t1, t2):
    return _diff_imported_elements(t1, t2) \
         + _diff_tags(t1, t2) \
         + _diff_meta(t1, t2)

def diff_views(v1, v2):
    return _diff_contents(v1, v2) \
         + _diff_tags(v1, v2) \
         + _diff_meta(v1, v2)

def diff_queries(q1, q2):
    return _diff_contents(q1, q2) \
         + _diff_tags(q1, q2) \
         + _diff_meta(q1, q2)

def diff_resources(r1, r2):
    return _diff_contents(r1, r2) \
         + _diff_tags(r1, r2) \
         + _diff_meta(r1, r2)

def diff_imports(i1, i2):
    return _diff_attr(i1, i2, "url") \
         + _diff_attr(i1, i2, "uri") \
         + _diff_tags(i1, i2) \
         + _diff_meta(i1, i2)

def diff_packages(p1, p2):
    "returns the list of operation to perform on p2 to make it like p1"
    return _diff_attr(p1, p2, "uri") \
         + _diff_meta(p1, p2) \
         + _diff_elt_lists(p1, p2, "imports") \
         + _diff_elt_lists(p1, p2, "medias") \
         + _diff_elt_lists(p1, p2, "annotations") \
         + _diff_elt_lists(p1, p2, "relations") \
         + _diff_elt_lists(p1, p2, "tags") \
         + _diff_elt_lists(p1, p2, "lists") \
         + _diff_elt_lists(p1, p2, "views") \
         + _diff_elt_lists(p1, p2, "queries") \
         + _diff_elt_lists(p1, p2, "resources") \
         + _diff_external_tag_associations(p1, p2)

# utility functions

def _diff_attr(elt1, elt2, attr):
    if getattr(elt1, attr) != getattr(elt2, attr):
        if hasattr(elt1, "ADVENE_TYPE"):
            obj = elt1._id
        else:
            obj = elt1
        return [("<setattr>", obj, attr, getattr(elt1, attr)),]
    return []

def _diff_members(r1, r2):
    l1 = list(enumerate(r1.iter_members_ids()))
    l2 = list(enumerate(r2.iter_members_ids()))
    r = []
    for i1, i2 in _xzip(l1, l2, lambda x: x[0]):
        if i1 is None:
            i2, m2 = i2
            r.append(("remove_member", r1._id, -1))
        elif i2 is None:
            i1, m1 = i1
            r.append(("insert_member", r1._id, -1, m1))
        elif i1 != i2:
            i1, m1 = i1
            i2, m2 = i2
            r.append(("update_member", r1._id, i1, m1))
    return r

def _diff_items(l1, l2):
    m1 = list(enumerate(l1.iter_items_ids()))
    m2 = list(enumerate(l2.iter_items_ids()))
    r = []
    for i1, i2 in _xzip(m1, m2, lambda x: x[0]):
        if i1 is None:
            i2, j2 = i2
            r.append(("remove_item", l1._id, -1))
        elif i2 is None:
            i1, j1 = i1
            r.append(("insert_item", l1._id, -1, j1))
        elif i1 != i2:
            i1, j1 = i1
            i2, j2 = i2
            r.append(("update_item", l1._id, i1, j1))
    return r

def _diff_imported_elements(t1, t2):
    l1 = [ i for i in enumerate(t1.iter_elements_ids(t1._owner)) 
             if ":" in i[1] ]
    l2 = [ i for i in enumerate(t2.iter_elements_ids(t2._owner)) 
             if ":" in i[1] ]
    r = []
    for e1, e2 in _xzip(l1, l2, lambda x: x):
        if e1 is None:
            r.append(("dissociate_tag", e2, t1._id))
        elif e2 is None:
            r.append(("associate_tag", e1, t1._id))
    return r

def _diff_contents(elt1, elt2):
    r = _diff_attr(elt1, elt2, "content_mimetype") \
         + _diff_attr(elt1, elt2, "content_schema_id") \
         + _diff_attr(elt1, elt2, "content_url")
    if elt1.content_url == elt2.content_url \
    and (not elt1.content_url or elt1.content_url.startswith("packaged:")):
        r += _diff_attr(elt1, elt2, "content_data")
    return r

def _diff_tags(e1, e2):
    l1 = list(enumerate(e1.iter_tags_ids(e1._owner)))
    l2 = list(enumerate(e2.iter_tags_ids(e2._owner)))
    r = []
    for t1, t2 in _xzip(l1, l2, lambda x: x):
        if t1 is None:
            r.append(("dissociate_tag", e1._id, t2))
        elif t2 is None:
            r.append(("associate_tag", e1._id, t1))
    return r

def _diff_meta(obj1, obj2):
    if hasattr(obj1, "ADVENE_TYPE"):
        id = obj1._id
        typ = obj1.ADVENE_TYPE
    else:
        id = ""
        typ = ""
    m1 = list(obj1.iter_meta_ids())
    m2 = list(obj2.iter_meta_ids())
    r = []
    for i1, i2 in _xzip(m1, m2, lambda x: x[0]):
        if i1 is None:
            r.append(("set_meta", id, typ, i2[0], None, None))
        elif i2 is None or i1 != i2:
            r.append(("set_meta", id, typ, i1[0], i1[1], i1[1].is_id))
    return r
            
def _diff_elt_lists(p1, p2, name):
    l1 = _sorted_list(getattr(p1.own, name), key=lambda x: x._id)
    l2 = _sorted_list(getattr(p2.own, name), key=lambda x: x._id)
    diff_ = globals()["diff_%s" % name]
    r = []
    for e1, e2 in _xzip(l1, l2, lambda x: x._id):
        if e1 is None:
            r.append(_delete(e2))
        elif e2 is None:
            r.append(_create(e1))
        else:
            r.extend(diff_(e1, e2))
    return r

def _diff_external_tag_associations(p1, p2):
    l1 = _sorted_list(p1._backend.iter_external_tagging(p1._id))
    l2 = _sorted_list(p2._backend.iter_external_tagging(p2._id))
    r = []
    for a1, a2 in _xzip(l1, l2, lambda x: x):
        if a1 is None:
            r.append(("dissociate_tag", a2[0], a2[1]))
        elif a2 is None:
            r.append(("associate_tag", a1[0], a1[1]))
    return r

def _delete(elt):
    return ("", "delete_element", elt._id)

def _create(elt):
    return ("<create>", elt)

def _sorted_list(it, cmp=None, key=None, reverse=False):
    r = list(it)
    r.sort(cmp, key, reverse)
    return r

def _xzip(l1, l2, idfier=lambda x:x):
    i1 = 0; i2 = 0
    while i1 < len(l1) and i2 < len(l2):
        id1 = idfier(l1[i1])
        id2 = idfier(l2[i2])
        if id1 == id2:
            yield l1[i1], l2[i2]
            i1 += 1
            i2 += 1
        elif id1 > id2:
            yield None, l2[i2]
            i2 += 1
        else:
            yield l1[i1], None
            i1 += 1
    for i in l1[i1:]:
        yield i, None
    for i in l2[i2:]:
        yield None, i
