import sys

from cStringIO import StringIO

from simpletal import simpleTAL
from simpletal import simpleTALES
from simpletal.simpleTALES import *

from advene.model.exception import AdveneException

import global_methods

class AdveneTalesException(AdveneException): pass

class AdveneTalesPathException(AdveneTalesException): pass

class DebugLogger:

        verbosity = 3

	def debug (self, *args):
            if self.verbosity > 3:
	        print >>sys.stderr, "TAL: Debug:   ", args

	def info (self, *args):
            if self.verbosity > 3:
	        print >>sys.stderr, "TAL: Info :   ", args

	def warn (self, *args):
            if self.verbosity > 2:
	        print >>sys.stderr, "TAL: Warning: ", args

	def error (self, *args):
            if self.verbosity > 1:
	        print >>sys.stderr, "TAL: Error:   ", args

	def critical (self, *args):
            if self.verbosity > 0:
	        print >>sys.stderr, "TAL: Critical:", args

class _advene_context (simpleTALES.Context):
    """Advene specific implementation of TALES.
       It is based on simpletal.simpleTALES.Context,
       but whenever a path item is not resolved as an attribute nor a key of
       the object to which it is applied, it is searched in a set of Methods
       contained in the context."""

    def __init__ (self, options):
	simpleTALES.Context.__init__(self, options)

    def traversePathPreHook(self, obj, path):
	"""Called before any TALES standard evaluation"""

        val = None

	if self.methods.has_key(path):
	    val = self.methods[path](obj, self)
	    # If the result is None, the method is not appliable
	    # and we should try other access ways (attributes,...) on the
	    # object

        if val is None and hasattr (obj, 'getQName'):
            if self.locals.has_key('view'):
                ref = self.locals['view'].value ()
            elif self.globals.has_key('view'):
                ref = self.globals['view'].value ()
            elif self.locals.has_key('here'):
                ref = self.locals['here'].value ()
            elif self.globals.has_key('here'):
                ref = self.globals['here'].value ()
            else:
                ref = None
            if ref is not None:
                pkg = ref.getOwnerPackage ()
                ns_dict = pkg.getImports ().getInverseDict ()
                ns_dict[''] = pkg.getUri (absolute=True)
                val = obj.getQName (path, ns_dict, None)

	if val is not None and not isinstance (val, ContextVariable):
	    val = ContextVariable (val)
        return val

    def traversePathPostHook(self, obj, path):
	"""Called if default TALES traversePath can not resolve path on obj"""
	return None
    
    def evaluatePython (self, expr):
	globals = dict(zip (self.globals.keys(),
			    map(ContextVariable.value, self.globals.values())))
	locals = dict(zip (self.locals.keys(),
			   map(ContextVariable.value, self.locals.values())))
	return ContextVariable(eval(expr, globals, locals))


    def traversePathStep (self, val, path, resolved_stack, canCall=1):
                        # intermediate path elements should never be called
			self.log.debug ("Looking for path element %s" % path)
			temp = NoCallVariable (val).value()

			val = self.traversePathPreHook (temp, path)
			if val is not None:
				pass # traversePathPreHook did the work
			elif (hasattr (temp, path)):
				val = getattr (temp, path)
				if (not isinstance (val, ContextVariable)):
					val = ContextVariable (val)
			elif (hasattr (temp, 'has_key') and temp.has_key (path)):
				val = temp[path]
				if (not isinstance (val, ContextVariable)):
					val = ContextVariable (val)
			else:
				self.log.debug ("Not found.")
				val = self.traversePathPostHook(temp, path)

                        resolved_stack.insert(0, (path, val) )
			return val

    def evaluate (self, expr, originalAtts = None):
		# Returns a ContextVariable
		self.log.debug ("Evaluating %s" % expr)
		if (originalAtts is not None):
			# Call from outside
			self.globals['attrs'] = ContextVariable(originalAtts)
			# Check for an correct for trailing/leading quotes
			if (expr[0] == '"' or expr[0] == "'"):
				expr = expr [1:]
			if (expr[-1] == '"' or expr[-1] == "'"):
				expr = expr [0:-1]
			
		# Supports path, exists, nocall, not, and string
		expr = expr.strip()
		if (expr[0:5] == 'path:'):
			return self.evaluatePath (expr[5:].strip ())
		elif (expr[0:7] == 'exists:'):
			return self.evaluateExists (expr[7:].strip ())
		elif (expr[0:7] == 'nocall:'):
			return self.evaluateNoCall (expr[7:].strip ())
		elif (expr[0:4] == 'not:'):
			return self.evaluateNot (expr[4:].strip ())
		elif (expr[0:7] == 'string:'):
			return self.evaluateString (expr[7:].strip ())
		elif (expr[0:7] == 'python:'):
			return self.evaluatePython (expr[7:].strip ())
		else:
			# Not specified - so it's a path
			return self.evaluatePath (expr)
		
    def evaluatePath (self, expr):
                # FIXED: take exceptions into account when evaluating '|'
		self.log.debug ("Evaluating path expression %s" % expr)
		allPaths = expr.split ('|')
                allPaths.reverse()
                if len(allPaths)==1:
                    return self.traversePath (allPaths[0])
                else:
                    while len (allPaths)>0:
                        path = allPaths.pop()
                        try:
                            pathResult = self.evaluate(path.strip ())
                            if pathResult is None:
                                raise AdveneTalesPathException
                        except AdveneTalesPathException:
                            if len (allPaths) == 0:
                                raise
                        else:
                            return pathResult
                    return simpleTALES.nothingVariable

    def traversePath (self, expr, canCall=1):
		"""Overridden version of simpleTALES.Context.traversePath"""
	# TODO: patch simpletal with this version of traversePath, plus
	#       traversePathStep, so that it can be cleanly overridden, i.e.,
	#       without involving all the copy stuff :-(
		self.log.debug ("Traversing path %s" % expr)
		pathList = expr.split ('/')
		path = pathList[0]
		if self.locals.has_key(path):
			val = self.locals[path]
		elif self.globals.has_key(path):
			val = self.globals[path]  
		else:
			# If we can't find it then return None
			return None

                resolved_stack = [ (path, val) ]
                self.addLocals( (('__resolved_stack', resolved_stack),) )
		for path in pathList[1:]:
			val = self.traversePathStep(val, path, resolved_stack,
                                                    canCall)
			if val is None:
				raise AdveneTalesPathException(
                                  "'%s' in %s returned None in context %s" %
						     (path, pathList, self))
                self.popLocals()

		#self.log.debug ("Found value %s" % str (val))
		if (not canCall):
				val = NoCallVariable (val)
		return val


