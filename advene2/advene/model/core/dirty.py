class DirtyMixin:
    """I provide functionality of dirty/clean objects.

    An object is dirty when its internal state is not consistent with a 
    reference state (another object, a database, etc.). This mixin provides 
    `add_cleaning_operation` and `add_once_cleaning_operation` method to define
    operations required to update the reference state.
    The readonly property dirty is True whenever there are pending operations.
    The clean method tries to execute all pending operations in the order they
    were submitted (quite so, see `add_cleaning_operation_once`).

    This mixin also ensure that dirty elements are not garbage collected, by
    keeping a reference on them.
    """

    __pending_dict = None
    __pending_list = None
    __lastchance = {} # class attribute

    def add_cleaning_operation(self, operation, *args, **kw):
        """Add pending operation to be performed on clean.

        Cleaning operations added that way will be performed in the order they
        were submitted.
        """
        self._add_cleaning_op(operation, args, kw, False)

    def add_cleaning_operation_once(self, operation, *args, **kw):
        """Add pending operation to be performed *only once* on clean.

        If the same operation has already been submitted, subsequent calls
        will be ignored. The first occurence will be used to determine the
        order of operations.

        Note that its an error to submit the same operation to
        `add_cleaning_operation` and `add_cleaning_operation_once`, and it is
        an error to submit the same operation with *different arguments* to
        `add_cleaning_operation_once`. In those cases, the beheviour is not
        specified.
        """
        self._add_cleaning_op(operation, args, kw, True)

    def _add_cleaning_op (self, op, args, kw, once):
        pending_d = self.__pending_dict
        if pending_d is None:
            pending_d = self.__pending_dict = {}
            self.__pending_list = []
        pending_l = self.__pending_list

        tpl = (op, args, kw)
        assert not op in pending_d  or (once and pending_d[op] == tpl[1:])
        if once:
            if op in pending_d:
                return
            pending_d[op] = tpl[1:]
        pending_l.append(tpl)
        DirtyMixin.__lastchance[id(self)] = self

    @property
    def dirty(self):
        return bool(self.__pending_list)

    def clean(self):
        """Execute pending operations until all are done or an excetion is \
        raised.

        Note that the order of the executions is not necessarily the order of
        submission. If an exception is raised, the operation is put back in
        the pending list.
        """
        pending_l = self.__pending_list
        pending_d = self.__pending_dict
        while pending_l:
            operation, args, kw = pending_l.pop(0)
            try:
                operation(*args, **kw)
            except:
                pending_l.insert(0, (operation, args, kw))
                raise
            pending_d.pop(operation, None)
        DirtyMixin.__lastchance.pop(id(self), None)


class DirtyMixinInstantCleaning:
    """I provide an easy replacement for DirtyMixin with instant cleaning.

    There are two possible uses of DirtyMixinInstantCleaning:
    * use it as a superclass of a class required to provide the DirtyMixin
      protocol but for which you do not want differed cleaning
    * before importing any module using this one, set dirty.DirtyMixin to
      DirtyMixinInstantCleaning
    """

    def add_cleaning_operation(self, operation, *args, **kw):
        operation(*args, **kw)

    add_cleaning_operation_once = add_cleaning_operation

    dirty = property(lambda self: None)

    def clean(self): pass
