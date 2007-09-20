name=$(shell basename `pwd`)

doc: FORCE
	PYTHONPATH=$(shell pwd)/lib find lib/advene -name '*.py' | xargs -n 500 epydoc -o doc/html -n Advene --inheritance=grouped

archive:
	tar -C .. --exclude=.svn --exclude=\*~ -cvzf ../$(name).tgz $(name)

FORCE:

translation:
	cd po; $(MAKE) update
