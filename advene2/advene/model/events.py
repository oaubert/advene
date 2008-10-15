"""
I provide the event/notification framework for Advene.

This framework is implemented on top of GTK (GObject) events. However, Advene
object do not inherit GObject, since they do not provide other functionalities
than events.
"""

from advene.util.synchronized import enter_cs, exit_cs

import gobject

class EventDelegate(gobject.GObject):
    """
    Base class of event delegate.
    """
    def __init__(self, boss):
        gobject.GObject.__init__(self)
        self._boss = boss

class PackageEventDelegate(EventDelegate):
    """
    Class for event-delegate for packages.
    """
    pass

class ElementEventDelegate(EventDelegate):
    """
    Class for event-delegate for elements.
    """
    pass

def _handler_wrapper(gobj, *args):
    original_handler = args[-1]
    args = args[:-1]
    return original_handler(gobj._boss, *args)

class WithEventsMixin(object):
    """
    This mixin class assumes that the mixed-in class will provide a
    `_make_event_delegate` method returning an instance of the appropriate
    subclass of EventDelegate.
    """

    __event_delegate = None
    __disabling_count = 0

    def connect(self, detailed_signal, handler, *args):
        """
        Connect the given handler to the (optionally detailed) signal.
        Additional arguments for the handler can be given.

        Return the handler_id, which can be used to disconnect the handler.
        """
        if self.__event_delegate is None:
            self.__event_delegate = self._make_event_delegate()
        wrapper_args = list(args) + [handler,]
        return self.__event_delegate.connect(detailed_signal, _handler_wrapper,
                                             *wrapper_args)

    def disconnect(self, handler_id):
        """Disconnect the handler associated to the given handler_id."""
        assert self.has_handler(handler_id), "Handler-id %d is not connected" % handler_id
        return self.__event_delegate.disconnect(handler_id)

    def has_handler(self, handler_id):
        """
        Return True iff the given handler_id represents a connected handler.

        NB: this has been renamed from GObject.handler_is_connected to comply
        with Advene coding style (methode names should start with a verb).
        """
        return self.__event_delegate is not None \
           and self.__event_delegate.handler_is_connected(handler_id)

    def block_handler(self, handler_id):
        """
        Prevent the handler identified by handler_id to be invoked until it is
        unblocked.

        NB: this has been renamed from GObject.handler_block to comply
        with Advene coding style (methode names should start with a verb).
        """
        assert self.has_handler(handler_id), "Handler-id %d is not connected" % handler_id
        return self.__event_delegate.handler_block(handler_id)

    def unblock_handler(self, handler_id):
        """
        Unblock the blocked handler identified by handler_id so it can be
        invoked again.

        NB: this has been renamed from GObject.handler_unblock to comply
        with Advene coding style (methode names should start with a verb).
        """
        assert self.has_handler(handler_id), "Handler-id %d is not connected" % handler_id
        return self.__event_delegate.handler_unblock(handler_id)

    def emit(self, detailed_signal, *args):
        """
        Cause the object to emit the signal specified by detailed_signal.
        The additional parameters must match the number and type of the
        required signal handler parameters.
        """
        if self.__event_delegate is not None and self.__disabling_count == 0:
            return self.__event_delegate.emit(detailed_signal, *args)

    def emit_lazy(self, lazy_params):
        """
        Like emit, but lazy_params is assumed to be a function returning an
        iterable of the params to send to emit.
        The rationale is that, since emit does nothing if we have no
        EventDelegate, the parameters would not be evaluated.
        """
        if self.__event_delegate is not None:
            return self.__event_delegate.emit(*lazy_params())

    def stop_emission(self, detailed_signal):
        """
        Stop the current emission of the signal specified by detailed_signal.
        Any signal handlers in the list still to be run will not be
        invoked.
        """
        assert self.__event_delegate is not None
        return self.__event_delegate.stop_emission(detailed_signal)

    # synonyms for the sake of readability in GTK applications

    handler_is_connected = has_handler
    handler_block = block_handler
    handler_unblock = unblock_handler

    # advene specific methods

    def enter_no_event_section(self):
        """
        Disable all event emission for this object, until
        `exit_no_event_section` is called.

        Not also that a "no event section is a critical section for the object
        (in the sense of the `advene.util.synchronized` module).
        """
        enter_cs(self)
        self.__disabling_count += 1

    def exit_no_event_section(self):
        """
        Re-enables all event emission for this object.

        :see-also: `enter_no_event_section`
        """
        self.__disabling_count -= 1
        exit_cs(self)


