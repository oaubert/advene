"""I provide functions to compare elements and packages."""

def cmp_medias(m1, m2):
    return _cmp_id(m1, m2) \
        or _cmp_attr(m1, m2, "url") \
        or _cmp_attr(m1, m2, "frame_of_reference") \
        or _cmp_tags(m1, m2) \
        or _cmp_meta(m1, m2)

def cmp_annotations(a1, a2):
    return _cmp_attr(a1, a2, "media_idref") \
        or _cmp_attr(a1, a2, "begin") \
        or _cmp_attr(a1, a2, "end") \
        or _cmp_id(a1, a2) \
        or _cmp_contents(a1, a2) \
        or _cmp_tags(a1, a2) \
        or _cmp_meta(a1, a2)

def cmp_relations(r1, r2):
    return _cmp_id(r1, r2) \
        or _cmp_members(r1, r2) \
        or _cmp_contents(r1, r2) \
        or _cmp_tags(r1, r2) \
        or _cmp_meta(r1, r2)

def cmp_lists(l1, l2):
    return _cmp_id(l1, l2) \
        or _cmp_items(l1, l2) \
        or _cmp_tags(l1, l2) \
        or _cmp_meta(l1, l2)

def cmp_tags(t1, t2):
    return _cmp_id(t1, t2) \
        or _cmp_elements(t1, t2) \
        or _cmp_tags(t1, t2) \
        or _cmp_meta(t1, t2)

def cmp_views(v1, v2):
    return _cmp_id(v1, v2) \
        or _cmp_contents(v1, v2) \
        or _cmp_tags(v1, v2) \
        or _cmp_meta(v1, v2)

def cmp_queries(q1, q2):
    return _cmp_id(q1, q2) \
        or _cmp_contents(q1, q2) \
        or _cmp_tags(q1, q2) \
        or _cmp_meta(q1, q2)

def cmp_resources(r1, r2):
    return _cmp_id(r1, r2) \
        or _cmp_contents(r1, r2) \
        or _cmp_tags(r1, r2) \
        or _cmp_meta(r1, r2)

def cmp_imports(i1, i2):
    return _cmp_id(i1, i2) \
        or _cmp_attr(i1, i2, "url") \
        or _cmp_attr(i1, i2, "uri") \
        or _cmp_tags(i1, i2) \
        or _cmp_meta(i1, i2)

def cmp_packages(p1, p2):
    return _cmp_attr(p1, p2, "uri") \
        or _cmp_meta(p1, p2) \
        or _cmp_elt_lists(p1, p2, "medias") \
        or _cmp_elt_lists(p1, p2, "annotations") \
        or _cmp_elt_lists(p1, p2, "relations") \
        or _cmp_elt_lists(p1, p2, "lists") \
        or _cmp_elt_lists(p1, p2, "tags") \
        or _cmp_elt_lists(p1, p2, "views") \
        or _cmp_elt_lists(p1, p2, "queries") \
        or _cmp_elt_lists(p1, p2, "resources") \
        or _cmp_elt_lists(p1, p2, "imports") \
        or _cmp_external_tag_associations(p1, p2)

# utility functions

def _cmp_id(elt1, elt2):
    return cmp(elt1._id, elt2._id)

def _cmp_attr(elt1, elt2, attr):
    return cmp(getattr(elt1, attr), getattr(elt2, attr))

def _cmp_members(r1, r2):
    return cmp(list(r1.iter_members_idrefs()),
               list(r2.iter_members_idrefs()))

def _cmp_items(l1, l2):
    return cmp(list(l1.iter_items_idrefs()),
               list(l2.iter_items_idrefs()))

def _cmp_elements(t1, t2):
    return cmp(_sorted_list(t1.iter_elements_idrefs(t1._owner)),
               _sorted_list(t2.iter_elements_idrefs(t2._owner)))

def _cmp_contents(elt1, elt2):
    return _cmp_attr(elt1, elt2, "content_mimetype") \
        or _cmp_attr(elt1, elt2, "content_schema_idref") \
        or _cmp_attr(elt1, elt2, "content_url") \
        or (not elt1.content_url or elt1.content_url.startswith("packaged:")) \
           and _cmp_attr(elt1, elt2, "content_data")

def _cmp_tags(elt1, elt2):
    return cmp(_sorted_list(elt1.iter_tags_idrefs(elt1._owner)),
               _sorted_list(elt2.iter_tags_idrefs(elt2._owner)))

def _cmp_meta(elt1, elt2):
    return cmp(list(elt1.iter_meta_idrefs()),
               list(elt2.iter_meta_idrefs()))

def _cmp_elt_lists(p1, p2, name):
    l1 = _sorted_list(getattr(p1.own, name), key=lambda x: x._id)
    l2 = _sorted_list(getattr(p2.own, name), key=lambda x: x._id)
    if len(l1) != len(l2):
        return len(l1)-len(l2)
    cmp_ = globals()["cmp_%s" % name]
    for i,j in zip(l1, l2):
        c = cmp_(i, j)
        if c: return c
    return 0

def _cmp_external_tag_associations(p1, p2):
    return cmp(_sorted_list(p1._backend.iter_external_tagging(p1._id)),
               _sorted_list(p2._backend.iter_external_tagging(p2._id)))

def _sorted_list(it, cmp=None, key=None, reverse=False):
    r = list(it)
    r.sort(cmp, key, reverse)
    return r
