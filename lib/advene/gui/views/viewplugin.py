class ViewPlugin:
    """
    Abstract class defining the interface of ViewPlugins.
    =====================================================

    The generic way of dealing with a ViewPlugin is to create an
    instance of it, then call the get_widget () method to get the
    corresponding Gtk widget.

    In the advenetool framework, the view should be registered via
    calls to register_view () so that it gets notified of the
    element's changes.
    """

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
        pass

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
    
