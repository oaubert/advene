class __UniversalContext:
    def __contains__(self, other):
        return 1

universalContext = __UniversalContext()


class __ContextFactory(dict):
    """A context class manager.
    
       Context classes are registered with the 'register' method.
       They are retrieved with the dict [] operator.
       Context classes must verify the following:
       - have a getNamespaceUrl() static or class method
       - have a getLocalName() static or class method
       - have a getAttributes() method returning a dict
       - they should be unmutable: the right way of changing the context of
         an annotation is to re-set it rather than modifying the existing one
    """

    def __init__(self):
        dict.__init__(self)

    def __setitem__(self, key, value):
        raise TypeError("read-only dictionnary! use x.register(cls) instead")

    def __getitem__(self, key):
        try:
            return dict__getitem__(self, key)
        except KeyError:
            return _universalContext

    def register(self, cls):
        """Register an element in the context. The key will be obtained with
        cls.getLocalName()"""
        key = cls.getNamespaceUrl(), cls.getLocalName()
        dict.__setitem__(self, key, cls)

contextFactory = __ContextFactory()
