#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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

from gettext import gettext as _

import os
import time
import re

import advene.core.config as config
import advene.util.helper as helper

class WebsiteExporter(object):
    """Export a set of static views to a directory.

    The intent of this export is to be able to quickly publish a
    comment in the form of a set of static views.

    @param destination: the destination directory
    @type destination: path
    @param views: the list of views to export
    @param max_depth: maximum recursion depth
    @param progress_callback: if defined, the method will be called with a float in 0..1 and a message indicating progress
    """
    def __init__(self, controller, destination='/tmp/n', views=None, max_depth=3, progress_callback=None, video_url=None):
        self.controller=controller

        # Directory creation/checks
        self.destination=destination
        self.imgdir=os.path.join(self.destination, 'imagecache')

        if os.path.exists(self.destination) and not os.path.isdir(self.destination):
            self.log(_("%s exists but is not a directory. Cancelling website export") % self.destination)
            return
        elif not os.path.exists(self.destination):
            helper.recursive_mkdir(self.destination)

        if not os.path.isdir(self.destination):
            self.log(_("%s does not exist") % self.destination)
            return

        if not os.path.isdir(self.imgdir):
            helper.recursive_mkdir(self.imgdir)

        if views is None:
            views=[ v
                    for v in self.controller.package.views
                    if (not v.id.startswith('_')
                        and v.matchFilter['class'] == 'package'
                        and helper.get_view_type(v) == 'static')
                    ]
        self.views=views
        self.max_depth=max_depth
        if progress_callback is not None:
            # Override dummy progress_callback
            self.progress_callback=progress_callback
        self.video_url=video_url
        self.video_player=self.find_video_player(video_url)

        self.url_translation={}
        self.used_resources=[]

    def log(self, *p):
        self.controller.log(*p)

    def find_video_player(self, video_url):
        p=None
        # FIXME: module introspection here to get classes
        # Note that generic VideoPlayer is last, so that it will be the default if no other is found.
        for cl in (GoogleVideoPlayer, VideoPlayer):
            if cl.can_handle(video_url):
                p=cl(self.destination, self.video_url)
                break
        return p

    def progress_callback(self, value, msg):
        """Do-nothing progress callback.
        
        This method can be overriden by the caller from the constructor.
        """
        return

    def unconverted(self, url, reason):
        return 'unconverted.html?' + reason.replace(' ', '_')
        #return url

    def export_page(self, url, depth=0):
        """Export the given URL.

        @param url: the source url
        @param depth: the current recursion depth.
        @return: the output name of the converted url
        """
        if depth > self.max_depth:
            return self.unconverted(url, 'max depth exceeded %d > %d' % (depth, self.max_depth))

        self.log("exporting %s (%d)" % (url, depth) )
        m=re.search('(.+)#(.+)', url)
        if m:
            url=m.group(1)
        m=re.search('packages/(advene|%s)/(.*)' % self.controller.current_alias, url)
        if m:
            # Absolute url
            address=m.group(2)
        elif url in (v.id for v in self.controller.package.views):
            # Relative url.
            address='view/'+url
        else:
            return self.unconverted(url, 'unknown url')

        m=re.match('(\w+)/(.+)', address)
        if m:
            if m.group(1) == 'resources':
                # We have a resource.
                self.url_translation[url]=address
                self.used_resources.append(m.group(2))
                return address
            elif m.group(1) in ('view', 'annotations', 'relations', 'views', 'schemas', 'annotationTypes', 'relationTypes', 'queries'):
                # We skip the first element, which is either view/
                # (for toplevel views), or a bundle (annotations, views...)
                output=m.group(2).replace('/', '_')
            else:
                # Can be a query over a package, or a relative pathname
                output=address.replace('/', '_')
        else:
            output=address.replace('/', '_')

        # Generate the view
        ctx=self.controller.build_context()
        try:
            content=ctx.evaluateValue('here/%s' % address)
        except Exception, e:
            print "Exception when evaluating", address
            print unicode(e).encode('utf-8')
            return self.unconverted(url, 'error for ' + output)

        if not isinstance(content, basestring):
            return self.unconverted(url, 'not a string ' + output)

        # Extract and copy snapshots + resources
        content=re.sub(r'/packages/[^/]+/(imagecache/\d+)', r'\1.png', content)
        for t in re.findall('imagecache/(\d+)', content):
            # FIXME: not robust wrt. multiple packages/videos
            f=open(os.path.join(self.imgdir, '%s.png' % t), 'wb')
            f.write(str(self.controller.package.imagecache[t]))
            f.close()

        # Extract and copy overlays
        content=re.sub(r'/media/overlay/[^/]+/([\w\d]+)', r'imagecache/overlay_\1.png', content)
        for t in re.findall('imagecache/overlay_([\w\d]+).png', content):
            # FIXME: not robust wrt. multiple packages/videos
            a=self.controller.package.get_element_by_id(t)
            if not a:
                print "Cannot find annotation %s for overlaying"
                continue
            f=open(os.path.join(self.imgdir, 'overlay_%s.png' % t), 'wb')
            f.write(str(self.controller.gui.overlay(self.package.imagecache[a.fragment.begin], a.content.data)))
            f.close()

        # Convert all links
        for link in re.findall(r'''href=['"](.+?)['"> ]''', content):
            if link in self.url_translation and not 'max depth exceeded' in self.url_translation[link]:
                # The destination has already been processed
                # We make an exception if the link was unconverted
                # because of max depth exceeded, since another
                # path can make it have a correct depth.
                continue
            l=link.replace(self.controller.server.urlbase, '')
            if l.startswith('http:'):
                # It is an external link
                self.url_translation[link]=link
                continue
            m=re.match('packages/[^/]+/(.+)', l)
            if m:
                # It is a view
                self.url_translation[link]=self.export_page(link, depth+1)
            else:
                if not '/' in l and l in (v.id for v in self.controller.package.views):
                    # It should be a relative link.
                    self.url_translation[link]=self.export_page(os.path.dirname(url)+"/"+link, depth+1)
                elif self.video_url and link.startswith('/media/play'):
                    l=re.findall(r'/media/play/(\d+)', link)
                    if l:
                        self.url_translation[link]=self.video_player.player_url(long(l[0]))
                    else:
                        self.url_translation[link]=self.unconverted(link, 'unhandled link')
                else:
                    # It is another element.
                    self.url_translation[link]=self.unconverted(link, 'unhandled link')

        # Replace all URL references.
        for link in re.findall(r'''href=['"](.+?)['"> ]''', content):
            tr=self.url_translation[link]
            if link != tr:
                extra=[]
                attr, l = self.video_player.fix_link(tr)
                if attr is not None:
                    extra.append(attr)
                if l is not None:
                    tr=l
                if 'unconverted' in tr:
                    extra.append('onClick="return false;"')
                if extra:
                    content=re.sub('''(href=['"])%s(['"> ])''' % link,
                                   " ".join(extra) + r''' \1''' + tr + r'''\2''',
                                   content)
                else:
                    content=re.sub('''(href=['"])%s(['"> ])''' % link,
                                   r'''\1''' + tr + r'''\2''',
                                   content)
        
        content=self.video_player.transform_document(content)
        # Write the result.
        f=open(os.path.join(self.destination, output), 'w')
        f.write(content)
        f.close()

        return output

    def website_export(self):
        main_step=1.0/len(self.views)

        progress=0
        self.progress_callback(progress, _("Starting export"))

        view_url={}
        ctx=self.controller.build_context()
        # Pre-seed url translations for base views
        for v in self.views:
            link="/".join( (ctx.globals['options']['package_url'], 'view', v.id) )
            self.url_translation[link]=v.id
            view_url[v]=link

        progress=.1
        for v in self.views:
            link=view_url[v]
            self.progress_callback(progress, _("Exporting ") + v.title)
            self.export_page(link)
            progress += main_step

        self.progress_callback(.95, _("Copying resources"))

        # Copy used resources
        for path in self.used_resources:
            dest=os.path.join(self.destination, 'resources', path)

            d=os.path.dirname(dest)
            if not os.path.isdir(d):
                helper.recursive_mkdir(d)

            r=self.controller.package.resources
            for element in path.split('/'):
                r=r[element]
            output=open(dest, 'wb')
            output.write(r.data)
            output.close()

        # Generate video helper files if necessary
        self.video_player.finalize()

        # Generate a default index.html
        f=open(os.path.join(self.destination, "index.html"), 'w')
        defaultview=self.controller.package.getMetaData(config.data.namespace, 'default_utbv')
        v=self.controller.package.views.get_by_id(defaultview)
        if defaultview and v:
            default=_("""<p><strong>You should probably begin at <a href="%(href)s">%(title)s</a>.</strong></p>""") % { 'href': v.id,
                                                                                                                        'title': self.controller.get_title(v) }
        else:
            default=''
        f.write("""<html><head>%(title)s</head>
<body>
<h1>%(title)s views</h1>
%(default)s
<ul>
%(data)s
</ul></body></html>""" % { 'title': self.controller.package.title,
                           'default': default,
                           'data': "\n".join( '<li><a href="%s">%s</a>' % (self.url_translation[view_url[v]],
                                                                           v.title)
                                              for v in self.views ) })
        f.close()

        f=open(os.path.join(self.destination, "unconverted.html"), 'w')
        f.write("""<html><head>%(title)s - not converted</head>
<body>
<h1>%(title)s - not converted resource</h1>
<p>Advene was unable to export this resource.</p>
</body></html>""" % { 'title': self.controller.get_title(self.controller.package) })
        f.close()

        self.progress_callback(1.0, _("Export complete"))
        
