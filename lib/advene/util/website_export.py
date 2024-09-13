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
name = "Website export plugin"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import os
from pathlib import Path
import time
import re
import urllib.request, urllib.parse, urllib.error
import mimetypes
import shutil

import advene.core.config as config
import advene.util.helper as helper
from advene.util.exporter import GenericExporter, register_exporter

fragment_re           = re.compile('(.*)#(.+)')
package_expression_re = re.compile(r'packages/(\w+)/(.*)')
href_re               = re.compile(r'''(xlink:href|href|src|about|resource)=['"](.+?)['"> ]''')
snapshot_re           = re.compile(r'/packages/[^/]+/imagecache/(\d+)')
tales_re              = re.compile(r'(\w+)/(.+)')
player_re             = re.compile(r'/media/play(/|\?position=)(\d+)(/(\d+))?')
overlay_re            = re.compile(r'/media/overlay/([^/]+)/([\w\d]+)(/.+)?')

@register_exporter
class WebsiteExporter(GenericExporter):
    """Export a set of static views to a directory.

    This filter does a static scraping of a set of static views, in
    order to publish them independently from Advene.
    """
    name = _("Website exporter")
    extension = ""
    mimetype = "inode/directory"

    @classmethod
    def is_valid_for(cls, expr):
        """Is the template valid for different types of sources.

        expr is either "package" or "annotation-type" or "annotation-container".
        """
        return expr == 'package'

    def __init__(self, controller=None, source=None, callback=None):
        super().__init__(controller, source, callback)

        # Default options
        self.video_url = (self.controller.package and self.controller.package.getMetaData(config.data.namespace, "media_uri")) or ""
        self.depth = 3
        self.views = ""

        self.optionparser.add_option("-u", "--video-url",
                                     type="string",
                                     action="store",
                                     dest="video_url",
                                     default=self.video_url,
                                     help=_("URL for the video, if it is available on a sharing website.\n It can also be a mp4 or ogg file, relative to the export directory."))

        self.optionparser.add_option("-d", "--depth",
                                     action="store",
                                     type="int",
                                     dest="depth",
                                     default=self.depth,
                                     help=_("Maximum recursion depth"))

        self.optionparser.add_option("-v", "--views",
                                     type="string",
                                     action="store",
                                     dest="views",
                                     default=self.views,
                                     help=_("Comma-separated list of views to export - leave blank for all views"))

    def find_video_player(self, video_url):
        p=None
        # FIXME: module introspection here to get classes
        # Note that generic VideoPlayer is last, so that it will be the default if no other is found.
        # Note: HTML5VideoPlayer is also generic
        for cl in (GoogleVideoPlayer, YoutubeVideoPlayer, HTML5VideoPlayer, VideoPlayer):
            if cl.can_handle(video_url):
                if cl == HTML5VideoPlayer and not self.video_url:
                    # Use current player movie
                    self.video_url = self.controller.get_default_media()
                p=cl(self.output, self.video_url)
                break


        return p

    def unconverted(self, url, reason):
        return 'unconverted.html?url=%s&reason=%s' % (
            urllib.parse.quote(url),
            urllib.parse.quote_plus(reason))

    def get_contents(self, url):
        """Return the contents of the given view.
        """
        # Handle fragments
        m = fragment_re.search(url)
        if m:
            url = m.group(1)
            if not url:
                # Empty URL: we are addressing ourselves.
                return None

        m = package_expression_re.search(url)
        if m:
            # Absolute url
            address = m.group(2)
        elif url in (v.id for v in self.controller.package.views):
            # Relative url for a view
            address = 'view/'+url
        else:
            # No match. Do not try to retrieve
            return None

        # Generate the view
        ctx = self.controller.build_context()
        try:
            content = ctx.evaluateValue('here/%s' % address)
        except Exception:
            logger.error("Exception when evaluating %s", address, exc_info=True)
            content = None

        if not isinstance(content, str):
            # Not a string. Could be an Advene element
            try:
                c = content.view(context=self.controller.build_context(here=content))
                content = c
            except AttributeError:
                # Apparently not. Fallback on explicit string conversion.
                content = str(content)
        return content

    def translate_links(self, content, baseurl=None, max_depth_exceeded=False):
        """Translate links from the given content.

        This method updates self.url_translation.

        It returns a list of URLs that should be processed in the next stage (depth+1).
        """
        res = set()
        used_snapshots = set()
        used_overlays = set()
        used_resources = set()

        # Convert all links
        for (attname, url) in href_re.findall(content):
            if url in self.url_translation:
                # Translation already done.
                continue

            original_url=url

            if url.startswith('javascript:'):
                self.url_translation[original_url] = original_url
                continue

            m = snapshot_re.search(url)
            # Image translation. Add a .png extension.
            if m:
                self.url_translation[original_url] = "imagecache/%s.png" % m.group(1)
                used_snapshots.add(m.group(1))
                continue

            m = overlay_re.search(url)
            if m:
                ident = m.group(2)
                tales = m.group(3) or ''
                # FIXME: not robust wrt. multiple packages/videos
                a = self.controller.package.get_element_by_id(ident)
                if not a:
                    self.url_translation[original_url]=self.unconverted(url, 'non-existent annotation')
                    self.log("Cannot find annotation %s for overlaying" % ident)
                    continue
                name = ident+tales.replace('/', '_')
                self.url_translation[original_url] = 'imagecache/overlay_%s.png' % name
                used_overlays.add( (ident, tales) )
                continue

            link = url.replace(self.controller.get_urlbase(), '')

            if link.startswith('http:') or link.startswith('https:'):
                # It is an external url
                self.url_translation[url] = url
                continue

            fragment = None
            m = fragment_re.search(url)
            if m:
                url = m.group(1)
                fragment = m.group(2)
                if not url:
                    # Empty URL: we are addressing ourselves.
                    continue
                if url in self.url_translation:
                    self.url_translation[original_url] = "%s#%s" % (self.url_translation[url],
                                                                  fragment)
                    # URL already processed
                    continue

            m = package_expression_re.search(url)
            if m:
                # Absolute url
                tales = m.group(2)
            elif url in (v.id for v in self.controller.package.views):
                # Relative url.
                tales = 'view/'+url
            else:
                tales = None

            if tales:
                m = tales_re.match(tales)
                if m:
                    if m.group(1) == 'resources':
                        # We have a resource.
                        self.url_translation[url] = tales
                        used_resources.add(m.group(2))
                        continue
                    elif m.group(1) in ('view', 'annotations', 'relations',
                                        'views', 'schemas', 'annotationTypes', 'relationTypes',
                                        'queries', 'export'):
                        # We skip the first element, which is either view/
                        # (for toplevel views), or a bundle (annotations, views...)
                        output = m.group(2).replace('/', '_')

                        # Check if we can add a suffix. This
                        # will facilitate handling by webservers.
                        path = m.group(2).split('/')
                        if path and len(path) == 1 and m.group(1) == 'export':
                            # Export filter. Find out its extension.
                            filter_class = self.controller.get_export_filters(ident=path[0])
                            if filter_class is not None and filter_class.extension:
                                output = output + "." + filter_class.extension
                        elif path and (len(path) == 1 or path[-2] == 'view'):
                            # Got a view. Check its mimetype
                            v = self.controller.package.get_element_by_id(path[-1])
                            if v and hasattr(v, 'content'):
                                if v.content.mimetype == 'text/plain':
                                    # Workaround: the mimetypes
                                    # modules returns a default .ksh
                                    # extension for text/plain. Ensure
                                    # that the more appropriate .txt
                                    # is used.
                                    ext = '.txt'
                                else:
                                    ext = mimetypes.guess_extension(v.content.mimetype)
                                if ext is not None:
                                    output = output + ext
                        elif len(path) > 1 and path[-2] in ('annotations', 'relations',
                                                            'views',
                                                            'schemas', 'annotationTypes', 'relationTypes',
                                                            'queries'):
                            # Reference to an Advene element, without
                            # a specified view. Assume a default view
                            # is applied and that it will output html.
                            output = output + ".html"

                        if m.group(1) == 'views':
                            # Addressing a view content. Prepend a
                            # prefix, so that it will not overwrite
                            # the result of the view applied to the
                            # package.
                            output = 'view_' + output

                        res.add(original_url)
                    else:
                        # Can be a query over a package, or a relative pathname
                        output = tales.replace('/', '_')
                        res.add(original_url)
                else:
                    output = tales.replace('/', '_')
                self.url_translation[url] = output
                if fragment:
                    self.url_translation[original_url] = "%s#%s" % (output, fragment)
            elif self.video_url and player_re.search(url):
                m = player_re.search(url)
                if 'stbv' not in url:
                    self.url_translation[original_url] = self.video_player.player_url(m.group(2), m.group(4))
                else:
                    self.url_translation[original_url] = self.unconverted(url, 'need advene')
            else:
                # It is another element.
                self.url_translation[url] = self.unconverted(url, 'unhandled url')
        if max_depth_exceeded:
            # Max depth exceeded: all new links should be marked as unconverted
            for url in res:
                self.url_translation[url] = self.unconverted(url, 'max depth exceeded')
            res=set()
        return res, used_snapshots, used_overlays, used_resources

    def fix_links(self, content):
        """Transform contents in order to fix links.
        """
        # Avoid messing with JSON data
        content = content.strip()
        if content.startswith('{') or content.startswith('[') or content.startswith('"'):
            return content
        # Convert all links
        for (attname, link) in href_re.findall(content):
            if link.startswith('imagecache/'):
                # Already processed by the global regexp at the beginning
                continue
            if link.startswith('#'):
                continue
            m = fragment_re.search(link)
            if m:
                fragment = m.group(2)
                tr = self.url_translation.get(m.group(1))
            else:
                fragment = None
                tr = self.url_translation.get(link)
            if tr is None:
                logger.error("website export bug: %s was not translated", link)
                continue
            if link != tr:
                extra=[]
                attr, reallink = self.video_player.fix_link(tr)
                if attr is not None:
                    extra.append(attr)
                if reallink is not None:
                    tr = reallink
                if 'unconverted' in tr:
                    extra.append('onClick="return false;"')
                if fragment is not None:
                    tr = tr + '#'+fragment

                if extra:
                    exp = '''(%s=['"])%s(['"> ])''' % (attname, re.escape(link))
                    content = re.sub(exp, " ".join(extra) + r''' \1''' + tr + r'''\2''', content)
                else:
                    exp = '''(%s=['"])%s(['"> ])''' % (attname, re.escape(link))
                    content = re.sub(exp, r'''\1''' + tr + r'''\2''', content)

        content = self.video_player.transform_document(content)
        return content

    def write_data(self, url, content, used_snapshots, used_overlays, used_resources):
        """Write the converted content as well as associated data.
        """
        # Write the content.
        output = self.url_translation[url]
        with open(self.output / output, 'w', encoding='utf-8') as f:
            f.write(content)

        if not self.imgdir.is_dir():
            self.imgdir.mkdir(parents=True)

        # Copy snapshots
        for t in used_snapshots:
            # FIXME: not robust wrt. multiple packages/videos
            with open(self.imgdir / f'{t}.png', 'wb') as f:
                f.write(bytes(self.controller.package.imagecache[t]))

        # Copy overlays
        for (ident, tales) in used_overlays:
            # FIXME: not robust wrt. multiple packages/videos
            a = self.controller.package.get_element_by_id(ident)
            if not a:
                logger.error("Cannot find annotation %s for overlaying", ident)
                continue
            name = ident + tales.replace('/', '_')
            if tales:
                # There is a TALES expression
                ctx = self.controller.build_context(here=a)
                data = ctx.evaluateValue('here' + tales)
            else:
                data = a.content.data
            with open(os.path.join(self.imgdir, 'overlay_%s.png' % name), 'wb') as f:
                try:
                    f.write(self.controller.gui.overlay(self.controller.package.imagecache[a.fragment.begin], data))
                except TypeError:
                    logger.exception("Error when trying to export overlayed thumbnail")

        # Copy resources
        for path in used_resources:
            dest = self.output / 'resources' / path

            d = dest.parent
            if not d.is_dir():
                d.mkdir(parents=True)

            r = self.controller.package.resources
            for element in path.split('/'):
                r = r[element]

            data = r.data
            if isinstance(data, str):
                data = data.encode('utf-8')
            with open(dest, 'wb') as output:
                output.write(data)

    def check_requirements(self):
        self.output = Path(self.output)
        self.imgdir = self.output / 'imagecache'

        if self.callback is None:
            self.callback = lambda progress, message: True

        if self.output.exists() and not self.output.is_dir():
            self.log(_("%s exists but is not a directory. Cancelling website export") % self.output)
            return
        elif not self.output.exists():
            self.output.mkdir(parents=True)

        # Last check, to be sure
        if not self.output.is_dir():
            self.log(_("%s does not exist") % self.output)
            return

        if self.views:
            # Specified view ids, should be a list of string, convert them to a list of views
            viewlist = [ (v.strip(), self.controller.package.get_element_by_id(v)) for v in self.views.split(",") ]
            missing_views = [ n[0] for n in viewlist if n[1] is None ]
            if missing_views:
                logger.error(_("The following views do not exist: %s"), ", ".join(missing_views))
            views = [ n[1] for n in viewlist if n[1] is not None ]
        else:
            # Empty, use all views
            views = [ v
                      for v in self.controller.package.views
                      if (not v.id.startswith('_') # Do not include admin views
                          and v.matchFilter['class'] == 'package'
                          and helper.get_view_type(v) == 'static')
                     ]
        defaultview = self.controller.package.getMetaData(config.data.namespace, 'default_utbv')
        v = self.controller.package.views.get_by_id(defaultview)
        if v is not None and v not in views:
            # The specified default view is not present in views
            # (probably because it starts with _). Add it.
            views.append(v)

        self.views = views

        self.video_player = self.find_video_player(self.video_url)
        self.url_translation = {}

    def export(self, filename=None):
        # The filename parameter is the output dir
        try:
            self.output = Path(filename)
        except TypeError:
            logger.error(_("This export filter must be called with an output directory name"))
            return

        if self.output.exists() and not self.output.is_dir():
            logger.error(f"{filename} exists and is not a directory.")
            return

        self.check_requirements()

        main_step = 1.0/self.depth
        progress = 0
        if not self.callback(progress, _("Starting export")):
            return

        view_url = {}
        ctx = self.controller.build_context()

        # Pre-seed url translations for base views
        for v in self.views:
            link = "/".join( (ctx.globals['options']['package_url'], 'view', v.id) )
            if hasattr(v, 'content'):
                if v.content.mimetype == 'text/plain':
                    ext = '.txt'
                else:
                    ext = mimetypes.guess_extension(v.content.mimetype)
                if ext is not None:
                    self.url_translation[link] = "%s%s" % (v.id, ext)
                else:
                    self.url_translation[link] = v.id
            else:
                self.url_translation[link] = v.id
            view_url[v] = link

        progress = .01
        depth = 1

        links_to_be_processed = list(view_url.values())

        while depth <= self.depth:
            max_depth_exceeded = (depth == self.depth)
            step = main_step / (len(links_to_be_processed) or 1)
            if not self.callback(progress, _("Depth %d") % depth):
                return
            links = set()
            for url in links_to_be_processed:
                if not self.callback(progress, _("Depth %(depth)d: processing %(url)s") % locals()):
                    return
                progress += step
                content = self.get_contents(url)

                (new_links,
                 used_snapshots,
                 used_overlays,
                 used_resources) = self.translate_links(content,
                                                        url,
                                                        max_depth_exceeded)
                links.update(new_links)

                # Write contents
                self.write_data(url,
                                self.fix_links(content),
                                used_snapshots,
                                used_overlays,
                                used_resources)

            links_to_be_processed = links
            depth += 1

        if not self.callback(0.95, _("Finalizing")):
            return

        # Copy static video player resources
        for (original, dest) in self.video_player.needed_resources():
            dest = self.output / dest
            original = Path(original)
            if original.is_dir():
                # Copy tree
                if dest.exists():
                    # First remove old version
                    if dest.is_dir():
                        shutil.rmtree(dest, True)
                    else:
                        dest.unlink()
                shutil.copytree(original, dest)
            else:
                # Copy file
                d = dest.parent
                if not d.is_dir():
                    d.mkdir(parents=True)
                shutil.copy(original, dest)

        # Generate video helper files if necessary
        self.video_player.finalize()

        # Generate a default index.html
        name = "index.html"
        if name in list(self.url_translation.values()):
            name = "_index.html"

        default_href = ''
        default = ''
        defaultview = self.controller.package.getMetaData(config.data.namespace, 'default_utbv')
        v = self.controller.package.views.get_by_id(defaultview)
        if defaultview and v:
            url = view_url.get(v)
            if url is not None:
                default_href = self.url_translation[url]
                default = _("""<p><strong>You should probably begin at <a href="%(href)s">%(title)s</a>.</strong></p>""") % { 'href': default_href, 'title': self.controller.get_title(v) }
            else:
                # No view url defined for v???
                logger.error("No view url for default view")

        with open(os.path.join(self.output, name), 'w', encoding='utf-8') as f:
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

        frame="frame.html"
        if frame in list(self.url_translation.values()):
            frame="_frame.html"
        with open(self.output / frame, 'w', encoding='utf-8') as f:
            f.write(f"""<html>
            <head><title>{self.controller.get_title(self.controller.package)}</title></head>
            <frameset cols="70%%,30%%">
            <frame name="main" src="{default_href or name}" />
            <frame name="video_player" src="" />
            </frameset>
            </html>
        """)

        with open(self.output / "unconverted.html", 'w', encoding='utf-8') as f:
            title = self.controller.get_title(self.controller.package)
            f.write(f"""<html><head>{title} - not converted</head>
<body>
<h1>{title} - not converted resource</h1>
<p>Advene was unable to export this resource.</p>
</body></html>""")

        self.callback(1.0, _("Export complete"))

