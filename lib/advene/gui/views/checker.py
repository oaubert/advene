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
"""Checker view.
"""
import logging
logger = logging.getLogger(__name__)

from gi.repository import Gtk

from gettext import gettext as _

import advene.core.config as config
import advene.gui.util.dialog as dialog
from advene.gui.views import AdhocView
from advene.gui.views.table import AnnotationTable, GenericTable
import advene.gui.views.table
import advene.util.helper as helper


CHECKERS = {}
def register_checker(checker):
    """Register a checker
    """
    CHECKERS[checker.__name__] = checker

def get_checker(name):
    """Return the checker corresponding to name.
    """
    return CHECKERS.get(name)

class FeatureChecker:
    """API for feature checking.
    """
    name = "Abstract FeatureChecker"
    def __init__(self, controller=None):
        self.controller = controller
        self.widget = self.build_widget()

    def build_widget(self):
        return Gtk.Label("Abstract checker")

    def update_model(self, package=None):
        return True

@register_checker
class OverlappingChecker(FeatureChecker):
    name = "Overlapping"
    description = _("This table presents for each type annotations that are overlapping.")
    def build_widget(self):
        self.table = AnnotationTable(controller=self.controller)
        # Set colors
        self.table.columns['begin'].add_attribute(self.table.columns['begin'].get_cells()[0],
                                                  'cell-background',
                                                  advene.gui.views.table.COLUMN_CUSTOM_FIRST)
        self.table.columns['end'].add_attribute(self.table.columns['end'].get_cells()[0],
                                                'cell-background',
                                                advene.gui.views.table.COLUMN_CUSTOM_FIRST + 1)
        return self.table.widget

    def overlapping_annotations(self):
        """Return a list of overlapping annotations for each annotation type.

        It returns 2 sets of elements: the ones which have a potentialy
        bogus begin time, and the ones with a potentialy bogus end
        time.
        """
        begins = set()
        ends = set()
        for at in self.controller.package.annotationTypes:
            for a, b in zip(at.annotations, at.annotations[1:]):
                if a.fragment.end > b.fragment.begin:
                    ends.add(a)
                    begins.add(b)
        return begins, ends

    def update_model(self, package=None):
        begins, ends = self.overlapping_annotations()
        overlap = list(begins.union(ends))

        def custom_data(b):
            if b is None:
                return (str, str)
            begin, end = None, None
            if b in begins:
                begin = "#ff6666"
            if b in ends:
                end = "#ff6666"
            return (begin, end)
        self.table.set_elements(overlap, custom_data)
        self.table.model.set_sort_column_id(advene.gui.views.table.COLUMN_TYPE, Gtk.SortType.ASCENDING)

@register_checker
class CompletionChecker(FeatureChecker):
    name = "Completions"
    description = _("For every annotation type that has predefined keywords, this table displays the annotations that contain unspecified keywords.")
    def build_widget(self):
        self.table = AnnotationTable(controller=self.controller, custom_data=lambda a: (str, ))
        column = self.table.columns['custom0']
        column.props.title = _("Undef. keywords")
        return self.table.widget

    def update_model(self, package=None):
        # Dictionary indexed by annotation, where values are the
        # keyword diff
        diff_dict = {}
        def custom_data(a):
            if a is None:
                return (str, )
            else:
                return (diff_dict.get(a, ""), )

        for at in self.controller.package.annotationTypes:
            completions = set(helper.get_type_predefined_completions(at))
            if completions:
                # There are completions. Check for every annotation if
                # they use a keyword not predefined.
                for a in at.annotations:
                    kws = set(a.content.parsed())
                    diff = kws - completions
                    if diff:
                        # There are used keywords that are not completions
                        diff_dict[a] = ",".join(diff)
        self.table.set_elements(list(diff_dict.keys()), custom_data)
        self.table.model.set_sort_column_id(advene.gui.views.table.COLUMN_TYPE, Gtk.SortType.ASCENDING)

@register_checker
class OntologyURIChecker(FeatureChecker):
    name = "Ontology URI"
    description = _("This table presents elements (package, schemas, annotation types) that do not have the ontology_uri reference metadata.")
    def build_widget(self):
        self.table = GenericTable(controller=self.controller)
        return self.table.widget

    def update_model(self, package=None):
        def check_element(el):
            return el.getMetaData(config.data.namespace, "ontology_uri")

        invalid = []
        if not check_element(self.controller.package):
            invalid.append(self.controller.package)
        invalid.extend(el for el in self.controller.package.schemas if not check_element(el))
        invalid.extend(el for el in self.controller.package.annotationTypes if not check_element(el))
        self.table.set_elements(invalid)

