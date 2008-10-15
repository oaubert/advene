from unittest import TestCase, main

from advene.model.core.package import Package as CorePackage
from advene.model.tales import AdveneContext, register_global_method, \
                               unregister_global_method

class TestGlobalMethod(TestCase):
    def setUp(self):
        self.p = p = CorePackage("tmp1", create=True)
        p.uri = "urn:1234"
        p.create_media("m1", "http://media.org/m1")

        self.c = AdveneContext(p)
        self.c.addGlobal("regpkg", p)

    def tearDown(self):
        pass

    def check_path(self, path, expected_result):
        self.assertEqual(self.c.traversePath(path), expected_result)


    def test_repr(self):
        p = self.p
        self.check_path("here", p)
        self.check_path("here/repr", repr(p))
        self.check_path("here/uri", p.uri)
        self.check_path("here/uri/repr", repr(p.uri))

    def test_registered(self):
        def my_global_method(obj, context):
            return (obj, context)
        register_global_method(my_global_method)
        c = self.c
        p = self.p
        try:
            self.check_path("here/my_global_method", (p,c))
            self.check_path("here/uri/my_global_method", (p.uri,c))
            self.check_path("here/m1/my_global_method", (p.get("m1"),c))
        finally:
            unregister_global_method(my_global_method)


    def test_aliased(self):
        def my_global_method(obj, context):
            return (obj, context)
        register_global_method(my_global_method, "aliased_global_method")
        c = self.c
        p = self.p
        try:
            self.check_path("here/aliased_global_method", (p,c))
            self.check_path("here/uri/aliased_global_method", (p.uri,c))
            self.check_path("here/m1/aliased_global_method", (p.get("m1"),c))
        finally:
            unregister_global_method("aliased_global_method")

if __name__ == "__main__":
    main()