# Common signals
# ==============
#
# NB: all signals involving a change have a "pre-" form, which is emitted
# *before* the actual change takes place. This can be useful for handlers
# requiring the state preceding the change (like EDL).
#
# signal:`modified`
# ----------------
#
# Emitted everytime an attribute is modified in the object
# 
# detail:: (depending on the object type) uri, url, frame_of_reference, media,
#          begin, end
# params::
#     * the attribute name
#     * the new value of the modified attribute
#
# This signal also has a "pre-" form.

gobject.signal_new("pre-modified", EventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,object,))

gobject.signal_new("modified", EventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,object,))

# signal:`modified-meta`
# -------------------
#
# Emitted everytime a meta-data is created/modified in the object
# 
# detail:: the URL key of the created/modified metadata
# params::
#     * the URL key of the metadata
#     * the new value of the modified meta-data (None if deleted)
#
# This signal also has a "pre-" form.

gobject.signal_new("pre-modified-meta", EventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,object,))

gobject.signal_new("modified-meta", EventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,object,))

# Package signals
# ===============
#
# signal:`created`
# ----------------
#
# Emitted everytime an element is created in the package
#
# detail:: media, annotation, relation, tag, list, query, view, resource,
#          import, content_url, content_mimetype, content_schema
# params::
#     * the object just created
# 

gobject.signal_new("created", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,))

# signal:`package-closed`
# ----------------
#
# Emitted when the package is closed.
# NB: the package is already closed, so it is an error to use it when receiving
# this signal. However, the URL and URI of the package are given as parameters.
#
# params::
#     * the package URL
#     * the package URI
#

gobject.signal_new("package-closed", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object, object,))

# signals:<element_type>
# ----------------------
#
# Instead of subscribint to each individual element, one can choose to
# subscribe globally to all elements of a given type in a package, using
# the signal named after that element type.
#
# The detail for this signal is the name of the corresponding element signal,
# without its detail. E.g. media::modified, list::pre-modified-items...
#
# signal:: media, annotation, relation, tag, list, query, view, resource,
#          import
#
# detail:: any element related signal
#
# params::
#     * the element to which the event is related
#     * a list of ojects corresponding to the parameters of the element       
#       signal

gobject.signal_new("media", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("annotation", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("relation", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("tag", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("list", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("query", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("view", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("resource", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))

gobject.signal_new("import", PackageEventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,str,object,))


# Element signals
# ===============
#
# signal:`modified-items`
# ----------------------
#
# Emitted for lists and relations when the structure of their items changes.
#
# params::
#     * a slice with only positive indices, relative to the old structure,
#       embeding all the modified indices
#     * a python list representing the new structure of the slice
#
# NB: because of the current implementation, some operations (set a slice,
# delete a slice, extend) are actually implemented using more atomic operations
# (__setitem__, __delitem__, append) and will hence emit no event by themselves
# but let the underlying operations send several "atomic" events.
#
# This signal also has a "pre-" form.

gobject.signal_new("pre-modified-items", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object, object,))

gobject.signal_new("modified-items", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object, object,))

# signal:`modified-content-data`
# -----------------------------
#
# Emitted for elements with content when their content data is modified.
#
# params::
#     * TODO: find a way to represent a versatile (i.e. text or binary) diff.
#       Can be None if such a diff mechanism is not implemented.

gobject.signal_new("modified-content-data", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object,))

# signal:`renamed`
# ----------------
#
# Emitted when the ID of this element changes.
#
# This signal also has a "pre-" form.

gobject.signal_new("pre-renamed", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object,))

gobject.signal_new("renamed", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object,))

# signal:`added-tag`
# ------------------
#
# Emitted when the element has a tag added to it.
#
# params::
#     * the tag that has been added

gobject.signal_new("added-tag", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object,)) 

# signal:`removed-tag`
# --------------------
#
# Emitted when the element has a tag removed from it.
#
# params::
#     * the tag that has been removed

gobject.signal_new("removed-tag", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object,))

# signal:`added`
# --------------
#
# Emitted by tags when added to an element.
#
# params::
#     * the element this tag has been added to.

gobject.signal_new("added", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object,)) 

# signal:`removed`
# ----------------
#
# Emitted by tags when removed from an element.
#
# params::
#     * the element this tag has been removed from.

gobject.signal_new("removed", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object,)) 

# TODO :
# * signal de suppression pour les elements
