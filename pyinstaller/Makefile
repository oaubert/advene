NAME=advene-bin
VERSION := $(shell ../scripts/version)
FULLNAME=$(NAME)-$(VERSION)
PYINSTALLER=${HOME}/src/pyinstaller-snapshot
SPECFILE=advene.pyspec
DESTDIR=$(shell pwd)/$(FULLNAME)
PREFIX=/usr
TGZ=$(FULLNAME).tgz

all:
	python $(PYINSTALLER)/Build.py $(SPECFILE)
	$(RM) advene.exe

install:
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	mkdir -p $(DESTDIR)$(PREFIX)/lib
	cp advene-bin $(DESTDIR)$(PREFIX)/bin
	perl -pi -e 's!^DIR=.+!DIR='$(PREFIX)'/lib/advene-package!' $(DESTDIR)$(PREFIX)/bin/advene-bin
	cp -r advene-package $(DESTDIR)$(PREFIX)/lib

tgz:
	tar -C $(DESTDIR) -czf $(TGZ)  usr

rpm:
	cp advene-bin.spec $(DESTDIR)/$(FULLNAME).spec
	perl -pi -e 's!^Buildroot:.+!Buildroot: '$(DESTDIR)'!;' \
	-e 's!^Version:.+!Version: '$(VERSION)'!;' $(DESTDIR)/$(FULLNAME).spec
	cd $(DESTDIR); find usr -printf '/%p\n' >> $(FULLNAME).spec
	cd $(DESTDIR); rpmbuild -bb --target=i386 $(FULLNAME).spec

clean:
	-$(RM) -rf advene-package
	-$(RM) -rf buildadvene
	-$(RM) -rf $(DESTDIR)
	-$(RM) warnadvene.txt
	-$(RM) $(TGZ)
