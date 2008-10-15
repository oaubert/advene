# backend related exceptions

class WrongFormat(Exception):
    """
    I am raised whenever a backend is badly formatted.
    """
    pass

class NoSuchPackage(Exception):
    """
    I am raised whenever a backend is required for an inexisting package.
    """
    pass

class PackageInUse(Exception):
    """
    I am raised whenever an attempt is made to bind a Package instance to a
    backend already bound, or to create an existing (bound or not) Package.
    The message can either be the other Package instance, if available, or the
    package backend url.
    """
    def __str__ (self):
        if isinstance(self.message, basestring):
            return self.message
        else:
            return self.message._id # a package instance
    pass

class InternalError(Exception):
    """I am raised whenever a backend encounters an internal error.

    I wrap the original exception, if any, as my second argument.
    """
    def __init__(self, msg, original_exception=None, *args):
        self.args = (msg, original_exception) + args
    def __str__(self):
        return "%s\nOriginal message:\n%s" % self.args[:2]

# utility class

class ClaimFailure(object):
    """Failure code of a claims_for_* method.

    A ClaimFailure always has a False truth value. Furthermore, it has an
    ``exception`` attribute containing, if not None, an exception explaining
    the failure.
    """

    def __init__(self, exception=None):
        self.exception = exception

    def __nonzero__(self):
        return False

    def __repr__(self):
        return "ClaimFailure(%r)" % self.exception


