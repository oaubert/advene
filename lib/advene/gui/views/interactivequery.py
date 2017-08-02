#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Interactive query.

Display the query results in a view (timeline, tree, etc).
"""
from gettext import gettext as _
import pprint

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

import advene.core.config as config
from advene.gui.edit.rules import EditQuery
from advene.model.bundle import AbstractBundle
from advene.rules.elements import SimpleQuery, Condition, Quicksearch
from advene.model.annotation import Annotation
from advene.model.tal.context import AdveneTalesException
from advene.gui.util import dialog, get_small_stock_button, get_pixmap_toolbutton

from advene.gui.views import AdhocView
import advene.gui.evaluator

from advene.gui.views.table import AnnotationTable, GenericTable

import advene.util.helper as helper

name="Interactive query plugin"

def register(controller):
    controller.register_viewclass(InteractiveQuery)
    controller.register_viewclass(InteractiveResult)

class InteractiveQuery(AdhocView):
    view_name = _("Interactive query")
    view_id = 'interactivequery'
    tooltip=_("Interactive query dialog")
    def __init__(self, controller=None, parameters=None, sources=None, here=None):
        super(InteractiveQuery, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            #(_("Refresh"), self.refresh),
            (_("Save query"), self.save_query),
            (_("Save default options"), self.save_default_options),
            )
        self.options = {
            'ignore-case': True,
            }
        self.controller=controller
        if here is None:
            here=controller.package
        self.here=here
        if sources is None:
            sources = [ "package/annotations" ]
        self.sources=sources

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        # Check for arg-defined sources
        sources = []
        for n, v in arg:
            if n == 'source':
                sources.append(v)
        if sources:
            self.sources = sources

        self.querycontainer, self.query = self.get_interactive_query()

        self.widget=self.build_widget()

    def get_interactive_query(self):
        l=helper.get_id(self.controller.package.queries, '_interactive')
        if l:
            q=SimpleQuery()
            q.from_xml(l.content.stream)
            q.container=l
            return l, q
        else:
            # Create the query
            el=self.controller.package.createQuery(ident='_interactive')
            el.author=config.data.userid
            el.date=self.controller.get_timestamp()
            el.title=_("Interactive query")

            # Create a basic query
            q=SimpleQuery(sources=self.sources,
                          rvalue="element")
            q.add_condition(Condition(lhs="element/content/data",
                                      operator="contains",
                                      rhs="string:a"))

            el.content.mimetype='application/x-advene-simplequery'
            el.content.data=q.xml_repr()

            self.controller.package.queries.append(el)

            self.controller.notify('QueryCreate', query=el)
            q.container=el
            return el, q

    def save_query(self, *p):
        """Saves the query in the package.
        """
        l=self.eq.invalid_items()
        if l:
            self.log(_("Invalid query.\nThe following fields have an invalid value:\n%s")
                     % ", ".join(l))
            return True
        # Update the query
        self.eq.update_value()

        if hasattr(self.eq, 'container'):
            default_id=self.eq.container.id
            default_title=self.eq.container.title
        else:
            default_id=helper.title2id(self._label)
            default_title=self._label


        t, i = dialog.get_title_id(title=_("Saving the query..."),
                                   text=_("Give a title and identifier for saving the query"),
                                   element_title=default_title,
                                   element_id=default_id)
        if i is None:
            return True

        q=helper.get_id(self.controller.package.queries, i)
        # Overwriting an existing query
        if q:
            create=False
            self.controller.notify('EditSessionStart', element=q, immediate=True)
        else:
            create=True
            # Create the query
            q=self.controller.package.createQuery(ident=i)
            q.author=config.data.userid
            q.date=self.controller.get_timestamp()
            self.controller.package.queries.append(q)

        q.title=t
        q.content.mimetype='application/x-advene-simplequery'

        # Store the query itself in the _interactive query
        q.content.data = self.eq.model.xml_repr()
        if create:
            self.controller.notify('QueryCreate', query=q)
        else:
            self.controller.notify('QueryEditEnd', query=q)
            self.controller.notify('EditSessionEnd', element=q)
        return q

    def validate(self, button=None):
        # Get the query
        l=self.eq.invalid_items()
        if l:
            self.log(_("Invalid query.\nThe following fields have an invalid value:\n%s")
                     % ", ".join(l))
            return True
        self.eq.update_value()
        query=self.eq.model
        # Store the query itself in the _interactive query
        self.querycontainer.content.data = query.xml_repr()

        label=_("Expert search")
        c=self.controller.build_context(here=self.here)
        try:
            res=c.evaluateValue("here/query/_interactive")
        except AdveneTalesException as e:
            # Display a dialog with the value
            dialog.message_dialog(_("TALES error in interactive expression:\n%s" % str(e)),
                icon=Gtk.MessageType.ERROR)
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
        vbox = Gtk.VBox()

        self.eq=EditQuery(self.query,
                          editable=True,
                          controller=self.controller)
        vbox.add(self.eq.widget)

        hb=Gtk.HButtonBox()

        b=Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', self.validate)
        hb.pack_start(b, False, True, 0)

        b=Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b.connect('clicked', self.cancel)
        hb.pack_start(b, False, True, 0)

        vbox.pack_start(hb, False, True, 0)

        def handle_key_press_event(widget, event):
            if event.keyval == Gdk.KEY_Return:
                self.validate()
                return True
            elif event.keyval == Gdk.KEY_Escape:
                self.cancel()
                return True
            return False

        vbox.connect('key-press-event', handle_key_press_event)

        return vbox

class InteractiveResult(AdhocView):
    """Interactive result display.

    Either we give a SimpleQuery (whose .result attribute will
    possibly be set), or we give a Quicksearch result.  In both cases,
    if the query was loaded from a saved Query, then .container will
    hold a reference to the advene.model.query.Query object, so that
    we can know its id, title, etc...
    """
    view_name = _("Interactive result")
    view_id = 'interactiveresult'
    tooltip=_("Interactive result display")

    def __init__(self, controller=None, parameters=None, query=None, result=None):
        super(InteractiveResult, self).__init__(controller=controller)
        self.close_on_package_load = True
        self.contextual_actions = (
            #(_("Refresh"), self.refresh),
            (_("Save query"), self.save_query),
            )
        self.controller=controller
        self.query=query
        if result is None and hasattr(query, 'result'):
            result=query.result
        self.result=result

        if isinstance(self.query, str):
            # Quicksearch entry. Convert to Quicksearch class.
            q=Quicksearch(controller=self.controller,
                          sources=config.data.preferences['quicksearch-sources'],
                          searched=self.query,
                          case_sensitive=not config.data.preferences['quicksearch-ignore-case'])
            self.query=q

        if hasattr(self.query, 'container'):
            if self.query.container.id == '_interactive':
                self._label=_("Result of interactive query")
            else:
                self._label=self.query.container.title
        elif isinstance(self.query, SimpleQuery):
            self._label=_("Result of a query")
        elif isinstance(self.query, Quicksearch):
            self._label=_("""'%s'""") % self.query.searched

        # Annotation-table view
        self.table=None
        self.widget=self.build_widget()

    def save_query(self, *p):
        """Saves the query in the package.
        """
        if hasattr(self.query, 'container'):
            default_id=self.query.container.id
            default_title=self.query.container.title
        else:
            default_id=helper.title2id(self._label)
            default_title=self._label

        t, i = dialog.get_title_id(title=_("Saving the query..."),
                                   text=_("Give a title and identifier for saving the query"),
                                   element_title=default_title,
                                   element_id=default_id)
        if i is None:
            return True

        q=helper.get_id(self.controller.package.queries, i)
        # Overwriting an existing query
        if q:
            create=False
        else:
            create=True
            # Create the query
            q=self.controller.package.createQuery(ident=i)
            q.author=config.data.userid
            q.date=self.controller.get_timestamp()
            self.controller.package.queries.append(q)

        q.title=t
        if isinstance(self.query, SimpleQuery):
            q.content.mimetype='application/x-advene-simplequery'
        elif isinstance(self.query, Quicksearch):
            q.content.mimetype='application/x-advene-quicksearch'
        q.content.data = self.query.xml_repr()
        if create:
            self.controller.notify('QueryCreate', query=q)
        else:
            self.controller.notify('QueryEditEnd', query=q)
        return q

    def create_comment(self, *p):
        if hasattr(self, 'table'):
            # There are annotations
            l=self.table.get_elements()
            v=self.controller.create_static_view(elements=l)
            if isinstance(self.query, Quicksearch):
                v.title=_("Comment on annotations containing %s") % self.query.searched
                self.controller.notify('ViewEditEnd', view=v)
            self.controller.gui.open_adhoc_view('edit', element=v, destination=self._destination)
        return True

    def create_montage(self, *p):
        if hasattr(self, 'table'):
            # There are annotations
            l=self.table.get_elements()
            self.controller.gui.open_adhoc_view('montage', elements=l, destination=self._destination)
        return True

    def create_annotations(self, *p):
        if self.table is not None:
            # There are annotations
            l=self.table.get_elements()
        else:
            l=None
        if l:
            at=self.controller.gui.ask_for_annotation_type(text=_("Choose the annotation type where annotations will be created."),
                                                           create=True)
            if at is None:
                return False
            at.setMetaData(config.data.namespace_prefix['dc'], 'description', _("Copied result of the '%s' query") % self.query)
            self.controller.notify('AnnotationTypeEditEnd', annotationtype=at)
            for a in l:
                self.controller.transmute_annotation(a, at)
        return True

    def search_replace(self, *p):
        default_search = None
        if isinstance(self.query, Quicksearch) and self.query.searched.split():
            default_search = self.query.searched.split()[0]
        l = self.table.get_elements()
        self.controller.gui.search_replace_dialog(l,
                                                  title=_("Search/replace content in %d elements") % len(l),
                                                  default_search=default_search)
        return True

    def redo_quicksearch(self, b, entry):
        s=entry.get_text()
        if not s:
            self.log(_("Empty quicksearch string"))
            return True
        self.query.searched=s
        res=self.controller.gui.search_string(s)
        label="'%s'" % s
        self.controller.gui.open_adhoc_view('interactiveresult', destination=self._destination,
                                            result=res, label=label, query=self.query)
        self.close()
        return True

    def build_widget(self):
        v=Gtk.VBox()

        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)
        v.pack_start(tb, False, True, 0)

        top_box=Gtk.HBox()
        v.pack_start(top_box, False, True, 0)

        if hasattr(self.query, 'container') and self.query.container.id == '_interactive':
            b=Gtk.Button(_("Edit query again"))
            b.connect('clicked', self.edit_query)
            top_box.pack_start(b, False, True, 0)
        elif isinstance(self.query, SimpleQuery):
            b=Gtk.Button(_("Edit query"))
            b.connect('clicked', lambda b: self.controller.gui.edit_element(self.query))
            top_box.pack_start(b, False, True, 0)
        elif isinstance(self.query, Quicksearch):
            e=Gtk.Entry()
            e.set_text(self.query.searched)
            e.set_width_chars(12)
            e.connect('activate', self.redo_quicksearch, e)
            b=get_small_stock_button(Gtk.STOCK_FIND, self.redo_quicksearch, e)
            e.set_tooltip_text(_('String to search'))
            b.set_tooltip_text(_('Search again'))
            top_box.pack_start(e, False, True, 0)
            top_box.pack_start(b, False, True, 0)

        # Present choices to display the result
        if not self.result:
            v.add(Gtk.Label(label=_("Empty result")))
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

            label=Gtk.Label(label=t)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_line_wrap(True)
            top_box.add(label)

            def toggle_highlight(b, annotation_list):
                if not hasattr(b, 'highlight') or b.highlight:
                    event="AnnotationActivate"
                    label= _("Unhighlight annotations")
                    b.highlight=False
                else:
                    event="AnnotationDeactivate"
                    label=_("Highlight annotations")
                    b.highlight=True
                b.set_tooltip_text(label)
                for a in annotation_list:
                    self.controller.notify(event, annotation=a)
                return True

            if l:
                # Instanciate a table view
                table=AnnotationTable(controller=self.controller, elements=l)

                if cr == cl:
                    # Only annotations.
                    v.add(table.widget)
                else:
                    # Mixed annotations + other elements
                    notebook=Gtk.Notebook()
                    notebook.set_tab_pos(Gtk.PositionType.TOP)
                    notebook.popup_disable()
                    v.add(notebook)

                    notebook.append_page(table.widget, Gtk.Label(label=_("Annotations")))

                    gtable=GenericTable(controller=self.controller, elements=[ e
                                                                               for e in self.result
                                                                               if not isinstance(e, Annotation) ]
                                                                               )
                    notebook.append_page(gtable.widget, Gtk.Label(label=_("Other elements")))


                for (icon, tip, action) in (
                    ('timeline.png' , _("Display annotations in timeline"), lambda b: self.open_in_timeline(l)),
                    ('transcription.png', _("Display annotations as transcription"), lambda b:
                         self.controller.gui.open_adhoc_view('transcription',
                                                             label=self._label,
                                                             destination=self._destination,
                                                             elements=l)),
                    ('highlight.png', _("Highlight annotations"), lambda b: toggle_highlight(b, l)),
                    (Gtk.STOCK_CONVERT, _("Export table"), lambda b: table.csv_export()),
                    (Gtk.STOCK_NEW, _("Create annotations from the result"), self.create_annotations),
                    ('montage.png', _("Define a montage with the result"), self.create_montage),
                    ('comment.png', _("Create a comment view with the result"), self.create_comment),
                    (Gtk.STOCK_FIND_AND_REPLACE, _("Search and replace strings in the annotations content"), self.search_replace),
                    ):
                    if icon.endswith('.png'):
                        ti=get_pixmap_toolbutton(icon)
                    else:
                        ti=Gtk.ToolButton(stock_id=icon)
                    ti.connect('clicked', action)
                    ti.set_tooltip_text(tip)
                    tb.insert(ti, -1)

                self.table=table
            else:
                # Only Instanciate a generic table view
                gtable=GenericTable(controller=self.controller, elements=self.result)
                v.add(gtable.widget)

                ti=Gtk.ToolButton(Gtk.STOCK_CONVERT)
                ti.connect('clicked', lambda b: gtable.csv_export())
                ti.set_tooltip_text(_("Export table"))
                tb.insert(ti, -1)
                self.table=gtable


            ti=get_pixmap_toolbutton('editaccumulator.png',
                                     lambda b: self.open_in_edit_accumulator(self.table.get_elements()))
            ti.set_tooltip_text(_("Edit elements"))
            tb.insert(ti, -1)

            if config.data.preferences['expert-mode']:
                ti=get_pixmap_toolbutton('python.png',
                                         lambda b: self.open_in_evaluator(self.table.get_elements()))
                ti.set_tooltip_text(_("Open in python evaluator"))
                tb.insert(ti, -1)
        else:
            v.add(Gtk.Label(label=_("Result:\n%s") % str(self.result)))
        v.show_all()
        return v

    def edit_query(self, *p):
        self.close()
        self.controller.gui.open_adhoc_view('interactivequery', destination='east')
        return True

    def open_in_timeline(self, l):
        self.controller.gui.open_adhoc_view('timeline', label=self._label, destination=self._destination, elements=l)
        return True

    def open_in_edit_accumulator(self, l):
        if not self.controller.gui.edit_accumulator:
            self.controller.gui.open_adhoc_view('editaccumulator')
        a=self.controller.gui.edit_accumulator
        for e in l:
            a.edit(e)
        return True

    def open_in_evaluator(self, l):
        p=self.controller.package
        try:
            a=p.annotations[-1]
        except IndexError:
            a=None

        ev=advene.gui.evaluator.Evaluator(globals_=globals(),
                                       locals_={'package': p,
                                                'result': l,
                                                'p': p,
                                                'a': a,
                                                'c': self.controller,
                                                'self': self,
                                                'pp': pprint.pformat },
                                       historyfile=config.data.advenefile('evaluator.log', 'settings')
                                       )
        w=ev.popup(embedded=True)

        self.controller.gui.init_window_size(w, 'evaluator')

        w.set_title(_("Results of _interactive query"))
        ev.set_expression('result')
        return True

