doc: FORCE
	PYTHONPATH=$(shell pwd)/lib find lib -name '*.py' | xargs -n 500 epydoc -o doc/html -n Advene --inheritance=grouped

FORCE:

translation:
	cd po; $(MAKE) update
