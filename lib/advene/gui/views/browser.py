#! /usr/bin/env python

# Advene browser, a la NeXT's workspace manager

import sys

# Advene part
import advene.core.config as config
from advene.model.package import Package
from advene.model.exception import AdveneException

import advene.model.tal.context
import inspect

from gettext import gettext as _

import gtk
import gobject

class BrowserColumn:
    def __init__(self, element=None, name="", callback=None, parent=None):
        self.model=element
        self.name=name
        self.callback=callback
        self.next=None
        self.previous=parent
        self.widget=self.build_widget()

    def get_widget(self):
        return self.widget

    def get_valid_members (self, el):
        """Return a list of strings, valid members of the object in TALES.

        This method is used to generate the contextual completion menu
        in the web interface.
        
        @param el: the object to examine (often an Advene object)
        @type el: any

        @return: the list of elements which are members of the object,
                 in the TALES meaning.
        @rtype: list
        """
        # FIXME: copy/pasted from adveneserver. We should share it (or better,
        # it should be provided by advenelib)
        l = []
        try:
            l.extend(el.ids())
        except AttributeError:
            try:
                l.extend(el.keys())
            except AttributeError:
                pass

        c = type(el)
        l.extend([e[0]
                  for e in inspect.getmembers(c)
                  if isinstance(e[1], property) and e[1].fget is not None])
    
        # Global methods
        l.extend (advene.model.tal.context.AdveneContext.defaultMethods ())
        
        return l

    def get_liststore(self):
        ls=gtk.ListStore(str)
        if self.model is None:
            return ls
        for att in self.get_valid_members(self.model):
            ls.append([att])
        return ls

    def update(self, element=None, name=""):
        self.liststore.clear()
        for att in self.get_valid_members(element):
            self.liststore.append([att])
        self.model=element
        self.name=name
        self.label.set_label(name)
        # Destroy all following columns
        self.next=None
        return True

    def row_activated(self, widget, treepath, treecolumn):
        att=widget.get_model()[treepath[0]][0]
        if self.callback:
            self.callback(self, att)
        return True

    def on_column_activation(self, widget):
        if self.callback:
            self.callback(self.previous, self.name)
        return True
    
    def on_button_press(self, widget, event):
        att=None
        if event.button == 1:
            selection = widget.get_selection()
            if selection is not None:
                store, it = selection.get_selected()
                if it is not None:
                    att = widget.get_model().get_value (it, 0)
        if att and self.callback:
            self.callback(self, att)
            return True
        return False

    def on_changed_selection(self, selection, model):
        att=None
        if selection is not None:
            store, it = selection.get_selected()
            if it is not None:
                att = model.get_value (it, 0)
        if att and self.callback:
            self.callback(self, att)
            return True
        return False

    def build_widget(self):
        vbox=gtk.VBox()

        self.label=gtk.Button(self.name)
        self.label.connect("clicked", self.on_column_activation)
        vbox.pack_start(self.label, expand=False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add (sw)

        self.liststore = self.get_liststore()
        self.listview = gtk.TreeView(self.liststore)
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Attributes", renderer, text=0)
        column.set_widget(gtk.Label())
        self.listview.append_column(column)

        selection = self.listview.get_selection()
        selection.unselect_all()
        selection.connect('changed', self.on_changed_selection, self.liststore)
        #self.listview.connect("row-activated", self.row_activated)
        #self.listview.connect("button-press-event", self.on_button_press)
        
        sw.add_with_viewport(self.listview)

        vbox.show_all()
        return vbox
        
class Browser:
    def __init__(self, package=None):
        self.package=package
        self.path=[package]
        # 640 / 4
        self.column_width=160
        self.rootcolumn=None
        self.widget=self.build_widget()

    def get_widget(self):
        return self.widget

    def default_options(self):
        return {
            'package_url': "/packages/advene",
            'namespace_prefix': config.data.namespace_prefix,
            'config': config.data.web,
            }

    def clicked_callback(self, columnbrowser, attribute):
        # We could use here=columnbrowser.model, but then the traversal
        # of path is not done and absolute_url does not work
        context = advene.model.tal.context.AdveneContext (here=self.package,
                                                          options=self.default_options())
        path=[]
        col=self.rootcolumn
        while col is not columnbrowser:
            col=col.next
            path.append(col.name)
        path.append(attribute)

        try:
            el=context.evaluateValue("here/%s" % "/".join(path))
        except AdveneException, e:
            # Delete all next columns
            cb=columnbrowser.next
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next
            columnbrowser.next=None
            columnbrowser.listview.get_selection().unselect_all()
            
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
                _("Exception: %s") % e)
            dialog.set_position(gtk.WIN_POS_MOUSE)
            dialog.run()
            dialog.destroy()
            return
        
        self.update_view(path, el)
        
        if columnbrowser.next is None:
            # Create a new columnbrowser
            col=BrowserColumn(element=el, name=attribute, callback=self.clicked_callback,
                              parent=columnbrowser)
            col.widget.set_property("width-request", self.column_width)
            self.hbox.pack_start(col.get_widget(), expand=False)
            columnbrowser.next=col
        else:
            # Delete all next+1 columns (we reuse the next one)
            cb=columnbrowser.next.next
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next
            columnbrowser.next.update(element=el, name=attribute)

        # Scroll the columns
        adj=self.sw.get_hadjustment()
        adj.value = adj.upper - .1
        return True

    def update_view(self, path, element):
        self.pathlabel.set_text("/"+"/".join(path))
        self.typelabel.set_text(unicode(type(element)))
        val=unicode(element)
        if '\n' in val:
            val=val[:val.index('\n')]+'...'
        if len(val) > 80:
            val=val[:77]+'...'
        self.valuelabel.set_text(val)
        return

    def scroll_event(self, widget=None, event=None):
        if event.state & gtk.gdk.CONTROL_MASK:
            a=widget.get_hadjustment()
            if event.direction == gtk.gdk.SCROLL_DOWN:
                val = a.value + a.step_increment
                if val > a.upper - a.page_size:
                    val = a.upper - a.page_size
                if val != a.value:
                    a.value = val
                    a.value_changed ()
                return True
            elif event.direction == gtk.gdk.SCROLL_UP:
                val = a.value - a.step_increment
                if val < a.lower:
                    val = a.lower
                if val != a.value:
                    a.value = val
                    a.value_changed ()
                return True
        return False
                     
    def build_widget(self):
        vbox=gtk.VBox()
        
        self.sw=gtk.ScrolledWindow()
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.sw.connect('scroll_event', self.scroll_event)
        vbox.add(self.sw)
        
        self.hbox = gtk.HBox()

        self.rootcolumn=BrowserColumn(element=self.package, name='package',
                                      callback=self.clicked_callback,
                                      parent=None)
        self.rootcolumn.widget.set_property("width-request", self.column_width)
        self.hbox.pack_start(self.rootcolumn.get_widget(), expand=False)

        self.sw.add_with_viewport(self.hbox)

        def name_label(name, label):
            hb=gtk.HBox()
            l=gtk.Label()
            l.set_markup("<b>%s :</b> " % name)
            hb.pack_start(l, expand=False)
            hb.pack_start(label, expand=False)
            return hb
        
        # Display the type/value of the current element
        self.pathlabel = gtk.Label("/")
        self.pathlabel.set_selectable(True)
        vbox.pack_start(name_label(_("Path"), self.pathlabel), expand=False)

        self.typelabel = gtk.Label("Package")
        vbox.pack_start(name_label(_("Type"), self.typelabel), expand=False)

        self.valuelabel = gtk.Label("package")
        self.valuelabel.set_selectable(True)
        vbox.pack_start(name_label(_("Value"), self.valuelabel), expand=False)
        
        vbox.show_all()
        return vbox

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print _("Should provide a package name")
        sys.exit(1)

    package = Package (uri=sys.argv[1])
    
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_size_request (320, 200)

    def validate_cb (win, package):
        filename="/tmp/package.xml"
        package.save (as=filename)
        print "Package saved as %s" % filename
        gtk.main_quit ()
        
    window.connect ("destroy", lambda e: gtk.main_quit())
    window.set_title (package.title or _("No package title"))
    
    vbox = gtk.VBox()
    
    window.add (vbox)

    browser = Browser(package)
    vbox.add (browser.get_widget())

    hbox = gtk.HButtonBox()
    vbox.pack_start (hbox, expand=gtk.FALSE)

    b = gtk.Button (stock=gtk.STOCK_SAVE)
    b.connect ("clicked", validate_cb, package)
    hbox.add (b)

    b = gtk.Button (stock=gtk.STOCK_QUIT)
    b.connect ("clicked", lambda w: window.destroy ())
    hbox.add (b)

    vbox.set_homogeneous (gtk.FALSE)

    window.show_all()
    gtk.main ()
