from advene.model.core.package import Package

p = Package("file:new-package.bzp", create=True)

v1 = p.create_view("v1", "application/x-advene-builtin-view")
v1.content_data = "method = hello_world"
v2 = p.create_view("is_view", "application/x-advene-builtin-view")
v2.content_data = "method = has_type \n type = VIEW"
v3 = p.create_view("is_package", "application/x-advene-builtin-view")
v3.content_data = "method = has_type \n type = PACKAGE"

for v in (v1, v2, v3):
    print "content-type:", v.output_mimetype, "\n"
    print v.apply_to(p)
    print "=========="
