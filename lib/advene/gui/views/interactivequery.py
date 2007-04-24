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

from advene.gui.views import AdhocView

from advene.gui.views.timeline import TimeLine

import advene.util.helper as helper

class InteractiveQuery(AdhocView):
    def __init__(self, here=None, controller=None, parameters=None, source="package/annotations"):
        self.view_name = _("Interactive query")
        self.view_id = 'interactive_query'
        self.close_on_package_load = False
        self.contextual_actions = (
            #(_("Refresh"), self.refresh),
            (_("Save view"), self.save_view),
            )
        self.options = {
            'ignore-case': True,
            }
        self.controller=controller
        if here is None:
            here=controller.package
        self.here=here
        self.source=source

        if parameters:
            opt, arg = self.load_parameters(parameters)
            self.options.update(opt)
            for n, v in arg:
                if n == 'source':
                    self.source=v

        self.querycontainer, self.query = self.get_interactive_query()

        self.widget=self.build_widget()

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
            query=s
            label=_("Search for %s") % s
            try:
                source=self.here.annotations
            except AttributeError:
                source=self.controller.package.annotations
            if self.ignorecase.get_active():
                s=s.lower()
                res=[ a for a in source if s in a.content.data.lower() ]
            else:
                res=[ a for a in source if s in a.content.data ]
        else:
            # Get the query
            l=self.eq.invalid_items()
            if l:
                self.controller.log(_("Invalid query.\nThe following fields have an invalid value:\n%s")
                         % ", ".join(l))
                return True
            query=self
            self.eq.update_value()
            # Store the query itself in the _interactive query
            self.querycontainer.content.data = self.eq.model.xml_repr()

            label=_("Expert search")
            c=self.controller.build_context(here=self.here)
            try:
                res=c.evaluateValue("here/query/_interactive")
            except AdveneTalesException, e:
                # Display a dialog with the value
                advene.gui.util.message_dialog(_("TALES error in interactive expression:\n%s" % str(e)),
                    icon=gtk.MESSAGE_ERROR)
                return True

        # Close the search window
        self.close()

        # Set the result attribute for the InteractiveResult view
        self.result=res

        # And display the result in the same viewbook or window
        self.controller.gui.open_adhoc_view('interactiveresult', destination=self._destination, 
                                            label=label, query=query, result=res)
        return True
        
    def cancel(self, button=None):
        self.close()
        return True

    def build_widget(self):
        vbox = gtk.VBox()

        l=gtk.Label(_("Search for text in the content of annotations"))
        vbox.pack_start(l, expand=False)

        self.entry=gtk.Entry()
        self.entry.connect('activate', self.validate)
        vbox.pack_start(self.entry, expand=False)

        self.ignorecase=gtk.CheckButton(_("Ignore case"))
        self.ignorecase.set_active(True)
        vbox.pack_start(self.ignorecase, expand=False)
        
        self.advanced = gtk.Expander ()
        self.advanced.set_label (_("Expert search"))
        self.advanced.set_expanded(False)

        vbox.add(self.advanced)

        self.eq=EditQuery(self.query,
                          editable=True,
                          controller=self.controller)
        self.advanced.add(self.eq.widget)

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

        vbox.connect('key-press-event', handle_key_press_event)
        self.entry.grab_focus()

        return vbox

class InteractiveResult(AdhocView):
    """Interactive result display.
    
    Either we give the query (whose .result attribute will be set), or
    we give a simple result (structure). In the first case, an option
    will be offered to edit the query again.

    FIXME: we should be able to DND action buttons to viewbooks
    """
    def __init__(self, controller=None, parameters=None, query=None, result=None):
        self.view_name = _("Interactive result")
        self.view_id = 'interactive_result'
        self.close_on_package_load = False
        self.contextual_actions = (
            #(_("Refresh"), self.refresh),
            #(_("Save view"), self.save_view),
            )
        self.controller=controller
        self.query=query
        if result is None and isinstance(query, InteractiveQuery):
            result=query.result
        self.result=result

        if isinstance(self.query, InteractiveQuery):
            self.label=_("Result of interactive query")
        else:
            # Must be a string
            self.label=_("Search for %s") % self.query

        self.widget=self.build_widget()

    def build_widget(self):
        v=gtk.VBox()
            
        # FIXME: if self.query: edit query again
        if self.query and isinstance(self.query, InteractiveQuery):
            b=gtk.Button(_("Edit query again"))
            b.connect('clicked', self.edit_query)
            v.pack_start(b, expand=False)
            
        # Present choices to display the result
        if not self.result:
            v.add(gtk.Label(_("Empty result")))
        elif (isinstance(self.result, list) or isinstance(self.result, tuple)
            or isinstance(self.result, AbstractBundle)):
            # Check if there are annotations
            l=[ a for a in self.result if isinstance(a, Annotation) ]
            cr=len(self.result)
            cl=len(l)

            if cr == cl:
                t=_("Result is a list of %d annotations.") % cr
            else:
                t=_("Result is a list of  %(number)d elements with %(elements)s.") % { 
                    'elements': helper.format_element_name("annotation", len(l)),
                    'number': len(self.result)}
            v.add(gtk.Label(t))

            highlight_label=_("Highlight annotations")
            def toggle_highlight(b, annotation_list):
                if b.get_label() == highlight_label:
                    event="AnnotationActivate"
                    label= _("Unhighlight annotations")
                else:
                    event="AnnotationDeactivate"
                    label= highlight_label
                b.set_label(label)
                for a in annotation_list:
                    self.controller.notify(event, annotation=a)
                return True

            hb=gtk.VButtonBox()
            v.pack_start(hb)
            if l:
                b=gtk.Button(_("Display annotations in timeline"))
                b.connect('clicked', lambda b: self.open_in_timeline(l))
                hb.add(b)
                b=gtk.Button(highlight_label)
                b.connect('clicked', toggle_highlight, l)
                hb.add(b)
            b=gtk.Button(_("Edit elements"))
            b.connect('clicked', lambda b: self.open_in_edit_accumulator(self.result))
            hb.add(b)
            b=gtk.Button(_("Open in python evaluator"))
            b.connect('clicked', lambda b: self.open_in_evaluator(self.result))
            hb.add(b)
        else:
            v.add(gtk.Label(_("Result:\n%s") % unicode(self.result)))
        v.show_all()
        return v

    def edit_query(self, *p):
        #FIXME
        return True

    def open_in_timeline(self, l):
        self.controller.gui.open_adhoc_view('timeline', label=self.label, destination=self._destination, elements=l, minimum=0)
        return True

    def open_in_edit_accumulator(self, l):
        if self.controller.gui.edit_accumulator:
            a=self.controller.gui.edit_accumulator
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

