"""Transcription view.
"""

import sys

import pygtk
#pygtk.require ('2.0')
import gtk
import gobject

import advene.core.config as config

# Advene part
from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

import advene.util.importer

import advene.util.vlclib as vlclib

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.edit.create
import advene.gui.popup

class TranscriptionImporter(advene.util.importer.GenericImporter):
    """Transcription importer.
    """
    def __init__(self, transcription_edit=None, **kw):
        super(TranscriptionImporter, self).__init__(**kw)
        self.transcription_edit=transcription_edit
        self.name = _("Transcription importer")

    def process_file(self, filename):
        if filename != 'transcription':
            return None
        if self.package is None:
            self.init_package()
        self.convert(self.transcription_edit.parse_transcription())
        return self.package

class TranscriptionEdit:
    def __init__ (self, controller=None):
        self.controller=controller
        self.package=controller.package
        self.tooltips=gtk.Tooltips()

        self.sourcefile=""
        
        self.timestamp_mode_toggle=gtk.CheckButton(_("Insert timestamps"))
        self.timestamp_mode_toggle.set_active (True)
        
        self.widget=self.build_widget()

    def build_widget(self):
        vbox = gtk.VBox()
        self.textview = gtk.TextView()
        # We could make it editable and modify the annotation
        self.textview.set_editable(True)
        self.textview.set_wrap_mode (gtk.WRAP_CHAR)

        self.textview.connect("button-press-event", self.button_press_event_cb)

        vbox.add(self.textview)
        vbox.show_all()
        return vbox

    def remove_anchor(self, button, anchor, b):
        begin=b.get_iter_at_child_anchor(anchor)
        end=begin.copy()
        end.forward_char()
        b.delete_interactive(begin, end, True)
        button.destroy()
        return True
    
    def button_press_event_cb(self, textview, event):
        if event.button != 1:
            return False
        if not self.timestamp_mode_toggle.get_active():
            return False
        textwin=textview.get_window(gtk.TEXT_WINDOW_TEXT)
        if event.window != textwin:
            print "Event.window: %s" % str(event.window)
            print "Textwin: %s" % str(textwin)
            return False

        (x, y) = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                                  int(event.x),
                                                  int(event.y))
        it=textview.get_iter_at_location(x, y)
        if it is None:
            print "Error in get_iter_at_location"
            return False
        
        if (self.controller.player.status == self.controller.player.PlayingStatus
            or
            self.controller.player.status == self.controller.player.PlayingStatus):
            self.create_timestamp_mark(self.controller.player.current_position_value,
                                       it)
        return False

    def create_timestamp_mark(self, timestamp, it):
        b=self.textview.get_buffer()
        anchor=b.create_child_anchor(it)
        # Create the mark representation
        child=gtk.Button("")
        child.connect("clicked", self.remove_anchor, anchor, b)
        # FIXME: handle right-click button to display a menu
        # with Goto action
        self.tooltips.set_tip(child, "%s" % vlclib.format_time(timestamp))
        child.timestamp=timestamp
        child.show()
        self.textview.add_child_at_anchor(child, anchor)
        return
    
    def populate(self, annotations):
        """Populate the buffer with data taken from the given annotations.
        """
        b=self.textview.get_buffer()
        # Clear the buffer
        begin,end=b.get_bounds()
        b.delete(begin, end)
        # FIXME: check for conflicting bounds
        l=[ (a.fragment.begin, a.fragment.end, a)
            for a in annotations ]
        l.sort(lambda a,b: cmp(a[0], b[0]))
        for (b, e, a) in l:
            it=b.get_iter_at_mark(b.get_insert())
            self.create_timestamp_mark(b, it)
            b.insert_at_cursor(unicode(a.content.data))
            it=b.get_iter_at_mark(b.get_insert())
            self.create_timestamp_mark(e, it)
        return            
        
    def parse_transcription(self):
        """Parse the transcription text.

        Return : a iterator on a dict with keys
        'begin', 'end', 'content' 
        (compatible with advene.util.importer)
        """

        # FIXME: offer an option "discontinuous" where an empty
        # annotation (\s*) represents a discontinuity.
        t=0
        b=self.textview.get_buffer()
        begin=b.get_start_iter()
        end=begin.copy()
        while end.forward_char():
            a=end.get_child_anchor()
            if a and a.get_widgets():
                # Found a TextAnchor
                timestamp=a.get_widgets()[0].timestamp
                text=b.get_text(begin, end, include_hidden_chars=False)
                yield { 'begin': t,
                        'end': timestamp,
                        'content': text }
                t=timestamp
                begin=end.copy()
        # End of buffer. Create the last annotation
        timestamp=self.controller.player.stream_duration
        text=b.get_text(begin, end, include_hidden_chars=False)
        yield { 'begin': t,
                'end': timestamp,
                'content': text }
        
    def save_transcription(self, button=None):
        fs = gtk.FileSelection ("Save transcription to...")

        def close_and_save(button, fs):
            self.save_output(filename=fs.get_filename())
            fs.destroy()
            return True

        fs.ok_button.connect_after ("clicked", close_and_save, fs)
        fs.cancel_button.connect ("clicked", lambda win: fs.destroy ())

        fs.show ()
        return True

    def save_output(self, filename=None):
        # FIXME: find a way to insert timestamps and recover them later
        b=self.textview.get_buffer()
        begin,end=b.get_bounds()
        out=b.get_text(begin, end)
        f=open(filename, "w")
        f.write(out)
        f.close()
        self.controller.log(_("Transcription saved to %s") % filename)
        return True
    
    def load_transcription_cb(self, button=None):
        fs = gtk.FileSelection ("Select transcription file to load")

        def close_and_save(button, fs):
            self.load_transcription(filename=fs.get_filename())
            fs.destroy()
            return True

        fs.ok_button.connect_after ("clicked", close_and_save, fs)
        fs.cancel_button.connect ("clicked", lambda win: fs.destroy ())

        fs.show ()
        return True

    def load_transcription(self, filename=None):
        b=self.textview.get_buffer()
        try:
            f=open(filename, 'r')
        except Exception, e:
            self.controller.log(_("Cannot read %s: %s") % (filename, str(e)))
            return
        data=unicode("".join(f.readlines())).encode('utf-8')
        b.set_text(data)
        self.sourcefile=filename
        return

    def convert_transcription_cb(self, button=None):
        print "convert transcription"
        if not self.controller.gui:
            self.controller.log(_("Cannot convert the data : no associated package"))
            return True

        at=self.controller.gui.ask_for_annotation_type(text=_("Select the annotation type to generate"), create=True)

        print "at = " + str(at)
        
        if at is None:
            self.controller.log(_("Conversion cancelled"))
            return True

        ti=TranscriptionImporter(transcription_edit=self)
        ti.package=self.controller.package
        ti.defaultype=at
        ti.process_file('transcription')

        self.controller.modified=True
        self.controller.notify("PackageLoad", package=ti.package)
        self.controller.log(_('Converted from file %s :') % self.sourcefile)
        kl=ti.statistics.keys()
        kl.sort()
        for k in kl:
            v=ti.statistics[k]
            if v > 1:
                self.controller.log('\t%d %ss' % (v, k))
            else:
                self.controller.log('\t%d %s' % (v, k))
        # Feedback
        dialog = gtk.MessageDialog(
            None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_INFO, gtk.BUTTONS_CLOSE,
            _("Conversion completed.\n%s annotations generated.") % ti.statistics['annotation'])
        response=dialog.run()
        dialog.destroy()
        
        return True
    
    def get_widget (self):
        """Return the TreeView widget."""
        return self.widget

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'transcribeview')

        window.set_title (_("Transcription alignment"))

        vbox = gtk.VBox()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add (sw)
        sw.add_with_viewport (self.get_widget())
        if self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb,
                            window, self)

        hb=gtk.HButtonBox()
        hb.set_homogeneous(False)

        hb.pack_start(self.timestamp_mode_toggle, expand=False)
        
        b=gtk.Button(stock=gtk.STOCK_OPEN)
        b.connect ("clicked", self.load_transcription_cb)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_SAVE)
        b.connect ("clicked", self.save_transcription)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CONVERT)
        b.connect ("clicked", self.convert_transcription_cb)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect ("clicked", lambda w: window.destroy ())
        hb.pack_start(b, expand=False)

        vbox.pack_start(hb, expand=False)

        window.add(vbox)

        window.show_all()
        return window

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    class DummyController:
        def log(self, *p):
            print p
            
        def notify(self, *p, **kw):
            print "Notify %s %s" % (p, kw)

            
    controller=DummyController()
    controller.gui=None

    import advene.player.dummy
    player=advene.player.dummy.Player()
    controller.player=player
    controller.player.status=controller.player.PlayingStatus
    
    #controller.package = Package (uri=sys.argv[1])
    config.data.path['resources']='/usr/local/src/advene-project/share'
    controller.package = Package (uri="new_pkg",
                            source=config.data.advenefile(config.data.templatefilename))

    transcription = TranscriptionEdit(controller=controller)

    window = transcription.popup()

    window.connect ("destroy", lambda e: gtk.main_quit())

    gtk.main ()

