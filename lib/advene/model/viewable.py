import cStringIO

import advene.model.modeled as modeled
import advene.model.tal.context

from advene.model.constants import *
from advene.model.exception import AdveneException

import advene.model.util as util

from util.auto_properties import auto_properties

class TypedUnicode(unicode):
    """Unicode string with a mimetype attribute.
    """
    def __init__(self, *p, **kw):
        super(TypedUnicode, self).__init__(*p, **kw)
        self.contenttype='text/plain'
        
class TypedString(str):
    """String with a mimetype attribute.
    """
    def __init__(self, *p, **kw):
        super(TypedString, self).__init__(*p, **kw)
        self.contenttype='text/plain'

class Viewable(object):
    """
    A viewable is an object on which advene Views can be applied. A viewable has
    a viewable-class (boldly corresponding to its python class), and can have a
    viewable-type (depending on its viewable-class).

    This class is the common superclass of all viewable objects. However, it
    must not be subclassed directy. Instead, a specific subclass must be
    created with the static method 'withClass', which takes the name of the
    viewable-class to be used, and optionnaly the name of the method to be used
    to get the viewable-type.

    Subclassing Viewable directly may have unpredictable results.
    """

    __metaclass__ = auto_properties

    def __init__(self):
        object.__init__(self)

    __subclasses = {}

    def withClass(viewable_class, viewable_type_getter_name=None):
        """
        Make or retrieve (if already created) a subclass of Viewable with
        the corresponding viewable_class
        """
        if viewable_class not in Viewable.__subclasses:
            class ViewableWithClass(Viewable):
                # getViewableClass is a static method,
                # so a class inheriting Viewable knows its viewable class
                def getViewableClass():
                    return viewable_class
                getViewableClass = staticmethod(getViewableClass)

                # we can not rely on metaclass 'auto_property' fot this one,
                # because properties need instance methods,
                # so we manage this particular property manually
                def _get_viewable_class(self):
                    return viewable_class
                viewableClass = property(_get_viewable_class)

                def getViewableTypeGetterName():
                    return viewable_type_getter_name
                getViewableTypeGetterName = \
                                         staticmethod(getViewableTypeGetterName)

                def getViewableType(self):
                    getter_name =self.getViewableTypeGetterName() 
                    if getter_name is not None:
                        return getattr(self, getter_name)()
                    return None

            Viewable.__subclasses[viewable_class] = ViewableWithClass
        return Viewable.__subclasses[viewable_class]

    withClass = staticmethod(withClass)

    def getAllClasses():
        """
        Return all the declared viewable classes
        """
        r = []
        for subcls in Viewable.__subclasses.values():
            r.append(subcls.getViewableClass())
        return tuple(r)

    getAllClasses = staticmethod(getAllClasses)

    def view(self, view_id=None, context=None):
        """
        Apply the specified view (or the best appliable view, cf
        findDefaultView) on the object, with optional parameters given
        in dico."""        

        if context is None:
            context = advene.model.tal.context.AdveneContext(self,{})

        view = None
        if view_id is None:
            view = self.findDefaultView ()
        else:
            view = self._find_named_view (view_id, context)
        if view is None:
            raise AdveneException('View %s not found' % view_id)
        if not view.match (self):
            raise AdveneException ("View %s cannot be applied to %s" %
                                   (view.getId(),
                                    self))
        view_source = view.getContent().getStream()
        mimetype = view.getContent().getMimetype()

        result = cStringIO.StringIO()
        #result.write((u"<!-- view %s applied to %s -->\n"
        #              % (unicode(view), unicode(self))).encode('utf-8'))
        #context.addLocals( (('here', self), ('view', view)) )
        context.pushLocals()
        context.setLocal('here', self)
        context.setLocal('view', view)
        context.interpret(view_source, mimetype, result)
        context.popLocals ()
        s=TypedUnicode(result.getvalue())
        s.contenttype=view.getContent().getMimetype()
        return s

    def findDefaultView(self):
        v = self.getDefaultView()
        if v: return v

        for pkg in self.__get_access_path():
            found = None
            for view in pkg.getViews():
                if view.match(self) \
                       and (found is None or view.isMoreSpecificThan(found)):
                    found = view
            if found:
                return found
        return None

    def _find_named_view (self, view_id, context):
        try:
            path =('view/ownerPackage/views/%s | '
                  +'here/ownerPackage/views/%s') % (view_id, view_id)
            return context.evaluateValue (path)
        except AdveneException:
            return None

    def getValidViews (self):
        """
        Returns the ids of views from the root package which are valid for
        this object.

        Note that such IDs may not work in every context in TALES.
        """
        return [ v.getId () for v in self.getRootPackage ().getViews ()
                            if v.match (self)]
        
    def getDefaultView(self):
        if isinstance(self, modeled.Modeled) \
               and self._getModel().hasAttributeNS(None,'default-view'):
            rel_uri = self._getModel().getAttributeNS(None, 'default-view')
            pkg_uri = self.getOwnerPackage ().getUri (absolute=True)
            abs_uri = util.uri.urljoin (pkg_uri, rel_uri)
            return self.getOwnerPackage().getViews()[abs_uri]
        else:
            return None

    def setDefaultView(self, value):
        if isinstance(self, modeled.Modeled):
            if value:
                views = self.getOwnerPackage().getViews()
                for id_ in views.ids():
                    if views[id_] is value:
                        self._getModel().setAttributeNS(None,'default-view', id_)
                        return
                raise AdveneException("%s not in owner package of %s" %
                                                                   (value,self))
            else:
                self._getModel().delAttributeNS(None, 'default-view')
        else:
            raise TypeError("%s has no XML representation" % self)

    def delDefaultView(self):
        self.setDefaultView(None)

    def __get_access_path(self):
        """This method is necessary since not all Viewable are Importable
        (e.g. Bundles, Contents and Fragments)
        """
        try:
            return self.getAccessPath()
        except AttributeError:
            try:
                return self._getParent().__get_access_path()
            except AttributeError:
                try:
                    return (self.getOwnerPackage(),)
                except AttributeError:
                    return ()

__system_default_view = cStringIO.StringIO("""<!-- ADVENE DEFAULT VIEW-->
<span tal:replace='here'>the object</span>""".encode('utf-8'))

def getSystemDefaultView():
    global __system_default_view
    __system_default_view.seek(0)
    return __system_default_view

def setSystemDefaultView(v):
    global __system_default_view
    __system_default_view = v
