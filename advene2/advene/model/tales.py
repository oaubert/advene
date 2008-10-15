"""
TODO docstring

Special TALES attributes
========================

Although TALES will search the attributes and item of an object when traversing
it, it may be useful in some situations to provide TALES with specific
attributes and methods.

Naming convention
-----------------

When traversing object o with path element "a", TALES with first look for an attribute or method named "_tales_a". This allows classes to provide additional attributes, or even to override existing attributes in TALES.

Method decorators
-----------------

This module provides a set of decorators (all functions named ``tales_X``) to be used with methods (either standard or TALES specific -- see `Naming convention`_) to customize the way TALES uses those methods.

Wrapping
--------

In some cases, the naming convention and method decorators are not sufficient (i.e. when a mixin class should use the TALES specific version of an underlying method). For those cases, classes may provide the ``__wrap_with_tales_context__`` method. TALES will look for this method just before attempting to traverse an object, and if found, will replace that object by the result of the method.

Note that the wrapping will happen just before traversing: TALES will never return a wrapped object as the result of an expression.

TALES Global Methods
====================

TALES global methods are functions that are available anywhere in a TALES path.

Warning
-------

TALES global method should be avoided as much as possible, since they clutter the attribute space in interactive TALES editing, and may induce unexpected behaviours. However, there are some uses to them.

"""
from simpletal import simpleTALES

AdveneTalesException=simpleTALES.PathNotFoundException

def tales_full_path_function(f):
    """
    Decorator for TALES full-path-functions.

    A full-path-function will be immediately invoked, with the rest of the path
    as its sole argument.
    """
    f.tales_type = "full-path-function"
    return f

def tales_path1_function(f):
    """
    Decorator for TALES path1-functions.

    A path1-function will be called with the next path element as its argument,
    rather than searching for an attribute or key with that name.

    See advene.model.core.meta for an example.
    """
    f.tales_type = "path1-function"
    return f

def tales_context_function(f):
    """
    Decorator for TALES context-functions.

    When the last item of a path, and no-call is not used, a context-function
    is invoked with the context as its argument (rather than without any
    argument for other functions).

    :see-also: `tales_use_context`
    """
    f.tales_type = "context-function"
    return f

def tales_property(f):
    """
    Decorator for TALES property.

    A TALES property is similar in use to python's properties:
    it will automatically be called (with the context as its sole parameter)
    *even* if it has a subpath or if ``no-call:`` is used.

    :see-also: `tales_use_context`
    """
    f.tales_type = "auto-call"
    return f

def tales_use_as_context(var):
    """
    Decorator with 1 argument to be used with TALES properties and
    context-functions (or it will have no effect).

    If the function expects a specific context variable rather than the context
    itself, the name of the variable can be specified with this decorator.

    Example::
        @tales_property
        @tales_use_as_context("package")
        def some_method(self, a_package):
            ...
    """
    def the_actual_decorator(f):
        f.tales_context_variable = var
        return f
    return the_actual_decorator


class AdveneContext(simpleTALES.Context):
    def __init__(self, here, options=None):
        """Creates a tales.AdveneContext object, having a global symbol 'here'
           with value 'here' and a global symbol 'options' where all the key-
           value pairs of parameter 'options' are copied. Of course, it also
           has all the standard TALES global symbols.
        """
        if options is None:
                options={}
        simpleTALES.Context.__init__(self, dict(options)) # *copy* dict 'options'
        self.addGlobal('here', here)

    def traversePath(self, expr, canCall=1):
        if expr.startswith('"') or expr.startswith("'"):
            if expr.endswith('"') or expr.endswith("'"):
                expr = expr[1:-1]
            else:
                expr = expr[1:]
        elif expr.endswith('"') or expr.endswith("'"):
            expr = expr[:-1]
        pathList = expr.split("/")

        val = self._traverse_first(pathList[0])
        tales_type = None
        for i, p in enumerate(pathList[1:]):
            val = self._traverse_next(val, p)
            tales_type = getattr(val, "tales_type", None)
            if tales_type == "full-path-function":
                # stop traversing, path remaining path to val
                arg = pathList[i+2:]
                if arg or canCall:
                    return val(pathList[i+2:])
                # else the function will be returned as is
            elif tales_type == "auto-call":
                variable_context = getattr(val, "tales_context_variable", None)
                if variable_context is None:
                    param = self
                else:
                    param = self._traverse_first(variable_context)
                val = val(param)
        if canCall and tales_type != "auto-call":
            val = self._eval(val)
        return val

    def _traverse_first(self, path):
        if path.startswith("?"):
            path = self._eval(self._traverse_first(self, path[1:]))

        if self.locals.has_key(path):
            r = self.locals[path]
        elif self.globals.has_key(path):
            r = self.globals[path]
        else:
            raise simpleTALES.PATHNOTFOUNDEXCEPTION
        return r

    def _traverse_next(self, val, path):
        # wrap current object with TALES context if possible
        # (see for example advene.model.core.tag)
        wrapper = getattr(val, "__wrap_with_tales_context__", None)
        if wrapper is not None:
            val = wrapper(self)
        # search different attributes/method for the given path
        protected = "_tales_%s" % path
        if getattr(val, "tales_type", None) == "path1-function":
            return val(path)
        elif hasattr(val, protected):
            return getattr(val, protected)
        elif hasattr(val, path):
            return getattr(val, path)
        else:
            try:
                return val[path]
            except Exception:
                try:
                    return val[int(path)]
                except Exception:
                    gm = get_global_method(path)
                    if gm is not None:
                        return gm(val, self)
                    else:
                        raise simpleTALES.PATHNOTFOUNDEXCEPTION

    def _eval(self, val):
        if callable(val):
            if getattr(val, "tales_type", None) == "context-function":
                variable_context = getattr(val, "tales_context_variable", None)
                if variable_context is None:
                    param = self
                else:
                    param = self._traverse_first(variable_context)
                return val(param)
            else:
                return val()
        else:
            return val


