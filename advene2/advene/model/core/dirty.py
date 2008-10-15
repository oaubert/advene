class DirtyMixin:
    """I provide functionality of dirty/clean objects.

    An object is dirty when its internal state is not consistent with a 
    reference state (another object, a database, etc.). This mixin provides an
    `add_cleaning_operation` method to define operations required to update the
    reference state. The readonly property dirty is True whenever there are
    pending operations. The clean method tries to execute all pending
    operations.

    This mixin also ensure that dirty elements are not garbage collected, by
    keeping a reference on them.
    """

    __pending = None
    __lastchance = {}

    def add_cleaning_operation(self, operation, *args, **kw):
        """Add pending operation to be performed on clean.

        Note that each operation can only be added once; if added again, it will
        be ignored, assuming that the arguments are the same. It is an error to 
        submit twice the same operation with different arguments.
        """
        pending = self.__pending
        if pending is None:
            pending = self.__pending = {}
        assert operation not in pending or pending[operation] == (args, kw)
        pending[operation] = (args, kw)
        DirtyMixin.__lastchance[id(self)] = self

    @property
    def dirty(self):
        return bool(self.__pending)

    def clean(self):
        """Execute pending operations until all are done or an excetion is \
        raised.

        Note that the order of the executions is not necessarily the order of
        submission. If an exception is raised, the operation is put back in
        the pending list.
        """
        pending = self.__pending
        while pending:
            operation, args_kw = pending.popitem()
            try:
                args, kw = args_kw
                operation(*args, **kw)
            except:
                pending[operation] = args_kw
                raise
        DirtyMixin.__lastchance.pop(id(self), None)
