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
import logging
logger = logging.getLogger(__name__)

import copy
import sys

from io import StringIO

from simpletal import simpleTAL
from simpletal import simpleTALES

from advene.model.exception import AdveneException

from . import global_methods

class AdveneTalesException(AdveneException): pass

class AdveneTalesPathException(AdveneTalesException): pass

class DebugLogger:
        verbosity = 3

        def debug (self, *args):
            logger.debug(args)

        def info (self, *args):
            logger.info(args)

        def warn (self, *args):
            logger.warn(args)

        def error (self, *args):
            logger.error(args)

        def critical (self, *args):
            logger.error(args)

debuglogger_singleton = DebugLogger()

class NoCallVariable(simpleTALES.ContextVariable):
        """Not callable variable.

        Used for view wrappers, that should not be called if intermediate values.
        Such a value (if used in a _advene_context) can hold a callable, that will
        be called only if final element in the path.
        """
        def value (self, currentPath=None):
                return self.ourValue

class _advene_context (simpleTALES.Context):
    """Advene specific implementation of TALES.
       It is based on simpletal.simpleTALES.Context,
       but whenever a path item is not resolved as an attribute nor a key of
       the object to which it is applied, it is searched in a set of Methods
       contained in the context."""

    def __init__ (self, options):
        simpleTALES.Context.__init__(self, options, allowPythonPath=True)

    def wrap_method(self, method):
        return simpleTALES.PathFunctionVariable(method)

    def wrap_nocall(self, o):
        return NoCallVariable(o)

    def wrap_object(self, o):
        """Wraps an object into a ContextVariable."""
        return simpleTALES.ContextVariable(o)

    def addLocals (self, localVarList):
        # For compatibility with code using simpletal 3.6 (migration phase)
        # Pop the current locals onto the stack
        self.pushLocals()
        for name, value in localVarList:
                self.setLocal(name, value)

    def traversePathPreHook(self, obj, path):
        """Called before any TALES standard evaluation"""

        #print "Prehook for %s on %s" % (obj, path)

        val = None

        if path in self.methods:
            #print "Evaluating %s on %s" % (path, obj)
            val = self.methods[path](obj, self)
            # If the result is None, the method is not appliable
            # and we should try other access ways (attributes,...) on the
            # object

        if val is None and hasattr (obj, 'getQName'):
            if 'view' in self.locals:
                ref = self.locals['view']
            elif 'view' in self.globals:
                ref = self.globals['view']
            elif 'here' in self.locals:
                ref = self.locals['here']
            elif 'here' in self.globals:
                ref = self.globals['here']
            else:
                ref = None
            if ref is None:
                ref = obj
            pkg = ref.getOwnerPackage ()
            ns_dict = pkg.getImports ().getInverseDict ()
            ns_dict[''] = pkg.getUri (absolute=True)
            val = obj.getQName (path, ns_dict, None)

        return val

    def traversePath (self, expr, canCall=1):
                # canCall only applies to the *final* path destination, not points down the path.
                # Check for and correct for trailing/leading quotes
                if (expr.startswith ('"') or expr.startswith ("'")):
                        if (expr.endswith ('"') or expr.endswith ("'")):
                                expr = expr [1:-1]
                        else:
                                expr = expr [1:]
                elif (expr.endswith ('"') or expr.endswith ("'")):
                        expr = expr [0:-1]
                pathList = expr.split ('/')

                path = pathList[0]
                if path.startswith ('?'):
                        path = path[1:]
                        if path in self.locals:
                                path = self.locals[path]
                                if (isinstance (path, simpleTALES.ContextVariable)): path = path.value()
                                elif (callable (path)):path = path(*())

                        elif path in self.globals:
                                path = self.globals[path]
                                if (isinstance (path, simpleTALES.ContextVariable)): path = path.value()
                                elif (callable (path)):path = path(*())
                                #self.log.debug ("Dereferenced to %s" % path)
                if path in self.locals:
                        val = self.locals[path]
                elif path in self.globals:
                        val = self.globals[path]
                else:
                        # If we can't find it then raise an exception
                        raise simpleTALES.PathNotFoundException() from None

                # Advene hook: store the resolved_stack
                resolved_stack = [ (path, val) ]
                self.pushLocals()
                self.setLocal( '__resolved_stack', resolved_stack )

                index = 1
                for path in pathList[1:]:
                        #self.log.debug ("Looking for path element %s" % path)
                        if path.startswith ('?'):
                                path = path[1:]
                                if path in self.locals:
                                        path = self.locals[path]
                                        if (isinstance (path, simpleTALES.ContextVariable)): path = path.value()
                                        elif (callable (path)):path = path(*())
                                elif path in self.globals:
                                        path = self.globals[path]
                                        if (isinstance (path, simpleTALES.ContextVariable)): path = path.value()
                                        elif (callable (path)):path = path(*())
                                #self.log.debug ("Dereferenced to %s" % path)
                        try:
                                if (isinstance (val, simpleTALES.ContextVariable)): temp = val.value((index, pathList))
                                elif (callable (val)):temp = val(*())
                                else: temp = val
                        except simpleTALES.ContextVariable as e:
                                # Fast path for those functions that return values
                                self.popLocals()
                                return e.value()

                        # Advene hook:
                        val = self.traversePathPreHook (temp, path)
                        if val is not None:
                                pass
                        elif (hasattr (temp, path)):
                                val = getattr (temp, path)
                        else:
                                try:
                                        val = temp[path]
                                except (TypeError, KeyError):
                                        try:
                                                val = temp[int(path)]
                                        except:
                                                #self.log.debug ("Not found.")
                                                raise simpleTALES.PathNotFoundException() from None
                        # Advene hook: stack resolution
                        resolved_stack.insert(0, (path, val) )

                        index = index + 1
                #self.log.debug ("Found value %s" % str (val))

                self.popLocals()
                if (canCall):
                        try:
                                if (isinstance (val, simpleTALES.ContextVariable)):
                                        result = val.value((index,pathList))
                                        # Advene hook: introduced by the NoCallVariable
                                        if callable(result):
                                                result = val.value((index, pathList))(*())
                                elif (callable (val)):result = val(*())
                                else: result = val
                        except simpleTALES.ContextVariable as e:
                                # Fast path for those functions that return values
                                return e.value()
                else:
                        if (isinstance (val, simpleTALES.ContextVariable)): result = val.realValue
                        else: result = val
                return result


