class MimeTypeException (Exception):
    pass

class MimeTypeValueError (MimeTypeException, ValueError):
    pass

class MimeType (object):
    """
    TODO
    """
    def __init__ (self, value):
        """
        Checks that this string looks like a valid MIME type.
        (the second member is not checked for validity)
        """
        try:
            type, subtype = str(value).split ('/')
        except ValueError:
            raise MimeTypeValueError ("%s has to few or too many /'s" % value)
        self.setType (type)
        self.setSubtype (subtype)

    def __repr__ (self):
        return "<%s.%s '%s' at 0x%x>" % (self.__module__,
                                         self.__class__.__name__,
                                         str(self),
                                         id(self))
    def __str__ (self):
        return '/'.join( (self.type, self.subtype) )

    def __ge__ (self, other):
        if not isinstance (other, MimeType):
            raise MimeTypeException ('Can not compare mime type to %s' % 
                                     repr (other))
        return other.isMoreSpecificThan (self)

    def __le__ (self, other):
        if not isinstance (other, MimeType):
            raise MimeTypeException ('Can not compare mime type to %s' % 
                                     repr (other))
        return self.isMoreSpecificThan (other)

    def __gt__ (self, other):
        if not isinstance (other, MimeType):
            raise MimeTypeException ('Can not compare mime type to %s' % 
                                     repr (other))
        return other.isMoreSpecificThan (self, strictly=True)

    def __lt__ (self, other):
        if not isinstance (other, MimeType):
            raise MimeTypeException ('Can not compare mime type to %s' % 
                                     repr (other))
        return self.isMoreSpecificThan (other, strictly=True)

    def getType (self):
        return self.__type

    def setType (self, type):
        self.checkType (type, exception=True)
        self.__type = type

    type = property (getType, setType)

    def getSubtype (self):
        return self.__subtype

    def setSubtype (self, subtype):
        self.checkSubtype (subtype, exception=True)
        self.__subtype = subtype

    subtype = property (getSubtype, setSubtype)

    def isGeneric (self):
        return self.__type == '*' or self.__subtype == '*'

    def isMoreSpecificThan (self, other, strictly=False):
        if not isinstance (other, MimeType):
            raise MimeTypeException ('Can not compare mime type to %s' % 
                                     repr (other))
        return (
            (
                other.__type == '*'
                and (not strictly or self.__type != '*')
            )
            or (
                self.__type == other.__type
                and (
                    other.__subtype == '*'
                    or (not strictly and self.__subtype == other.__subtype)
                )
                and (not strictly or self.__subtype != '*')
            )
        )

        

    def checkType (type, exception=False):
        r = (
          type in ('*',
                   'text',
                   'multipart',
                   'application',
                   'message',
                   'image',
                   'audio',
                   'video',)
          or (
              (type.startswith ('x-') or type.startswith ('X-'))
              and MimeType._check_token (type[2:], exception)
          )
        )
        if not r and exception:
            raise MimeTypeValueError ("%s is not a valid type" % type)
        return r
    checkType = staticmethod(checkType)

    def checkSubtype (self, subtype, exception=False):
        type = self.__type
        r = type != '*' or subtype == '*'
        r = r and self._check_token (subtype, exception)
        if not r and exception:
            raise MimeTypeValueError ("%s/%s is not a valid MIME type" %
                                      (type, subtype))
        return r

    def _check_token (token, exception=False):
        r = True
        for c in token:
            if c.isspace() or c in '()<>@,;:\\"/[]?.=':
                r = False
                break
        if not r and exception:
            raise MimeTypeValueError ("%s is an invalid token" % token)
        return r
    _check_token = staticmethod(_check_token)
