CORBAMODULE=MediaControl
CORBAIDL=/usr/share/idl/$(CORBAMODULE).idl

corba-generate-typelib:
	orbit-idl-2 --imodule $(CORBAIDL)
	gcc -fPIC -c $(CORBAMODULE)-imodule.c `pkg-config --cflags ORBit-2.0`
	gcc -shared -o $(CORBAMODULE).so $(CORBAMODULE)-imodule.o `pkg-config --libs ORBit-2.0`

# Create the translation file
create-po:
	xgettext -j -L Python advenetool *.py advene.gladestrings