# global method registration

def get_global_method(name):
    """
    Retrieves a global method, or return None if no such global method has been
    registered.
    """
    global _global_methods
    return _global_methods.get(name)

def iter_global_methods():
    """
    Iter over all the global method names.
    """
    global _global_methods
    return iter(_global_methods)

def register_global_method(f, name=None):
    """
    Register f as a global method, under the given name, or under its own
    name if no name is provided.

    f must accept two arguments: the object retrieved from the previous TALES
    path, and the TALES context.
    """
    global _global_methods
    _global_methods[name or f.func_name] = f

def unregister_global_method(f_or_name):
    """
    Unregister a global method. The parameter is the name of the global method,
    or can be the function if it has been registered under its own name.
    """
    global _global_methods
    name = getattr(f_or_name, "func_name", f_or_name)
    del _global_methods[name]

_global_methods = {}

def _gm_repr(obj, context):
    return repr(obj)

register_global_method(_gm_repr, "repr")


# absolute_url

class WithAbsoluteUrlMixin(object):
    """
    This class provides a common implementation for the ``absolute_url`` tales
    function.

    ``absolute_url`` is supposed to return an URL where one can retrieve a
    *description* of an object (this is *not* the URL where a package can be
    downloaded, nor the URI-ref of an element). It is intensively used in
    HTML views served by the embedded HTTP server in the Advene tool.

    ``absolute_url`` is expected to consume the rest of the TALES path, and
    suffix it to its return value. E.g::
          some_element/absolute_url/content_data
          -> http://localhost:1234/packages/p/some_element/content_data

          some_package/absolute_url/annotations
          -> http://localhost:1234/packages/some_package/annotations

    But if no URL can be constructed, it returns None.

    This mixin provides all the bells and whistles to do so. It relies on
    the presence of two TALES variables:
     * options/packages (mandatory) contains a dict whose keys are package
       names, and whose values are package instances
     * options/base_url (optional) contains the reference URL

    The returned value will be of the form::
      base_url/specific/rest/of/the/path
    where ``specific`` is computed by a method from the mixed-in class, of the
    form::

      def _compute_absolute_url(self, packages)

    and this method should invoke `self._absolute_url_fail()` if it can not
    construct a URL (resulting in the TALES path failing to evaluate).
    """
    @tales_property
    def _tales_absolute_url(self, context):
        """
        See class documentation.
        """
        options = context.evaluate("options|nothing")
        if options is None:
            raise AdveneTalesException
        packages = options.get("packages")
        if packages is None:
            raise AdveneTalesException
        base = options.get("base_url", "")
        abs = self._compute_absolute_url(packages)
        return _AbsoluteUrl("%s/%s" % (base, abs))

    def _absolute_url_fail(self):
        raise AdveneTalesException

class _AbsoluteUrl(unicode):
    """
    Used by `WithAbsoluteUrlMixin`.
    """
    def __new__(self, abs):
        return unicode.__new__(self, abs)
    def __getitem__(self, item):
        return _AbsoluteUrl(u"%s/%s" % (self, item))
