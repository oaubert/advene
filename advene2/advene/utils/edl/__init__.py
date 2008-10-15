"""
I provide classes for managins Edit Decision Lists.
"""

#TODO learn to use gettext
_ = lambda x:x

class EDL(object):
    """
    A simple Edit Decision List.

    Decisions must implement three methods: ``__str__'' (localized), ``undo''
    and ``redo''.
    """
    def __init__(self, name):
        self._name = name
        self._list = l = []
        self._stack = [l]
        self._undoing = False
        self.trace = None

    def append(self, ed):
        if not self._undoing:
            self._stack[-1].append(ed)
            tr = self.trace
            if tr is not None:
                tr.append(ed)

    def begin_complex_ED(self, name):
        if not self._undoing:
            edl = self.__class__(name)
            edl.undo = edl.undo_all
            tr = self.trace
            if tr is not None:
                tr.append(name)
            s = self._stack
            s[-1].append(edl)
            s.append(edl)

    def end_complex_ED(self):
        assert len(self._stack) > 1
        if not self._undoing:
            self._stack.pop()
            tr = self.trace
            if tr is not None:
                tr.append(None)
        

    def __str__(self):
        return self._name

    def __len__(self):
        return len(self._list)

    def __iter__(self):
        return iter(self._list)

    def reversed(self):
        l = self._list
        for i in xrange(len(l)-1, -1, -1):
            d = l[i]
            if isinstance(d, EDL):
                for d2 in d.reversed():
                    yield d2
            else:
                yield d

    def undo_one(self):
        if len(self._stack) != 1:
            raise EdlException("Cannot undo during complex ED: %s" %
                                self._stack[-1])
        self._undoing = True
        d = self._list.pop()
        d.undo()
        self._undoing = False
        tr = self.trace
        if tr is not None:
            tr.append(Undo(d))
        return d

    def undo_all(self):
        l = self._list
        while(l): self.undo_one()

    def redo(self):
        for d in self:
            d.redo()


class Undo(object):
    def __init__(self, decision):
        if isinstance(decision, Undo) and isinstance(decision.decision, Undo):
            decision = decision.decision.decision
        self.__decision = decision        

    @property
    def decision(self):
        return self.__decision

    def __str__(self):
        d = self.__decision
        if isinstance(d, Undo):
            return _("Redo %s") % (d.decision,)
        else:
            return _("Undo %s") % (d,)


class EdlException(Exception):
    pass
