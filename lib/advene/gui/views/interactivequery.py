"""Interactive query.

Display the query results in a view (timeline, tree, etc).
"""
import advene.core.config as config
import time

import gtk

from advene.gui.edit.rules import EditQuery
from advene.model.bundle import AbstractBundle
from advene.rules.elements import Query, Condition
from advene.model.annotation import Annotation

import advene.gui.views.timeline

import advene.util.vlclib as vlclib

class InteractiveQuery:
    def __init__(self, here=None, controller=None):

        if here is None:
            here=controller.package

        self.here=here
        self.controller=controller

        self.querycontainer, self.query = self.get_interactive_query()


        self.window=None

    def get_interactive_query(self):
        l=[ q
            for q in self.controller.package.queries
            if q.id == '_interactive' ]
        if l:
            q=Query()
            q.from_dom(l[0].content.model)
            return l[0], q
        else:
            # Create the query
            el=self.controller.package.createQuery(ident='_interactive')
            el.author=config.data.userid
            el.date=time.strftime("%Y-%m-%d")
            el.title=_("Interactive query")

            # Create a basic query
            q=Query(source="here/rootPackage/annotations",
                    rvalue="element")
            q.add_condition(Condition(lhs="element/content/data",
                                      operator="contains",
                                      rhs="string:a"))

            el.content.data=q.xml_repr()
            el.content.mimetype='application/x-advene-simplequery'
            
            self.controller.package.queries.append(el)
            
            self.controller.notify('QueryCreate', query=el)
            return el, q

    def validate(self, button=None):
        # Get the query
        l=self.eq.invalid_items()
        if l:
            self.controller.log(_("Invalid query.\nThe following fields have an invalid value:\n%s")
                     % ", ".join(l))
            return True
        self.eq.update_value()
        # Store the query itself in the _interactive query
        self.querycontainer.content.data = self.eq.model.xml_repr()
        
        self.window.destroy()
        
        c=self.controller.build_context(here=self.here)
        res=c.evaluateValue("here/query/_interactive")

        if (isinstance(res, list) or isinstance(res, tuple)
            or isinstance(res, AbstractBundle)):
            # Assume it is a list of annotations
            l=[ a for a in res if isinstance(a, Annotation) ]
            if l:
                self.controller.log(_("Displaying %s of %d elements")
                         % (vlclib.format_element_name("annotation", len(l)),
                            len(res)))
                t = advene.gui.views.timeline.TimeLine (l,
                                                        minimum=0,
                                                        controller=self.controller)
                window=t.popup()
                window.set_title(_("Results of _interactive query"))
            else:
                dialog = gtk.MessageDialog(
                    None, gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
                    _("Empty list result."))
                dialog.set_position(gtk.WIN_POS_MOUSE)
                dialog.run()
                dialog.destroy()
        else:
            # Display a dialog with the value
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                _("Result:\n%s") % unicode(res))
            dialog.set_position(gtk.WIN_POS_MOUSE)
            dialog.run()
            dialog.destroy()
        return True
    
    def cancel(self, button=None):
        self.window.destroy()
        return True
    
    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'interactivequery')

        window.set_title (_("Query element %s") % (self.controller.get_title(self.here)))

        vbox = gtk.VBox()

        self.eq=EditQuery(self.query,
                          editable=True,
                          controller=self.controller)
        vbox.add(self.eq.widget)
        
        if self.controller.gui:
            window.connect ("destroy", self.controller.gui.close_view_cb,
                            window, self)

        hb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect ("clicked", self.validate)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect ("clicked", self.cancel)
        hb.pack_start(b, expand=False)

        vbox.pack_start(hb, expand=False)

        window.add(vbox)

        window.show_all()
        self.window=window
        return window
        