class VideoPlayer(object):
    """Generic video player support.

    @ivar destination: the destination directory (must exist)
    @ivar video_id: the video url
    """
    def __init__(self, destination, video_url):
        self.destination=destination
        self.video_url=video_url

    @staticmethod
    def can_handle(video_url):
        """Static method indicating wether the class can handle the given video url.
        """
        return True

    def setup(self):
        """Setup the necessary files.
        """
        return

    def player_url(self, t):
        """Return the converted player URL.
        """
        return "unconverted.html?Player_at_%d" % t

    def fix_link(self, link):
        """Convert link code.

        It returns a tuple (attributes, link)

        If attributes is not None, then it is a string that should be
        added to the link's attributes.

        It link is not None, then it is the new link that should be used.

        @return tuple(attributes, link)
        """
        return None, link

    def transform_document(self, content):
        """Transform the document if necessary.

        This method is called at the end of the content generation. It
        can be used to inject javascript code for instance.
        """
        return content

    def finalize(self):
        """Finalise the environment.
        """
        return
        
class GoogleVideoPlayer(VideoPlayer):
    """Google video player support.
    """
    def __init__(self, destination, video_url):
        self.destination=destination
        self.video_url=video_url

    @staticmethod
    def can_handle(video_url):
        """Static method indicating wether the class can handle the given video url.
        """
        return 'video.google' in video_url

    def player_url(self, t):
        """Return the URL to play video at the given time.
        """
        # Format: HH:MM:SS.mmm
        return '%s#%s' % (self.video_url, time.strftime("%Hh%Mm%Ss", time.gmtime(long(t) / 1000)))

    def fix_link(self, link):
        """
        """
        if self.video_url in link:
            return "target='video_player'", link
        else:
            return None, link

    def transform_document(self, content):
        """Transform the document if necessary.

        This method is called at the end of the content generation. It
        can be used to inject javascript code for instance.
        """
        return content

    def finalize(self):
        """Finalise the environment.
        """
        return

