all:

MO_DIR = ../locale
PO_DIR = po
DOMAIN = advene

POTFILES: FORCE
	grep -r --include=\*.py -l '\b_(' ../lib > POTFILES
FORCE:

pot: POTFILES
	xgettext --from-code=utf-8 -d $(DOMAIN) -o $(DOMAIN).pot -f POTFILES
	perl -pi -e 's/^.+POT-Creation-Date.+\n//' $(DOMAIN).pot
update-po:
	for po in *.po; do \
		lingua=`basename $$po .po`; \
		mv $$lingua.po $$lingua.old.po; \
		if msgmerge -o $$lingua.po $$lingua.old.po $(DOMAIN).pot; then\
		    rm $$lingua.old.po; \
		else \
		    rm -f $$lingua.po; \
		    mv $$lingua.old.po $$lingua.po; \
		fi \
	done

mo:
	for po in *.po; do\
		lingua=`basename $$po .po`; \
		install -d $(MO_DIR)/$$lingua/LC_MESSAGES/ ; \
		msgfmt -o $(MO_DIR)/$$lingua/LC_MESSAGES/$(DOMAIN).mo $$po ;\
	done

update: POTFILES pot update-po

clean:
	-$(RM) POTFILES
