"""GUI to import package elements.
"""
import sys
import gtk
import gobject

from gettext import gettext as _

class HomogeneousImporter:
    COLUMN_ELEMENT=0
    COLUMN_LABEL=1
    COLUMN_ID=2
    COLUMN_IMPORTED=3
    
    def __init__(self, controller=None, sourcepackage=None,
                 elementtype=None):
        self.controller=controller
        self.sourcepackage=sourcepackage
        # Name of the elementtype: views, annotationTypes,
        # relationTypes, schemas
        self.elementtype=elementtype
        self.widget=self.build_widget()

    def is_imported(self, el):
        """Check wether the element is imported in the controller's package."""
        check=[ v.uri
                for v in getattr(self.controller.package, self.elementtype)
                if v.isImported() ]
        return ( el.uri in check )
    
    def build_liststore(self):
        # Store reference to the element, string representation (title and id)
        # and boolean indicating wether it is imported or not
        store=gtk.ListStore(gobject.TYPE_PYOBJECT,
                            gobject.TYPE_STRING,
                            gobject.TYPE_STRING,
                            gobject.TYPE_BOOLEAN)
        source=getattr(self.sourcepackage, self.elementtype)        
        for el in source:
            store.append([el,
                          el.title or el.id,
                          el.id,
                          self.is_imported(el)])
        return store

    def toggled_cb(self, renderer, path, model, column):
        model[path][column] = not model[path][column]
        # FIXME: should update the self.controller.package accordingly
        # But we need the corresponding methods in the model first
        print "Toggled %s" % str(path)
        return False
    
    def build_widget(self):
        vbox=gtk.VBox()
        
        self.store=self.build_liststore()

        treeview=gtk.TreeView(model=self.store)

        renderer = gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        renderer.connect('toggled', self.toggled_cb, self.store, self.COLUMN_IMPORTED)
        
        column = gtk.TreeViewColumn(_('Imported?'), renderer,
                                    active=self.COLUMN_IMPORTED)
        treeview.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Id'), renderer,
                                    text=self.COLUMN_ID)
        treeview.append_column(column)        

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Title'), renderer,
                                    text=self.COLUMN_LABEL)
        treeview.append_column(column)
        
        vbox.add(treeview)
        vbox.show_all()
        
        return vbox
    
class Importer:
    def __init__(self, controller=None, sourcepackage=None):
        self.controller=controller
        self.sourcepackage=sourcepackage
        self.widget=self.build_widget()

    def build_widget(self):
        vbox=gtk.VBox()

        vbox.add(gtk.Label("Elements imported from %s" % self.sourcepackage.uri))
                 
        # Build a notebook with different elements
        notebook=gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_TOP)
        notebook.popup_enable()
        notebook.set_scrollable(True)
        
        for t in ('views', 'schemas', 'annotationTypes', 'relationTypes'):
            hi=HomogeneousImporter(controller=self.controller,
                                   sourcepackage=self.sourcepackage,
                                   elementtype=t)
            l=gtk.Label(t.capitalize())
            notebook.append_page(hi.widget, l)
            
        vbox.add(notebook)
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
    if len(sys.argv) < 3:
        print "Should provide two package names"
        sys.exit(1)

    class DummyController:
        pass

    from advene.model.package import Package
    
    controller=DummyController()
    
    controller.package = Package (uri=sys.argv[1])
    controller.gui=None

    sourcepackage=Package(uri=sys.argv[2])

    i=Importer(controller=controller,
               sourcepackage=sourcepackage)
    window=i.popup()
    
    window.connect ("destroy", lambda e: gtk.main_quit())

    gtk.main ()

