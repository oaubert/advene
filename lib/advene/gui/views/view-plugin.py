class ViewPlugin:
    """Abstract class defining the interface of ViewPlugins.

    The generic way of dealing with a ViewPlugin is to create an
    instance of it, then call the get_widget () method to get the
    corresponding Gtk widget.

    In the advenetool framework, the view should be registered via
    calls to register_view ()."""

    def register_callback (self, controller=None):
        """Method invoked on view creation.

        It can be used to register new EventHandler callbacks for
        instance (typically AnnotationBegin and AnnotationEnd)."""
        pass
    
    def unregister_callback (self, controller=None):
        """Method invoked on view closing."""
        pass

    def get_widget (self):
        """Return a Gtk widget representing the view of the component.

        It should be idempotent (i.e. return the same reference upon
        multiple invocations)."""
        pass

    def get_model (self):
        """Return the model (data structure) corresponding to the view."""
        pass

    #def update_position (self, pos):
    #    """If defined, this method will be invoked regularly with the current
    #       position."""
    #    pass
    
    def activate_annotation (self, annotation):
        """Activate the given annotation (some kind of visual feedback)."""
        pass

    def desactivate_annotation (self, annotation):
        """Desactivate the given annotation (some kind of visual feedback)."""
        pass
    
    def update_annotation (self, annotation):
        """Update the representation of the given annotation.

        This should be called when the annotation data or metadata has been modified.
        """
        pass

    def activate_relation (self, relation):
        """Activate the given annotation (some kind of visual feedback)."""
        pass

    def desactivate_relation (self, relation):
        """Desactivate the given annotation (some kind of visual feedback)."""
        pass

    def update_relation (self, relation):
        """Update the representation of the given relation.

        This should be called when the relation data or metadata has been modified.
        """
        pass