class VideoPlayer:
    """Generic video player support.

    @ivar destination: the destination directory (must exist)
    @ivar video_id: the video url
    """
    def __init__(self, destination, video_url):
        self.output=destination
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

    def player_url(self, begin, end=None):
        """Return the converted player URL.
        """
        return "unconverted.html?Player_at_%s" % begin

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

    def needed_resources(self):
        """Return a list of needed resources.

        It is a list of ( original_file/dir, destination_file/dir )
        items. The destination_file/dir is a directory relative to the base
        of the exported websites.
        """
        return []

class GoogleVideoPlayer(VideoPlayer):
    """Google video player support.
    """
    @staticmethod
    def can_handle(video_url):
        """Static method indicating wether the class can handle the given video url.
        """
        return 'video.google' in video_url

    def player_url(self, begin, end=None):
        """Return the URL to play video at the given time.
        """
        # Format: HH:MM:SS.mmm
        return '%s#%s' % (self.video_url, time.strftime("%Hh%Mm%Ss", time.gmtime(int(begin) / 1000)))

    def fix_link(self, link):
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
    @staticmethod
    def can_handle(video_url):
        """Static method indicating wether the class can handle the given video url.
        """
        return 'youtube.com/watch' in video_url

    def player_url(self, begin, end=None):
        """Return the URL to play video at the given time.
        """
        # Format: HHhMMmSSs
        return '%s#t=%s' % (self.video_url, time.strftime("%Hh%Mm%Ss", time.gmtime(int(begin) / 1000)))

    def fix_link(self, link):
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

