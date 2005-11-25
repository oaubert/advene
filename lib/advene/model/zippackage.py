"""OpenDocument style package format.
==================================

This format is a transition from the plain xml Advene package format
to a richer format inspired by OpenDocument (zip file with data + metadata).

It is intented as a temporary measure before the complete rewrite of
the Advene package format.

File extension: .azp (Advene Zip Package) which will be followed by
.aod (Advene OpenDocument)

General layout:

foo.azp/
        mimetype
        content.xml
        resources/
	meta.xml (optional)
	META-INF/manifest.xml

Contents:

mimetype: application/x-advene-zip-package
content.xml: the previous package.xml format
resources/: associated resources, 
            available through the TALES expression /package/resources/...
meta.xml: metadata (cf OpenDocument specification)
META-INF/manifest.xml : Manifest (package contents)
"""

import zipfile
import os
import shutil
import urllib
from advene.model.exception import AdveneException
from advene.model.resources import Resources, ResourceData
import util.uri
import mimetypes
import warnings

import xml.dom.ext.reader.PyExpat
import xml.sax

from gettext import gettext as _
    
class ZipPackage:
    # Some constants
    MIMETYPE='application/x-advene-zip-package'
    MANIFEST_NAMESPACE='urn:oasis:names:tc:opendocument:xmlns:manifest:1.0'

    # Global method for cleaning up
    tempdir_list = []
    
    def cleanup():
	"""Remove the temp. directories used during the session.

	No check is done to see wether it is in use or not. This 
	method is intended to be used at the end of the application,
	to clean up the mess.
	"""
	for d in ZipPackage.tempdir_list:
	    # FIXME: there should be a way to determine wether it
	    # is still used or not.
	    print "Cleaning up %s" % d
	    if os.path.isdir(d):
		shutil.rmtree(d, ignore_errors=True)

    cleanup = staticmethod(cleanup)

    def __init__(self, uri=None):
	self.uri = None
	self._tempdir = None
	self.file_ = None

	if uri is not None:
	    if uri.startswith('file://'):
		uri=uri[5:]
	    if os.path.exists(uri):
		# It is a real filename
		self.uri = 'file://' + os.path.abspath(uri)
		self.file_ = uri
	    else:
		u=urllib.urlopen(uri)

		# Use the same extension
		(n, e) = os.path.splitext(uri)
		self.file_ = os.tempnam(None, 'adv') + e		
		print "Making a local copy of %s" % uri
		self.uri = uri
		f=open(self.file_, 'w')
		f.write(u.read())
		f.close()
		u.close()

	if self.file_ is not None:
	    self.open(self.file_)

    def getContentsFile(self):
	return os.path.join( self._tempdir, 'content.xml' )

    def new(self):
	"""Prepare a new AZP expanded package.
	"""
	self._tempdir=os.tempnam(None, 'adv')
	os.mkdir(self._tempdir)
	self.tempdir_list.append(self._tempdir)

	open(os.path.join(self._tempdir, 'mimetype'), 'w').write(self.MIMETYPE)

	os.mkdir(os.path.join(self._tempdir, 'resources'))

    def open(self, fname=None):
	if fname is None:
	    fname=self.file_

	z=zipfile.ZipFile(fname, 'r')

	# Check the validity of mimetype
	try:
	    typ = z.read('mimetype')
	except KeyError:
	    raise AdveneException(_("File %s is not an Advene zip package.") % self.file_)
	if typ != self.MIMETYPE:
	    raise AdveneException(_("File %s is not an Advene zip package.") % self.file_)

	# The file is an advene zip package. We can extract its contents
	# to a temporary directory
	self._tempdir=os.tempnam(None, 'adv')
	os.mkdir(self._tempdir)
	os.mkdir(os.path.join( self._tempdir, 'resources'))
	self.tempdir_list.append(self._tempdir)
	
	# FIXME: check the portability (convert / to os.path.sep ?)
	for name in z.namelist():
	    if name.endswith('/'):
		os.mkdir(os.path.join(self._tempdir, name))
	    else:
		fname=os.path.join(self._tempdir, name)
		if not os.path.isdir(os.path.dirname(fname)):
		    os.mkdir(os.path.dirname(fname))
		outfile = open(fname, 'wb')
		outfile.write(z.read(name))
		outfile.close()

	z.close()

	# Create the resources directory if necessary
	resource_dir = os.path.join( self._tempdir, 'resources' )
	if not os.path.exists(resource_dir):
	    os.mkdir(resource_dir)

	# FIXME: Check against the MANIFEST file
	for (name, mimetype) in self.manifest_to_list(os.path.join( self._tempdir, 'META-INF/manifest.xml') ):
	    if name == u'/':
		pass
	    n=name.replace('/', os.path.sep)
	    if not os.path.exists( os.path.join( self._tempdir, n ) ):
		print "Warning: missing file : %s" % name

	# FIXME: Make some validity checks (resources/ dir, etc)
	self.file_ = fname

    def save(self, fname=None):
	if fname is None:
	    fname=self.file_

	z=zipfile.ZipFile(fname, 'w')
	manifest=[]

	for (dirpath, dirnames, filenames) in os.walk(self._tempdir):
	    # Remove tempdir prefix
	    zpath=dirpath.replace(self._tempdir, '')

	    # Normalize os.path.sep to UNIX pathsep (/)
	    zpath=zpath.replace(os.path.sep, '/', -1)
	    if zpath and zpath[0] == '/':
		# We should have only a relative subdir here
		zpath=zpath[1:]

	    for f in filenames:
		if zpath:
		    name='/'.join( (zpath, f) )
		else:
		    name=f
		manifest.append(name)
		z.writestr( name,
			    open(os.path.join(dirpath, f)).read() )

	# Generation of the manifest file
	z.writestr( "META-INF/manifest.xml", 
		    self.list_to_manifest(manifest) )

	z.close()

    def list_to_manifest(self, manifest):
	"""Generate the XML representation of the manifest.

	"""
	# FIXME: This is done in a hackish way. It should be rewritten
	# using a proper XML binding
	out=u"""<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
"""
	out += u"""<manifest:file-entry manifest:media-type="%s" manifest:full-path="/"/>\n""" % self.MIMETYPE

	for f in manifest:
	    if f == 'mimetype' or f == 'META-INF/manifest.xml':
		continue
	    (mimetype, encoding) = mimetypes.guess_type(f)
	    if mimetype is None:
		mimetype = "text/plain"
	    out += u"""<manifest:file-entry manifest:media-type="%s" manifest:full-path="%s"/>\n""" % (unicode(mimetype), unicode(f))
	out += """</manifest:manifest>"""
	return out

    def manifest_to_list(self, name):
	"""Convert the manifest.xml to a list.

	List of tuples : (name, mimetype)
	"""
	h=ManifestHandler()
	return h.parse_file(name)
	
    def close(self):
	"""Close the package and remove temporary files.
	"""
	shutil.rmtree(self._tempdir, ignore_errors=True)
	self.tempdir_list.remove(self._tempdir)
	return True

    def getResources(self, package=None):
	return Resources( self, '', parent=package )

class ManifestHandler(xml.sax.handler.ContentHandler):
    """Parse a manifest.xml file.
    """
    def __init__(self):
	self.filelist = []
 
    def startElement(self, name, attributes):
	if name == "manifest:file-entry":
	    p=attributes['manifest:full-path']
	    t=attributes['manifest:media-type']
	    self.filelist.append( (p, t) )
    
    def parse_file(self, name):
	p=xml.sax.make_parser()
	p.setFeature(xml.sax.handler.feature_namespaces, False)
	p.setContentHandler(self)
	p.parse(name)
	return self.filelist

warnings.filterwarnings('ignore', 'tempnam', RuntimeWarning)