class AdveneContext(_advene_context):

    def defaultMethods():
        return [ n
            for n in dir(global_methods)
            if not n.startswith('_')
        ]

    defaultMethods = staticmethod(defaultMethods)

    def checkpoint(self):
        """Checkpoint locals/globals variables to preserve state
        """
        self._cached_locals = copy.copy(self.locals)
        self._cached_globals = copy.copy(self.globals)

    def restore(self):
        """Restore locals/globals from a previous checkpoint state.
        """
        self.locals = copy.copy(self._cached_locals)
        self.globals = copy.copy(self._cached_globals)

    def __str__ (self):
        return "<pre>AdveneContext\nGlobals:\n\t%s\nLocals:\n\t%s</pre>" % (
                "\n\t".join([ "%s: %s" % (k, str(v).replace("<", "&lt;"))
                              for k, v in self.globals.items() ]),
                "\n\t".join([ "%s: %s" % (k, str(v).replace("<", "&lt;"))
                              for k, v in self.locals.items() ]))


    def __init__(self, here, options=None):
        """Creates a tales.AdveneContext object, having a global symbol 'here'
           with value 'here' and a global symbol 'options' where all the key-
           value pairs of parameter 'options' are copied. Of course, it also
           has all the standard TALES global symbols.
        """
        if options is None:
                options={}
        _advene_context.__init__(self, dict(options)) # *copy* dict 'options'
        self.methods = {}
        self.addGlobal('here', here)
        for dm_name in self.defaultMethods():
            self.addMethod(dm_name, global_methods.__dict__[dm_name])
        # FIXME: debug
        self.log = debuglogger_singleton

    def addMethod (self, name, function):
        """Add a new method to this context."""
        # TODO: test that function is indeed a function, and that it has the
        #       correct signature
        if (True):
            self.methods[name] = function
        else:
            raise AdveneTalesException("%s is not a valid method" % function)

    def interpret (self, view_source, mimetype, stream=None):
        """
        Interpret the TAL template available through the stream view_source,
        with the mime-type mimetype, and print the result to the stream
        "stream". The stream is returned. If stream is not given or None, a
        StringIO will be created and returned.
        """
        if stream is None:
            stream = StringIO ()

        if isinstance (view_source, str) or isinstance (view_source, str):
            view_source = StringIO (str(view_source))

        kw = {}
        if mimetype is None or mimetype.startswith('text/'):
            compiler = simpleTAL.HTMLTemplateCompiler ()
            compiler.log = self.log
            compiler.parseTemplate (view_source, 'utf-8')
        else:
            compiler = simpleTAL.XMLTemplateCompiler ()
            compiler.log = self.log
            compiler.parseTemplate (view_source)
            kw["suppressXMLDeclaration"] = 1
        compiler.getTemplate ().expand (context=self, outputFile=stream, outputEncoding='utf-8', **kw)

        return stream

    def evaluateValue(self, expr):
        """Returns the object matching the TALES expression expr applied on the
        given context. If context is an instance of tales.AdveneContext, it
        will be used directly. If it is another instance, a new AdveneContext
        will be created with this instance as global symbol 'here'.
        """
        r = None
        try:
                r = self.evaluate (expr)
        except simpleTALES.PathNotFoundException:
                raise AdveneTalesException(
                        'TALES expression %s returned None in context %s' %
                        (expr, self)) from None
        except:
                logger.error("Unhandled exception - please report", exc_info=True)
        return r