class AdveneContext(_advene_context):

    def defaultMethods():
        return [ n
            for n in dir(global_methods)
            if not n.startswith('_')
        ]

    defaultMethods = staticmethod(defaultMethods)

    def __str__ (self):
        return "<pre>AdveneContext\nGlobals:\n\t%s\nLocals:\n\t%s</pre>" % (
		"\n\t".join([ "%s: %s" % (k, str(v.value()).replace("<", "&lt;"))
			      for k, v in self.globals.iteritems() ]),
		"\n\t".join([ "%s: %s" % (k, str(v.value()).replace("<", "&lt;"))
			      for k, v in self.locals.iteritems() ]))

	
    def __init__(self, here, options={}):
        """Creates a tales.AdveneContext object, having a global symbol 'here'
           with value 'here' and a global symbol 'options' where all the key-
           value pairs of parameter 'options' are copied. Of course, it also
           has all the standard TALES global symbols.
        """
        _advene_context.__init__(self, dict(options)) # *copy* dict 'options'
        self.methods = {}
        self.addGlobal('here', here)
        for dm_name in self.defaultMethods():
            self.addMethod(dm_name, global_methods.__dict__[dm_name])
        # FIXME: debug
        self.log = DebugLogger()

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

        if isinstance (view_source, str) or isinstance (view_source, unicode):
            view_source = StringIO (unicode(view_source).encode('utf-8'))
            
        if mimetype is None or mimetype == 'text/html':
            compiler = simpleTAL.HTMLTemplateCompiler ()
        else:
            compiler = simpleTAL.XMLTemplateCompiler ()
        compiler.log = self.log
        compiler.parseTemplate (view_source, 'utf-8')
        compiler.getTemplate ().expand (context=self, outputFile=stream, outputEncoding='utf-8')

        return stream

    def evaluateValue(self, expr):
        """Returns the object matching the TALES expression expr applied on the
        given context. If context is an instance of tales.AdveneContext, it
        will be used directly. If it is another instance, a new AdveneContext
        will be created with this instance as global symbol 'here'.
        """
        r = self.evaluate (expr)
        if r is not None:
            return r.value()
        else:
            raise AdveneTalesException(
                     'TALES epression %s returned None in context %s' %
								   (expr, self))