class YoutubeVideoPlayer(VideoPlayer):
    """Youtube video player support.
    """
    def __init__(self, destination, video_url):
        self.destination=destination
        self.video_url=video_url
        l=re.findall('youtube.com/.+v=([\w\d]+)', self.video_url)
        if l:
            self.video_id=l[0]
        else:
            # FIXME: what should we do then?
            self.video_id=''

    @staticmethod
    def can_handle(video_url):
        """Static method indicating wether the class can handle the given video url.
        """
        return 'youtube' in video_url

    def player_url(self, t):
        """Return the URL to play video at the given time.
        """
        # FIXME
        # Format: HH:MM:SS.mmm
        return '%s#%s' % (self.video_url, time.strftime("%Hh%Mm%Ss", time.gmtime(long(t) / 1000)))

    def fix_link(self, link):
        """
        """
        if self.video_url in link:
            return "target='video_player'", link
        else:
            return None, link

    def transform_document(self, content):
        """Transform the document if necessary.

        This method is called at the end of the content generation. It
        can be used to inject javascript code for instance.
        """
        # Inject javascript code if necessary
        jsinject='''<script type="text/javascript" src="advene.js"></script>'''
        if re.findall('<head>', content, re.IGNORECASE):
            content=re.sub('''<head>''', '''<head>%s''' % jsinject, content)
        else:
            content=('''<head>%s</head>\n''' % jsinject) + content
        return content

    def finalize(self):
        """Finalise the environment.
        """            
        f=open(os.path.join(self.destination, "player.html"), 'w')
        f.write('''<html><head>
<title>Video Player</title>
<script type="text/javascript" src="http://ajax.googleapis.com/ajax/libs/swfobject/2/swfobject.js"></script>
</head>
<body>
  <div id="player">
    You need Flash player 8+ and JavaScript enabled to view this video.
  </div>

  <script type="text/javascript">
    function onYouTubePlayerReady(playerId) {
      var ytplayer = swfobject.getObjectById(playerId);
    }
    var params = { allowScriptAccess: "always",
                   start: 30,
                   rel: 0,
                   autoplay: 1,
                   enablejsapi: 1,
                  };
    var atts = { id: "myytplayer" };
    swfobject.embedSWF("http://www.youtube.com/v/%(video_id)s&playerapiid=ytplayer",
                       "player", "425", "356", "8", null, null, params, atts);
  </script>
</body></html>''' % { 'video_id': self.video_id })
        f.close()

        # Generate the appropriate advene.js
        f=open(os.path.join(self.destination, "advene.js"), 'w')
        f.write('''<?php
# FIXME: cross-window scripting: http://www.quirksmode.org/js/croswin.html

<script language="javascript" type="text/javascript">
<!--
function popitup(url) {
	newwindow=window.open(url,'name','height=200,width=150');
	if (window.focus) {newwindow.focus()}
	return false;
}

// -->
</script>

Then, you link to it by:

<a href="popupex.html" onclick="return popitup('popupex.html')"
	>Link to popup</a>

<div id="ytapiplayer">
    You need Flash player 8+ and JavaScript enabled to view this video.
  </div>

  <script type="text/javascript">

    var params = { allowScriptAccess: "always" };
    var atts = { id: "myytplayer" };
    swfobject.embedSWF("http://www.youtube.com/v/VIDEO_ID&enablejsapi=1&playerapiid=ytplayer",
                       "ytapiplayer", "425", "356", "8", null, null, params, atts);

  </script>


        # FIXME
?>''')
        f.close()
        # FIXME: generate advene.js and player.html
        return