@register_checker
class DurationChecker(FeatureChecker):
    name = "Duration"
    description = _("This table presents the annotations that have a null duration.")
    def build_widget(self):
        self.table = AnnotationTable(controller=self.controller)
        return self.table.widget

    def update_model(self, package=None):
        self.table.set_elements([ a for a in self.controller.package.annotations
                                  if not a.fragment.duration ])

@register_checker
class TypeChecker(FeatureChecker):
    name = "Type"
    description = _("This table presents annotation whose content types does not match their type's content-type")
    def build_widget(self):
        self.table = AnnotationTable(controller=self.controller, custom_data=lambda a: (str, str))
        self.table.columns['custom0'].props.title = 'content mimetype'
        self.table.columns['custom1'].props.title = 'type mimetype'
        return self.table.widget

    def update_model(self, package=None):
        def custom_data(a):
            if a is None:
                return (str, str)
            else:
                return (a.content.mimetype, a.type.mimetype)
        self.table.set_elements([ a for a in self.controller.package.annotations
                                  if a.content.mimetype != a.type.mimetype ], custom_data)

@register_checker
class EmptyContentChecker(FeatureChecker):
    name = "EmptyContent"
    description = _("This table presents the annotations that have an empty content.")
    def build_widget(self):
        self.table = AnnotationTable(controller=self.controller)
        return self.table.widget

    def update_model(self, package=None):
        self.table.set_elements([ a for a in self.controller.package.annotations
                                  if not a.content.data ])

class CheckerView(AdhocView):
    view_name = _("Checker")
    view_id = 'checker'
    tooltip = _("Check various package properties")

    def __init__ (self, controller=None, parameters=None):
        super(CheckerView, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = ()
        self.controller=controller
        self.options = {
            # Comma-separated list of active checker classnames
            'active_checkers': ""
            }
        self.contextual_actions = (
            (_("Select active checkers"), self.select_active_checkers),
            )
        self.checkers = []

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        self.widget = self.build_widget()
        self.update_annotation = self.update_model
        self.update_relation = self.update_model
        self.update_annotationtype = self.update_model
        self.update_relationtype = self.update_model
        self.update_model()

    def select_active_checkers(self):
        active = self.options.get('active_checkers')
        if active:
            active = [ name.strip() for name in active.split(',') ]
        else:
            active = list(CHECKERS.keys())

        d = Gtk.Dialog(title=_("Active checkers"),
                       parent=self.widget.get_toplevel(),
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ))

        d.vbox.pack_start(Gtk.Label(_("Please specify the active checkers.")), False, False, 0)
        for name in CHECKERS:
            b = Gtk.CheckButton(name, use_underline=False)
            b._element = name
            b.set_active(name in active)
            d.vbox.pack_start(b, False, True, 0)
        d.vbox.show_all()
        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        d.show()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == Gtk.ResponseType.OK:
            elements=[ but._element
                       for but in d.vbox.get_children()
                       if hasattr(but, 'get_active') and but.get_active() ]
            self.options['active_checkers'] = ",".join(elements)
            self.build_checkers()
            self.update_model()
        d.close()
        return True

    def update_model(self, *p, **kw):
        for checker in self.checkers:
            checker.update_model()

    def active_checkers(self):
        active = self.options.get('active_checkers')
        if active:
            return [ c
                     for c in [ get_checker(name.strip()) for name in active.split(',') ]
                     if c is not None ]
        else:
            return CHECKERS.values()

    def build_checkers(self):
        # Clear notebook if there are already checkers
        for i in range(self.notebook.get_n_pages(), 0, -1):
            self.notebook.remove_page(i - 1)
        self.checkers = []

        for checkerclass in self.active_checkers():
            checker = checkerclass(self.controller)
            self.checkers.append(checker)
            vbox = Gtk.VBox()
            description = Gtk.Label.new(checker.description)
            description.set_line_wrap(True)
            vbox.pack_start(description, False, False, 0)
            vbox.add(checker.widget)
            self.notebook.append_page(vbox, Gtk.Label(label=checker.name))
        self.notebook.show_all()

    def build_widget(self):
        mainbox = Gtk.VBox()

        mainbox.pack_start(Gtk.Label(_("List of possible issues in the current package")), False, False, 0)

        self.notebook=Gtk.Notebook()
        self.notebook.set_tab_pos(Gtk.PositionType.TOP)
        self.notebook.popup_disable()
        mainbox.add(self.notebook)

        self.build_checkers()
        return mainbox

    def update_annotation (self, annotation=None, event=None):
        self.update_model()
        return True
