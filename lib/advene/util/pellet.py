class PelletRow (object):
    def __init__ (self):
        self.l = []
        self.d = {}

    def __get_item__ (self, k):
        if type (k) == type (1):
            return self.l[k]
        else:
            return self.d[k]

    def keys (self):
        return self.d.keys()

    def iterkeys (self):
        return self.d.iterkeys()

    def __iter__ (self):
        return iter (self.l)

    def __len__ (self):
        return len (self.l)

    def _append  (self, k, v):
        self.l.append (v)
        self.d[k] = v

class PelletResult (object):
    """
    Given the output of Pellet as a file,
    produces a PelletResult object with the following attributes:
      - consistent (True or False)
      - reason (textual explanation if not consistent)
      - results (list of results if a query was given)
    """

    def __init__ (self, f):
        print "=== start reading Pellet output"
        self.consistent = None
        self.reason = None
        self.results = []
        for l in f:
            print "===", l
            if l.startswith ("Consistent: "):
                self.consistent = l[12:].startswith("Yes")
            elif l.startswith ("Reason: "):
                self.reason = l[8:-1]
            elif l.startswith ("Query Results"):
                self.results = self.__make_results__ (f)
        print "=== finished reading Pellet output"

    def __make_results__ (self, f):
        r = []
        it = iter (f)
        header = it.next()
        if header.startswith ("NO RESULT"):
            return r
        equals = it.next()
        columns = [ (i.strip(), len(i)) for i in header.split("| ") ]
        r = []
        for l in f:
            if l == "\n": break
            row = PelletRow()
            for ck,cl in columns:
                row._append (ck, l[:cl].strip())
                l = l[cl+2:]
            r.append (row)
        return r

if __name__ == "__main__":
    import sys
    r = PelletResult (sys.stdin)
    print r.consistent
    print r.reason
    for i in r.results:
        print "    %s" % i.d