class HTML5VideoPlayer(VideoPlayer):
    """HTML5 video player support.
    """
    @staticmethod
    def can_handle(video_url):
        """Static method indicating wether the class can handle the given video url.
        """
        # We always can handle videos.
        return True

    def player_url(self, begin, end=None):
        """Return the URL to play video at the given time.
        """
        if end is not None:
            return '%s#t=%.03f,%.03f' % (self.video_url, (float(begin) / 1000.0), (float(end) / 1000.0))
        else:
            return '%s#t=%.03f' % (self.video_url, (float(begin) / 1000.0))

    def fix_link(self, link):
        if self.video_url in link:
            return "target='video_player'", link
        else:
            return None, None

    def transform_document(self, content):
        """Transform the document if necessary.

        This method is called at the end of the content generation. It
        can be used to inject javascript code for instance.
        """
        # Inject javascript code if necessary

        # Note: Firefox does not seem to like <link href=... /> style
        # of closing tags. Use the explicit end tag.
        jsinject='''
<link type="text/css" href="./resources/HTML5/theme/jqueryui.css" rel="stylesheet"></link>
<link href="./resources/HTML5/style.css" rel="stylesheet" type="text/css"></link>

<script type="text/javascript" src="./resources/HTML5/jquery.js"></script>
<script type="text/javascript" src="./resources/HTML5/jqueryui.js"></script>
<script type="text/javascript" src="./resources/HTML5/advene.js"></script>
<script type="text/javascript">
    $(document).ready(function() {
        $(document).advene();
    });
</script>
'''
        head_re = re.compile('<head>', re.IGNORECASE)
        if head_re.findall(content):
            content = head_re.sub('''<head>%s''' % jsinject, content)
        else:
            # It could be SVG
            svg_re = re.compile('<svg(.+?)>', re.IGNORECASE)
            if svg_re.search(content):
                jsinject = """<script type="text/ecmascript" xlink:href="./resources/HTML5/advene_svg.js"></script>
<g id="video_layout" class="draggable" transform="translate(50 400)">
  <foreignObject>
    <div xmlns="http://www.w3.org/1999/xhtml">
      <video style="position: fixed; top: 300px; left: 50px;" controls="true" id="video_player" width="320" height="200" src=""></video>
    </div>
  </foreignObject>
</g>
"""
                content = svg_re.sub(r'''<svg\1>
%s''' % jsinject, content)
            else:
                content = '''<head>%s</head>\n''' % jsinject + content
        return content

    def finalize(self):
        """Finalise the environment.
        """
        return

    def needed_resources(self):
        """Return a list of needed resources.
        """
        return [ ( config.data.advenefile('HTML5', 'web'), 'resources/HTML5' ) ]
