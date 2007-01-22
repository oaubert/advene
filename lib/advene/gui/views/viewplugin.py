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

from gettext import gettext as _

from advene.gui.views import AdhocView

class ViewPlugin(AdhocView):
    """
    Abstract class defining the interface of ViewPlugins.
    =====================================================

    The generic way of dealing with a ViewPlugin is to create an
    instance of it, then call the get_widget () method to get the
    corresponding Gtk widget.

    In the advenetool framework, the view should be registered via
    calls to register_view () so that it gets notified of the
    element's changes.

    Do not inherit from this class, as it defines many optional
    methods. Inherit from AdhocView, and define the relevant
    additional methods.

    self.load_parameters() takes a Content object as parameter, that
    must be of application/x-advene-adhoc-view mimetype. It will read
    the Content data, update the self.options dictionary, and put
    arguments in the self.arguments list (which is a list of (name,
    value) tuples).

    @ivar view_name: the name of the view
    @type view_name: string
    @ivar view_id: the id of the view
    @type view_id: string
    @ivar options: view options
    @type options: dict
    @ivar controller: the controller
    @type controller: AdveneController
    @ivar widget: the gtk widget representing the view
    @type widget: gkt.Widget
    """
    def __init__(self, controller=None, parameters=None):
        self.view_name = _("Generic view plugin")
        self.view_id = 'viewplugin'
        self.controller=controller
        self.options={}
        self.load_parameters(parameters)
        self.widget = self.build_widget()

    def register_callback (self, controller=None):
        """Method invoked on view creation.

        It can be used to register new EventHandler callbacks for
        instance (typically AnnotationBegin and AnnotationEnd).

        @param controller: the Advene controller
        @type controller: advene.core.controller.Controller
        """
        pass

    def unregister_callback (self, controller=None):
        """Method invoked on view closing.

        It is used to clean up the settings done in
        L{register_callback}.

        @param controller: the Advene controller
        @type controller: advene.core.controller.Controller
        """
        pass

    def get_widget (self):
        """Return a Gtk widget representing the view of the component.

        It should be idempotent (i.e. return the same reference upon
        multiple invocations).

        @return: the corresponding view
        @rtype: a Gtk Widget
        """
        return self.widget

    def popup(self):
        """Popup the view in a toplevel window.
        """
        pass

    def get_model (self):
        """Return the model (data structure) corresponding to the view.

        @return: the model
        @rtype: usually an Advene element (Annotation, Schema, ...)
        """
        pass

    #def update_position (self, pos):
    #    """If defined, this method will be invoked regularly with the current
    #       position.
    #       Note: beware when implementing update_position in views:
    #       it is a critical execution path, see gui.main.update_display
    #
    #    @param pos: the position
    #    @type pos: long
    #    """
    #    pass

    def activate_annotation (self, annotation):
        """Activate the given annotation (some kind of visual feedback).

        @param annotation: the activated annotation
        @type annotation: advene.model.annotation.Annotation
        """
        pass

    def desactivate_annotation (self, annotation):
        """Desactivate the given annotation (some kind of visual feedback).

        @param annotation: the activated annotation
        @type annotation: advene.model.annotation.Annotation
        """
        pass

    def update_model (self, package):
        """Update the model of the view.

        This should be called when a new package has been loaded.

        @param package: the new package
        @type package: advene.model.package.Package
        """
        pass

    def update_annotation (self, annotation=None, event=None):
        """Update the representation of the given annotation.

        This should be called when the annotation data or metadata has
        been modified.

        @param annotation: the activated annotation
        @type annotation: advene.model.annotation.Annotation
        @param event: the precise event (AnnotationCreate, AnnotationEditEnd, AnnotationDelete)
        @type event: advene.rules.elements.Event
        """
        pass

    def activate_relation (self, relation):
        """Activate the given relation (some kind of visual feedback).

        @param relation: the activated relation
        @type relation: advene.model.annotation.Relation
        """
        pass

    def desactivate_relation (self, relation):
        """Desactivate the given annotation (some kind of visual feedback).

        @param relation: the activated relation
        @type relation: advene.model.annotation.Relation
        """
        pass

    # Note: similar methods exist for annotationtype, relationtype, schema, view
    def update_relation (self, relation=None, event=None):
        """Update the representation of the given relation.

        This should be called when the relation data or metadata has
        been modified.

        @param relation: the activated relation
        @type relation: advene.model.relation.Relation
        @param event: the precise event (RelationCreate, RelationEditEnd, RelationDelete)
        @type event: advene.rules.elements.Event
        """
        pass

