#
# This file is part of Advene.
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Interactive query.

Display the query results in a view (timeline, tree, etc).
"""
import advene.core.config as config
import time
from gettext import gettext as _
import pprint

import gtk

from advene.gui.edit.rules import EditQuery
from advene.model.bundle import AbstractBundle
from advene.rules.elements import Query, Condition
from advene.model.annotation import Annotation
from advene.model.tal.context import AdveneTalesException
from advene.gui.views.editaccumulator import EditAccumulator
import advene.gui.util

from advene.gui.views.timeline import TimeLine

import advene.util.helper as helper

class InteractiveQuery:
    def __init__(self, here=None, controller=None, source="package/annotations"):

        if here is None:
            here=controller.package

        self.here=here
        self.source=source
        self.controller=controller

        self.querycontainer, self.query = self.get_interactive_query()


        self.window=None

    def get_interactive_query(self):
        l=helper.get_id(self.controller.package.queries, '_interactive')
        if l:
            q=Query()
            q.from_dom(l.content.model)
            return l, q
        else:
            # Create the query
            el=self.controller.package.createQuery(ident='_interactive')
            el.author=config.data.userid
            el.date=time.strftime("%Y-%m-%d")
            el.title=_("Interactive query")

            # Create a basic query
            q=Query(source=self.source,
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
        # Check if we are doing a short search
        if not self.advanced.get_expanded():
            # The advanced query is not shown. Use the self.entry
            s=self.entry.get_text()
            if self.ignorecase.get_active():
                s=s.lower()
                res=[ a for a in self.controller.package.annotations if s in a.content.data.lower() ]
            else:
                res=[ a for a in self.controller.package.annotations if s in a.content.data ]
        else:
            # Get the query
            l=self.eq.invalid_items()
            if l:
                self.controller.log(_("Invalid query.\nThe following fields have an invalid value:\n%s")
                         % ", ".join(l))
                return True
            self.eq.update_value()
            # Store the query itself in the _interactive query
            self.querycontainer.content.data = self.eq.model.xml_repr()

            c=self.controller.build_context(here=self.here)
            try:
                res=c.evaluateValue("here/query/_interactive")
            except AdveneTalesException, e:
                # Display a dialog with the value
                advene.gui.util.message_dialog(_("TALES error in interactive expression:\n%s" % str(e)),
                    icon=gtk.MESSAGE_ERROR)
                return True

        # Close the search window
        self.window.destroy()

        # Present choices to display the result
        if (isinstance(res, list) or isinstance(res, tuple)
            or isinstance(res, AbstractBundle)):

            if not res:
                advene.gui.util.message_dialog(_("Empty list result"))
                return True

            # Check if there are annotations
            l=[ a for a in res if isinstance(a, Annotation) ]
            cr=len(res)
            cl=len(l)

            w=gtk.Window()
            w.set_title(_("Interactive evaluation result"))
            v=gtk.VBox()
            w.add(v)

            if cr == cl:
                t=_("Result is a list of %d annotations.") % cr
            else:
                t=_("Result is a list of  %(number)d elements with %(elements)s.") % { 
                    'elements': helper.format_element_name("annotation", len(l)),
                    'number': len(res)}
            v.add(gtk.Label(t))

            hb=gtk.VButtonBox()
            v.pack_start(hb)
            if cl:
                b=gtk.Button(_("Display annotations in timeline"))
                b.connect('clicked', lambda b: self.open_in_timeline(l))
                hb.add(b)
                b=gtk.Button(_("Highlight annotations"))
                b.connect('clicked', lambda b: self.highlight_annotations(l))
                hb.add(b)
                b=gtk.Button(_("Unhighlight annotations"))
                b.connect('clicked', lambda b: self.unhighlight_annotations(l))
                hb.add(b)
            b=gtk.Button(_("Edit elements"))
            b.connect('clicked', lambda b: self.open_in_edit_accumulator(res))
            hb.add(b)
            b=gtk.Button(_("Open in python evaluator"))
            b.connect('clicked', lambda b: self.open_in_evaluator(res))
            hb.add(b)
            b=gtk.Button(stock=gtk.STOCK_CLOSE)
            b.connect('clicked', lambda b: w.destroy())
            hb.add(b)
            
            w.show_all()
        else:
            advene.gui.util.message_dialog(_("Result:\n%s") % unicode(res))
        return True

    def open_in_timeline(self, l):
        t = TimeLine (l,
                      minimum=0,
                      controller=self.controller)
        window=t.popup()
        window.set_title(_("Results of _interactive query"))
        return True

    def highlight_annotations(self, l):
        for a in l:
            self.controller.notify("AnnotationActivate", annotation=a)
        return True

    def unhighlight_annotations(self, l):
        for a in l:
            self.controller.notify("AnnotationDeactivate", annotation=a)
        return True

    def open_in_edit_accumulator(self, l):
        if self.controller.gui.edit_accumulator:
            a=self.controller.gui.edit_accumulator()
        else:
            a=EditAccumulator(controller=self.controller, scrollable=True)

        for e in l:
            a.edit(e)

        if a != self.controller.gui.edit_accumulator:
            window=a.popup()
            window.set_title(_("Results of _interactive query"))
        
        return True

    def open_in_evaluator(self, l):
        p=self.controller.package
        try:
            a=p.annotations[-1]
        except IndexError:
            a=None

        ev=advene.gui.evaluator.Window(globals_=globals(),
                                       locals_={'package': p,
                                                'result': l,
                                                'p': p,
                                                'a': a,
                                                'c': self.controller,
                                                'self': self,
                                                'pp': pprint.pformat },
                                       historyfile=config.data.advenefile('evaluator.log', 'settings')
                                       )
        w=ev.popup()
        b=gtk.Button(stock=gtk.STOCK_CLOSE)

        def close_evaluator(*p):
            ev.save_history()
            w.destroy()
            return True

        b.connect("clicked", close_evaluator)
        b.show()
        ev.hbox.add(b)

        self.controller.gui.init_window_size(w, 'evaluator')
        
        w.set_title(_("Results of _interactive query"))
        ev.set_expression('result')
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

        l=gtk.Label(_("Search for text in the content of annotations"))
        vbox.pack_start(l, expand=False)

        self.entry=gtk.Entry()
        vbox.pack_start(self.entry, expand=False)

        self.ignorecase=gtk.CheckButton(_("Ignore case"))
        self.ignorecase.set_active(True)
        vbox.pack_start(self.ignorecase, expand=False)
        
        self.advanced = gtk.Expander ()
        self.advanced.set_label (_("Advanced search"))
        self.advanced.set_expanded(False)

        vbox.add(self.advanced)

        self.eq=EditQuery(self.query,
                          editable=True,
                          controller=self.controller)
        self.advanced.add(self.eq.widget)

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


        def handle_key_press_event(widget, event):
            if event.keyval == gtk.keysyms.Return:
                self.validate()
                return True
            elif event.keyval == gtk.keysyms.Escape:
                self.cancel()
                return True
            return False

        window.connect('key-press-event', handle_key_press_event)

        window.add(vbox)

        window.show_all()
        self.entry.grab_focus()
        self.window=window
        advene.gui.util.center_on_mouse(window)

        return window

