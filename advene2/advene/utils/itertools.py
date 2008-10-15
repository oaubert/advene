from heapq import heapify, heapreplace, heappop

class _IterHead(object):
    __slots__ = ["head", "iter"]

    def __init__(self, iter):
        self.iter = iter
        self.fetch_next()

    def fetch_next(self):
        try:
            self.head = self.iter.next()
        except StopIteration:
            self.head = None

    def __cmp__(self, other):
        return cmp(self.head, other.head)

def interclass(*iterables):
    """
    Takes a number of sorted iterables, and inteclass them, suppressing 
    doublons.
    """
    h = [ _IterHead(iter(i)) for i in iterables ]
    heapify(h)
    prev = None

    while h:
        ih = h[0]
        ihh = ih.head
        if ihh is not None:
            if ihh != prev:
                yield ihh
                prev = ihh
            ih.fetch_next()
        # ih.head may have changed with fetch_next, so don't use ihh anymore:
        if ih.head is not None:
            heapreplace(h, ih)
        else:
            heappop(h)


