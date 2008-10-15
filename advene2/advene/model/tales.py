from simpletal import simpleTALES
from inspect import getargspec

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

    See advene.model.core.element and advene.model.core.tag for examples.
    """
    f.tales_type = "context-function"
    return f

def tales_auto_call(f):
    """
    Decorator for TALES auto-called functions.

    An auto-called function will be called (with the context as its sole 
    parameter) even if it has a subpath or if no-call is used.
    """
    f.tales_type = "auto-call"
    return f


class AdveneContext(simpleTALES.Context):
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
                return val(pathList[i+2:])
            elif tales_type == "auto-call":
                val = val(self)
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
            except TypeError:
                try:
                    return val[int(path)]
                except Exception:
                    raise simpleTALES.PATHNOTFOUNDEXCEPTION

    def _eval(self, val):
        if callable(val):
            if getattr(val, "tales_type", None) == "context-function":
                return val(self)
            else:
                return val()
        else:
            return val


