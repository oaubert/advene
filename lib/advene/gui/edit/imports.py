"""GUI to import package elements.
"""
import sys
import os

import pygtk
pygtk.require('2.0')
import gtk
import gobject

from gettext import gettext as _

import advene.gui.popup

class TreeViewImporter:
    COLUMN_ELEMENT=0
    COLUMN_LABEL=1
    COLUMN_ID=2
    COLUMN_IMPORTED=3
    COLUMN_URI=4
    
    types_mapping={'view': 'views',
                   'schema': 'schemas',
                   'annotation-type': 'annotationTypes',
                   'relation-type': 'relationTypes'}
    
    def __init__(self, controller=None):
        self.controller=controller
        self.widget=self.build_widget()

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)
        
        if button == 3:
            if event.window is widget.get_bin_window():
                model = widget.get_model()
                t = widget.get_path_at_pos(x, y)
                if t is not None:
                    path, col, cx, cy = t
                    node=model[path][self.COLUMN_ELEMENT]
                    widget.get_selection().select_path (path)
                    menu = advene.gui.popup.Menu(node, controller=self.controller)
                    menu.popup()
                    retval = True
        return retval

    def is_imported(self, el):
        """Check wether the element is imported in the controller's package."""
        source=None
        try:
            at=self.types_mapping[el.viewableClass]
            source=getattr(self.controller.package, at)
        except AttributeError:
            print "Exception on %s" % str(el)
            return False
        l=[ e.uri for e in source if e.isImported() ]
        return (el.uri in l)
    
    def build_liststore(self):
        # Store reference to the element, string representation (title and id)
        # and boolean indicating wether it is imported or not
        store=gtk.TreeStore(
            gobject.TYPE_PYOBJECT,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_BOOLEAN,
            gobject.TYPE_STRING,
            )
        
        for i in self.controller.package.imports:
            p=i.package
            packagerow=store.append(parent=None,
                                    row=[p,
                                         p.title,
                                         i.getAs(),
                                         True,
                                         p.uri])
            viewsrow=store.append(parent=packagerow,
                                  row=[p.views,
                                       _('Views'),
                                       _('Views'),
                                       False,
                                       ''])
            for v in p.views:
                store.append(parent=viewsrow,
                             row=[v,
                                  v.title or v.id,
                                  v.id,
                                  self.is_imported(v),
                                  v.uri]) 

            schemasrow=store.append(parent=packagerow,
                                    row=[p.schemas,
                                         _('Schemas'),
                                         _('Schemas'),
                                         False,
                                         ''])
            for s in p.schemas:
                srow=store.append(parent=schemasrow,
                                  row=[s,
                                       s.title or s.id,
                                       'FIXME:id',
                                       self.is_imported(s),
                                       s.uri])
                for at in s.annotationTypes:
                    store.append(parent=srow,
                                 row=[at,
                                      at.title or at.id,
                                      "FIXME:at.id",
                                      self.is_imported(at),
                                      at.uri])
                for rt in s.relationTypes:
                    store.append(parent=srow,
                                 row=[rt,
                                      rt.title or rt.id,
                                      "FIXME:rt.id",
                                      self.is_imported(rt),
                                      rt.uri])
        return store

    def toggled_cb(self, renderer, path, model, column):
        model[path][column] = not model[path][column]
        # FIXME: should update the self.controller.package accordingly
        # But we need the corresponding methods in the model first
        
        print "Toggled %s" % model[path][self.COLUMN_LABEL]
        return False

    def build_widget(self):
        vbox=gtk.VBox()

        # FIXME: implement package removal from the list
        # FIXME: implement "import all elements" actions (popup menu?)
        self.store=self.build_liststore()

        treeview=gtk.TreeView(model=self.store)
        treeview.connect("button_press_event", self.tree_view_button_cb)

        renderer = gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        renderer.connect('toggled', self.toggled_cb, self.store, self.COLUMN_IMPORTED)
        
        column = gtk.TreeViewColumn(_('Imported?'), renderer,
                                    active=self.COLUMN_IMPORTED)
        treeview.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Id'), renderer,
                                    text=self.COLUMN_ID)
        column.set_resizable(True)
        treeview.append_column(column)        

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Title'), renderer,
                                    text=self.COLUMN_LABEL)
        column.set_resizable(True)
        treeview.append_column(column)
        
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('URI'), renderer,
                                    text=self.COLUMN_URI)
        column.set_resizable(True)
        treeview.append_column(column)

        
        vbox.add(treeview)
        vbox.show_all()
        
        return vbox
    
class Importer:
    def __init__(self, controller=None, sourcepackage=None):
        self.controller=controller
        self.sourcepackage=sourcepackage
        self.widget=self.build_widget()

    def add_package_cb(self, button, fs):
        """Import a new package."""
        file_ = fs.get_property ("filename")

        # Determine a default alias for the filename
        alias=os.path.splitext( os.path.basename(file_) )[0]
        alias=alias.lower()
        
        d = gtk.Dialog(title='Enter the package alias',
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                                 gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT ))
        l=gtk.Label(_("Specify the alias which will be used\nas prefix for the package's elements."))
        l.show()
        d.vbox.add(l)
        
        e=gtk.Entry()
        e.show()
        e.set_text(alias)
        d.vbox.add(e)

        res=d.run()
        if res == gtk.RESPONSE_ACCEPT:
            try:
                retval=e.get_text()
            except ValueError:
                retval=None
        else:
            retval=None

        d.destroy()
        if retval is None:
            # The user canceled the action
            return True

        alias=retval

        # FIXME: to be implemented in the model
        #self.controller.package.importPackage(uri=file_, alias=alias)
        print "Will be implemented soon."
        return True
        
    def add_package(self, button=None):
        if not self.controller.gui:
            return False
        self.controller.gui.file_selector (callback=self.add_package_cb,
                                           label=_("Choose the package to import"))
        return True
    
    def build_widget(self):
        vbox=gtk.VBox()

        vbox.pack_start(gtk.Label("Elements imported into %s" % self.controller.package.title),
                        expand=False)

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add(scroll_win)
        
        ti=TreeViewImporter(controller=self.controller)
        scroll_win.add_with_viewport(ti.widget)

        hb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", self.add_package)
        hb.pack_start(b, expand=False)

        vbox.pack_start(hb, expand=False)

        hb.show_all()
        
        return vbox

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title (_("Package %s") % (self.controller.package.title or _("No title")))

        vbox = gtk.VBox()
        window.add (vbox)

        vbox.add (self.widget)
        if self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb, window, self)

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'importeditor')

        self.buttonbox = gtk.HButtonBox()

        b = gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect("clicked", lambda w: window.destroy ())
        self.buttonbox.add (b)

        vbox.pack_start(self.buttonbox, expand=False)
        
        window.show_all()
        
        return window


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    class DummyController:
        pass

    from advene.model.package import Package
    
    controller=DummyController()
    
    controller.package = Package (uri=sys.argv[1])
    controller.gui=None

    i=Importer(controller=controller)
    window=i.popup()
    
    window.connect ("destroy", lambda e: gtk.main_quit())

    gtk.main ()

