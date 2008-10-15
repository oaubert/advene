from os import path, listdir
from sys import path as pythonpath
from unittest import main, TestCase, TestSuite

dirname = path.dirname(__file__)
pythonpath.append(dir)

for i in listdir(dirname):
    if i.endswith(".py") and i != "all.py":
        modulename = i[:-3]
        m = __import__(modulename, globals(), locals(), ["*",], level=0)
        for j in dir(m):
            a = getattr(m,j)
            if isinstance(a,type) and issubclass(a, (TestCase, TestSuite)):
                globals()[j] = a

main()
