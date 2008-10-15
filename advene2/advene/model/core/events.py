"""
I provide the event/notification framework for Advene.

This framework is implemented on top of GTK (GObject) events. However, Advene
object do not inherit GObject, since they do not provide other functionalities
than events.
"""

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

class WithEventsMixin:
    """
    This mixin class assumes that the mixed-in class will provide a
    `_event_delegate` attribute valued with an instance of EventDelegate.
    """

    def connect(self, detailed_signal, handler, *args):
        """
        Connect the given handler to the (optionally detailed) signal.
        Additional arguments for the handler can be given.

        Return the handler_id, which can be used to disconnect the handler.
        """
        wrapper_args = list(args) + [handler,]
        return self._event_delegate.connect(detailed_signal, _handler_wrapper,
                                            *wrapper_args)

    def disconnect(self, handler_id):
        """Disconnect the handler associated to the given handler_id."""
        return self._event_delegate.disconnect(handler_id)

    def has_handler(self, handler_id):
        """
        Return True iff the given handler_id represents a connected handler.

        NB: this has been renamed from GObject.handler_is_connected to comply
        with Advene coding style (methode names should start with a verb).
        """
        return self._event_delegate.handler_is_connected(handler_id)

    def block_handler(self, handler_id):
        """
        Prevent the handler identified by handler_id to be invoked until it is
        unblocked.

        NB: this has been renamed from GObject.handler_is_connected to comply
        with Advene coding style (methode names should start with a verb).
        """
        return self._event_delegate.handler_block(handler_id)

    def unblock_handler(self, handler_id):
        """
        Unblock the blocked handler identified by handler_id so it can be
        invoked again.

        NB: this has been renamed from GObject.handler_is_connected to comply
        with Advene coding style (methode names should start with a verb).
        """
        return self._event_delegate.handler_unblock(handler_id)

    def emit(self, detailed_signal, *args):
        """
        Cause the object to emit the signal specified by detailed_signal.
        The additional parameters must match the number and type of the
        required signal handler parameters.
        """
        return self._event_delegate.emit(detailed_signal, *args)

    def stop_emission(self, detailed_signal):
        """
        Stop the current emission of the signal specified by detailed_signal.
        Any signal handlers in the list still to be run will not be
        invoked.
        """
        return self._stop_emi(detailed_signal)

# Common signals
# ==============
#
# NB: all signals involving a change have a "pre-" form, which is emitted
# *before* the actual change takes place. This can be useful for handlers
# requiring the state preceding the change (like EDL).
#
# signal:`changed`
# ----------------
#
# Emitted everytime an attribute is changed in the object
# 
# detail:: (depending on the object type) uri, url, foref, media, begin, end
# params::
#     * the attribute name
#     * the new value of the changed attribute
#
# This signal also has a "pre-" form.

gobject.signal_new("pre-changed", EventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,object,))

gobject.signal_new("changed", EventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,object,))

# signal:`changed-meta`
# -------------------
#
# Emitted everytime a meta-data is created/changed in the object
# 
# detail:: the URL key of the created/changed metadata
# params::
#     * the URL key of the metadata
#     * the new value of the changed meta-data (None if deleted)
#
# This signal also has a "pre-" form.

gobject.signal_new("pre-changed-meta", EventDelegate,
                   gobject.SIGNAL_RUN_FIRST|gobject.SIGNAL_DETAILED,
                   gobject.TYPE_NONE, (object,object,))

gobject.signal_new("changed-meta", EventDelegate,
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

# signal:`closed`
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

gobject.signal_new("closed", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object, object,))

# Element signals
# ===============
#
# signal:`changed-items`
# ----------------------
#
# Emitted for lists and relations when the structure of their items changes.
#
# params::
#     * a slice with only positive indices, relative to the old structure,
#       embeding all the changed indices
#     * a python list representing the new structure of the slice
#
# This signal also has a "pre-" form.

gobject.signal_new("pre-changed-items", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object, object,))

gobject.signal_new("changed-items", ElementEventDelegate,
                   gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE, (object, object,))

# signal:`changed-content-data`
# -----------------------------
#
# Emitted for elements with content when their content data is changed.
#
# params::
#     * TODO: find a way to represent a versatile (i.e. text or binary) diff.
#       Can be None if such a diff mechanism is not implemented.

gobject.signal_new("changed-content-data", ElementEventDelegate,
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
