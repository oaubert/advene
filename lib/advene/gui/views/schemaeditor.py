#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Helper GUI classes and methods.

This module provides a schema editor form

"""

import advene.core.config as config
from gettext import gettext as _

import gtk
import gobject
import pango
import re
import os
import struct
import goocanvas
import cairo
import array

from advene.model.constants import adveneNS
from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.view import View
from advene.model.resources import ResourceData
from advene.model.query import Query
from advene.gui.views import AdhocView
from advene.gui.util import get_pixmap_button
from advene.gui.util import dialog
from advene.gui.popup import Menu
from advene.gui.edit.create import CreateElementPopup
from advene.gui.edit.elements import get_edit_popup
import advene.util.helper as helper
from math import *
import xml.dom
ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE


name="Schema editor view plugin"

def register(controller):
    print "Registering SchemaEditor"
    controller.register_viewclass(SchemaEditor)

class SchemaEditor (AdhocView):
    view_name = _("Schema Editor")
    view_id = 'schemaeditor'
    tooltip=("Editor view of Advene schemas")
    def __init__ (self, controller=None, parameters=None, package=None):
        super(SchemaEditor, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            )
        self.TE=None
        self.PE=None
        self.hboxEspaceSchema=None
        self.listeSchemas = None
        self.controller=controller
        self.options={}
        self.books={}
        self.dragging = False
        self.drag_x = 0
        self.drag_y = 0
        if package is None and controller is not None:
            package=controller.package
        self.__package=package
        self.widget = self.build_widget()
        #print "%s" % self.widget.size_request()
        # 51/70 ...

    def refresh(self, *p):
        return True  

    def build_widget(self):
        vbox=gtk.VBox()
        hboxMenu = gtk.HBox(spacing=5)
        #liste et boutons
        self.hboxEspaceSchema = gtk.HBox()
        self.listeSchemas = dialog.list_selector_widget(
            members=[ (s, s.getTitle()) for s in self.controller.package.getSchemas()])
        hboxMenu.pack_start(self.listeSchemas, expand=True)
        #penser a connecter le changed event.
        boutonSuppr = gtk.Button(label="Supprimer", stock=gtk.STOCK_DELETE)
        #on peut aussi associer une box au bouton pour mettre autre chose
        boutonModif = gtk.Button(label="Modifier", stock=gtk.STOCK_OPEN)
        boutonNew = gtk.Button(label="Nouveau", stock=gtk.STOCK_NEW)
        #penser a connecter les clics
        hboxMenu.pack_start(boutonModif, expand=False)
        hboxMenu.pack_start(boutonSuppr, expand=False)
        hboxMenu.pack_start(boutonNew, expand=False)
        #fin du menu
        #onglets schemas
        self.books=[] # books = [[notebook,[schemaong1,schemaong2]],...]
        self.addNotebook()
        #fin onglets
        #menu pour faire les schemas
        vBoxExp = gtk.VBox()
        packExp = gtk.VBox()# sans doute un arbre pour le package voir treeview
        packExp.pack_start(gtk.Label("Package Explorer"), expand=False)
        self.PE=packExp
        vBoxExp.pack_start(packExp)
        vBoxExp.pack_start(gtk.VSeparator(), expand=False)
        self.TE= TypeExplorer(self.controller, self.controller.package)
        vBoxExp.pack_start(self.TE, expand=True)
        self.hboxEspaceSchema.pack_end(vBoxExp, expand=True)
        #fin menu schemas
        vbox.pack_start(hboxMenu, expand=False, padding=10)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(self.hboxEspaceSchema, expand=True)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        boutonModif.connect("button-press-event", self.openSchema )
        boutonSuppr.connect("clicked", self.delSchema)
        boutonNew.connect("clicked", self.newSchema)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        #sw.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        sw.add_with_viewport(vbox)
        #sw.set_size_request(640, 480)
        return sw

    def update_list_schemas(self, active_element):
        store, i = dialog.generate_list_model( elements = [ (s, s.getTitle()) for s in self.controller.package.getSchemas()],active_element=active_element)
        self.listeSchemas.set_model(store)
        if i is None:
            i = store.get_iter_first()
        if i is not None:
            self.listeSchemas.set_active_iter(i)

    def newSchema(self, w):
        cr = CreateElementPopup(type_=Schema,
                                    parent=self.controller.package,
                                    controller=self.controller)
        schema=cr.popup(modal=True)
        if schema:
            self.update_list_schemas( active_element=schema)

    def delSchema(self, w):
        tsc, sc=self.listeSchemas.get_model()[self.listeSchemas.get_active()]
        if (sc==None):
            return False
        if (dialog.message_dialog(label="Voulez-vous effacer ce schema ?", icon=gtk.MESSAGE_QUESTION, callback=None)):
            self.controller.delete_element(sc)
            self.update_list_schemas(None)
            lenB = len(self.books)-1
            while (lenB>=0):
                book = self.books[lenB]
                lrem=[]
                for i in range(book[0].get_n_pages()):
                    #FIXME need to find a way to find the good tab (new notebookclass) ?
                    if (book[1][i]==sc):
                        lrem.append(book[0].get_nth_page(i))
                for tab in lrem:
                    self.removeSchemaArea(w, tab, book)
                lenB = lenB-1
            return True
        else:
            return False

    def removeNoteBook(self, book):
        if (self.books[0]==book):
            return False
            # un seul espace schema (le premier), on ne le supprime pas.
        indB =-1
        for i in range(len(self.books)):
            if (self.books[i]==book):
                indB=i
                break
        if (indB<0):
            print "Error removing book %s" % book
            return False
        self.books.remove(self.books[indB])
        # on retire ensuite la zone correspondante
        vb = book[0].get_parent()
        win = vb.get_parent()
        ch = win.get_children()
        # on recherche le separateur qui va avec
        sep = None
        for i in range(len(ch)):
            if (ch[i]==vb):
                sep=ch[i-1]
                break
        win.remove(sep)
        win.remove(vb)
        return True
		    
    def addNotebook(self):
        self.books.append([gtk.Notebook(),[]])
        i = len(self.books)-1
        self.books[i][0].show()
        self.books[i][0].show_tabs =1
        self.books[i][0].popup_disable()
        hboxConExplorer = gtk.HBox()
        labelConExplorer = gtk.Label("Constraint Explorer")
        hboxConExplorer.pack_start(labelConExplorer, expand=False)
        vbtemp = gtk.VBox()
        vbtemp.pack_start(self.books[i][0], expand=True, fill=True)
        vbtemp.pack_start(gtk.HSeparator(), expand=False)	    
        vbtemp.pack_start(hboxConExplorer, expand=False)
        self.hboxEspaceSchema.pack_start(vbtemp, expand=True, fill=True)
        self.hboxEspaceSchema.pack_start(gtk.VSeparator(), expand=False)
        self.hboxEspaceSchema.show_all()
        return self.books[i]

    def openSchema(self, w, event):
        tsc, schema =self.listeSchemas.get_model()[self.listeSchemas.get_active()]
        if (schema==None):
            print "Error opening schema"
            return
        if (event.button==1):
            scArea = self.addSchemaArea(tsc, schema, self.books[0])
            self.setup_canvas(scArea, schema)
        if (event.button==3):
            bk = self.addNotebook()
            scArea = self.addSchemaArea(tsc, schema, bk)
            self.setup_canvas(scArea, schema)
        return	

    def update_color(self, schema, color):
        if color is None:
            return
        for book in self.books:
            for i in range(len(book[1])):
                #FIXME need to find a way to find the good tab (new notebookclass ?
                if (book[1][i]==schema):
                    book[0].get_tab_label(book[0].get_nth_page(i)).get_children()[0].modify_bg(gtk.STATE_NORMAL,color)
                    book[0].get_tab_label(book[0].get_nth_page(i)).get_children()[0].modify_bg(gtk.STATE_ACTIVE,color)
                    book[0].get_tab_label(book[0].get_nth_page(i)).get_children()[0].modify_bg(gtk.STATE_PRELIGHT,color)
                    book[0].get_tab_label(book[0].get_nth_page(i)).get_children()[0].modify_bg(gtk.STATE_SELECTED,color)
                    book[0].get_tab_label(book[0].get_nth_page(i)).get_children()[0].modify_bg(gtk.STATE_INSENSITIVE,color)
	
    def addSchemaArea(self, nom, schema, book):
        ongLab = gtk.Label(nom)
        ong = self.create_canvas_primitives(nom, schema)
        hb=gtk.HBox()
        color = self.controller.get_element_color(schema)
        e=gtk.EventBox()
        if (color is not None):
            e.modify_bg(gtk.STATE_NORMAL,gtk.gdk.color_parse(color))
            e.modify_bg(gtk.STATE_ACTIVE,gtk.gdk.color_parse(color))
            e.modify_bg(gtk.STATE_PRELIGHT,gtk.gdk.color_parse(color))
            e.modify_bg(gtk.STATE_SELECTED,gtk.gdk.color_parse(color))
            e.modify_bg(gtk.STATE_INSENSITIVE,gtk.gdk.color_parse(color))
        e.add(ongLab)
        e.connect("button-press-event", self.schemaAreaHandler, book)
        hb.pack_start(e, expand=False, fill=False)
        b=get_pixmap_button('small_close.png')
        b.set_relief(gtk.RELIEF_NONE)
        b.connect('clicked',self.removeSchemaArea, ong , book)
        hb.pack_start(b, expand=False, fill=False)
        hb.show_all()
        book[0].append_page(ong, hb)
        book[0].show_all()
        book[1].append(schema)
        return ong.get_children()[3].get_children()[0]

    def removeSchemaArea(self, w, ong, book):
        npg = book[0].page_num(ong)
        book[0].remove_page(npg)
        del book[1][npg]
        if (book[0].get_n_pages()==0):
            self.removeNoteBook(book)
            # si plus de page on retire l'espace schema.

    def schemaAreaHandler(self, w, event, book):
        if (event.button==3):
            menu = gtk.Menu()
            item = gtk.MenuItem(_("Close"))
            item.connect("activate", self.removeSchemaArea, w, book)
            menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())

    def buttonTypeAHandler(self,w, event, canvas, schema ):
        if (event.button==1):
            # ajout d'un nouveau type
            self.addAnnotationTypeGroup(canvas, schema)

    def buttonTypeRHandler(self,w, event, canvas, schema ):
        if (event.button==1):
            # ajout d'un nouveau type
            self.addRelationTypeGroup(canvas, schema)

### Functions to add remove modify RelationTypesGroup and redraw them when moving AnnotationTypeGroup

    def addRelationTypeGroup(self, canvas, schema, name=" ", type=None, members=[]):
        # FIXME : type out of schema
        cvgroup = RelationTypeGroup(self.controller, canvas, schema, name, type, members)
        if cvgroup is not None:
            self.setup_rel_signals (cvgroup)
        return cvgroup

    def findRelationTypeGroup(self, typeId, canvas):
        #cherche le groupe correspondant a l'id
        root = canvas.get_root_item ()
        for i in range(0, root.get_n_children()):
            if hasattr(root.get_child(i), 'type') and root.get_child(i).type.id== typeId:
                return root.get_child(i)
        return None

    def rel_redraw(self, rtg):
        rtg.redraw()

    def removeRelationTypeGroup(self, group):
        group.remove()
        ### FIXME : propagate to other canvas

### Functions to add remove modify AnnotationTypesGroup
    def addAnnotationTypeGroup(self, canvas, schema, name=" ", type=None, rx =20, ry=30):
        cvgroup = AnnotationGroup(self.controller, canvas, schema, name, type, rx, ry)
        if cvgroup is not None:
            self.setup_annot_signals(cvgroup, schema)
        return cvgroup


    def removeAnnotationTypeGroup(self, group, schema):
        group.remove()
        ### FIXME : propagate to other canvas
        ### FIXME : delete relation types based on this annotation type in othe shcemas

### Functions to handle notification signals

    def setup_rel_signals (self, item):
        #pour capter les events sur les relations du dessin
        #item.connect ("motion_notify_event", self.rel_on_motion_notify)
        item.connect ("button_press_event", self.rel_on_button_press)
        item.connect ("button_release_event", self.rel_on_button_release)
        return

    def setup_annot_signals (self, item, schema):
        #pour capter les events sur les annotations du dessin
        item.connect ("motion_notify_event", self.annot_on_motion_notify)
        item.connect ("button_press_event", self.annot_on_button_press, schema)
        item.connect ("button_release_event", self.annot_on_button_release)

    def rel_on_button_press (self, item, target, event):
        #on remplit l'explo
        self.TE.initWithType(item.type)
        self.drawFocusOn(item.line)
        if event.button == 1:
            self.drag_x = event.x
            self.drag_y = event.y
            fleur = gtk.gdk.Cursor (gtk.gdk.FLEUR)
            canvas = item.get_canvas ()
            canvas.pointer_grab (item,
                                gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.BUTTON_RELEASE_MASK,
                                fleur,
                                event.time)
            self.dragging = True
        elif event.button == 3:
            def menuRem(w, item):
                self.removeRelationTypeGroup(item)
                return True
            menu = gtk.Menu()
            itemM = gtk.MenuItem(_("Remove Relation Type"))
            itemM.connect("activate", menuRem, item )
            menu.append(itemM)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def rel_on_button_release (self, item, target, event):
        canvas = item.get_canvas ()
        canvas.pointer_ungrab (item, event.time)
        self.dragging = False

### events on annotationTypeGroup

    def annot_on_motion_notify (self, item, target, event):
        if (self.dragging == True) and (event.state & gtk.gdk.BUTTON1_MASK):
            new_x = event.x
            new_y = event.y
            item.translate (new_x - self.drag_x, new_y - self.drag_y)
            for rtg in item.rels:
                self.rel_redraw(rtg)
        return True

    def annot_on_button_press (self, item, target, event, schema):
        self.TE.initWithType(item.type)
        self.drawFocusOn(item.rect)
        if event.button == 1:
            self.drag_x = event.x
            self.drag_y = event.y
            fleur = gtk.gdk.Cursor (gtk.gdk.FLEUR)
            canvas = item.get_canvas ()
            canvas.pointer_grab (item,
                                    gtk.gdk.POINTER_MOTION_MASK | gtk.gdk.BUTTON_RELEASE_MASK,
                                    fleur,
                                    event.time)
            self.dragging = True
        elif event.button == 3:
            def menuRem(w, item, schema):
                self.removeAnnotationTypeGroup(item, schema)
                return True
            def menuNew(w, item, schema, member2):
                mem = []
                mem.append(item.type)
                mem.append(member2)
                self.addRelationTypeGroup(item.get_canvas(), schema, members=mem)
                return True
            menu = gtk.Menu()
            itemM = gtk.MenuItem(_("Remove Annotation Type"))
            itemM.connect("activate", menuRem, item, schema )
            menu.append(itemM)
            itemM = gtk.MenuItem(_("Create Relation Type between this one and..."))
            ssmenu = gtk.Menu()
            itemM.set_submenu(ssmenu)
            for s in self.controller.package.getSchemas():
                sssmenu = gtk.Menu()
                itemSM = gtk.MenuItem(s.title)
                itemSM.set_submenu(sssmenu)
                for a in s.getAnnotationTypes(): 
                    itemSSM = gtk.MenuItem(a.title)
                    itemSSM.connect("activate", menuNew, item, schema, a )
                    sssmenu.append(itemSSM)
                ssmenu.append(itemSM)
            menu.append(itemM)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def annot_on_button_release (self, item, target, event):
        canvas = item.get_canvas ()
        canvas.pointer_ungrab (item, event.time)
        self.dragging = False
        # on check si des relations sont liees, auquel cas on les redessine
        for rtg in item.rels:
            self.rel_redraw(rtg)

### events on background

    def on_background_button_press (self, item, target, event, schema):
        self.TE.initWithType(None)
        canvas = item.get_canvas()
        self.drawFocusOn(canvas)
        if (event.button==3):
            def menuNew(w, canvas, schema):
                self.addAnnotationTypeGroup(canvas, schema)
                return True
            def pick_color(w, schema):
                color = self.controller.gui.update_color(schema)
                self.update_color(schema, color)
            menu = gtk.Menu()
            itemM = gtk.MenuItem(_("Select a color"))
            itemM.connect("activate", pick_color, schema)
            menu.append(itemM)
            itemM = gtk.MenuItem(_("New Annotation Type"))
            itemM.connect("activate", menuNew, canvas, schema )
            menu.append(itemM)
            itemM = gtk.MenuItem(_("Copy Annotation Type from Schema..."))
            #itemM.connect("activate", menuNew, canvas )
            menu.append(itemM)
            itemM = gtk.MenuItem(_("Move Annotation Type from Schema..."))
            #itemM.connect("activate", menuNew, canvas )
            menu.append(itemM)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def drawFocusOn(self, item):
        canvas=None
        if isinstance(item, goocanvas.Canvas):
            canvas=item
        else:
            canvas = item.get_canvas()
            item.props.line_width = 4.0
        root = canvas.get_root_item()
        for i in range(root.get_n_children()):
            if hasattr(root.get_child(i), 'rect'):
                ite=root.get_child(i).rect
            elif hasattr(root.get_child(i), 'line'):
                ite=root.get_child(i).line
            else:
                ite=None
            if ite is not None and ite != item:
                ite.props.line_width = 2.0
		    
    def create_canvas_primitives (self, nom, schema):
        #if (self.controller.get_element_color(schema) is not None):
        #   bg_color = self.controller.get_element_color(schema)
	    #else:
        bg_color = gtk.gdk.Color (55000, 55000, 65535, 0)
        vbox = gtk.VBox (False, 4)
        vbox.set_border_width (4)
        w = gtk.Label(nom)
        hbox = gtk.HBox (False, 4)
        vbox.pack_start (w, False, False, 0)
        vbox.pack_start (hbox, False, False, 0)
        #Create the canvas   
        canvas = goocanvas.Canvas()
        canvas.modify_base (gtk.STATE_NORMAL, bg_color)
        canvas.set_bounds (0, 0, 8000, 6000)
        #Zoom
        w = gtk.Label ("Zoom:")
        hbox.pack_start (w, False, False, 0)
        adj = gtk.Adjustment (1.00, 0.05, 100.00, 0.05, 0.50, 0.50)
        adj.connect("value_changed", self.zoom_changed, canvas)
        w = gtk.SpinButton (adj, 0.0, 2)
        w.set_size_request (50, -1)
        hbox.pack_start (w, False, False, 0)
        #Types
        boutonTypeA = gtk.Button(label="AT")
        boutonTypeR = gtk.Button(label="RT")
        boutonTypeA.connect("button-press-event", self.buttonTypeAHandler, canvas, schema )
        boutonTypeR.connect("button-press-event", self.buttonTypeRHandler, canvas, schema )
        hbox.pack_start (boutonTypeA, False, False, 0)
        hbox.pack_start (boutonTypeR, False, False, 0)
        vbox.pack_start (gtk.VSeparator(), expand=False)
        scrolled_win = gtk.ScrolledWindow ()
        vbox.pack_start (scrolled_win, True, True, 0)
        scrolled_win.add(canvas)
        return vbox

    def zoom_changed (self, adj, canvas):
        canvas.set_scale (adj.get_value())
    
    def center_toggled (self, button, data):
        pass

    #pour dessiner le schema
    def setup_canvas (self, canvas, schema):
        root = canvas.get_root_item ()
        root.connect("button_press_event", self.on_background_button_press, schema)
        annotTypes = schema.getAnnotationTypes()
        relTypes = schema.getRelationTypes()
        a=0
        for i in annotTypes:
            self.addAnnotationTypeGroup(canvas, schema, i.getTitle(), i, 20, 20+a*90)
            a=a+1
        r=0
        for j in relTypes:
            self.addRelationTypeGroup(canvas,schema, j.getTitle(), j)
            r=r+1

### Type Explorer class
class TypeExplorer (gtk.ScrolledWindow):
    def __init__ (self, controller=None, package=None):
        gtk.ScrolledWindow.__init__(self)
        self.controller=controller
        self.type=None
        if package is None and controller is not None:
            package=controller.package
        vbox=gtk.VBox()
        hboxNom = gtk.HBox()
        labelNom = gtk.Label("Title : ")
        entryNom = gtk.Entry()
        self.TName = entryNom 
        hboxNom.pack_start(labelNom)
        hboxNom.pack_start(entryNom)
        hboxAddAtt = gtk.HBox()
        labelAddAtt = gtk.Label("Add attribute")
        boutonAddAtt = gtk.Button("Add")
        boutonAddAtt.connect("clicked", self.addAtributeSpace )
        hboxAddAtt.pack_start(labelAddAtt)
        hboxAddAtt.pack_start(boutonAddAtt)
        hboxMime = gtk.HBox()
        labelMime = gtk.Label("Mime Type : ")
        entryMime = gtk.Entry()
        self.TMimeType = entryMime
        # a remplacer par la selection de type Mime
        hboxMime.pack_start(labelMime)
        hboxMime.pack_start(entryMime)
        hboxId = gtk.HBox()
        labelId1 = gtk.Label("Id :")
        labelId2 = gtk.Label("")
        self.TId = labelId2
        hboxId.pack_start(labelId1)
        hboxId.pack_start(labelId2)
        labelAtt = gtk.Label("Attributes : ")
        labelTypeExplorer = gtk.Label("Type Explorer")
        espaceAtt = gtk.VBox()
        self.TAttsSpace = espaceAtt
        self.TAtts = []
        espaceBoutons = gtk.HBox()
        self.boutonSave = gtk.Button("Save")
        self.boutonSave.connect("clicked", self.saveType)
        self.boutonCancel = gtk.Button("Cancel")
        self.boutonCancel.connect("clicked", self.cancelType )
        espaceBoutons.pack_end(self.boutonCancel, expand=False, fill=False)
        espaceBoutons.pack_end(self.boutonSave, expand=False, fill=False)
        vbox.pack_start(labelTypeExplorer, expand=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(hboxId, expand=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(hboxNom, expand=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(hboxMime, expand=False, fill=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        #vbox.pack_start(hboxAddAtt, expand=False, fill=False)
        #vbox.pack_start(gtk.HSeparator(), expand=False)
        #vbox.pack_start(labelAtt, expand=False, fill=False)
        #vbox.pack_start(espaceAtt, expand=False, fill=False)
        #vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(espaceBoutons, expand=False, fill=False)	
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.add_with_viewport(vbox)

    def refresh(self, *p):
        return True  

    def getTypeId(self):
        return self.TId.get_text()

    def setTypeId(self, name=""):
        if (name is None):
            return False
        self.TId.set_text(name)
        return True
    
    def getTypeName(self):
        return self.TName.get_text()

    def setTypeName(self, name=""):
        if (name is None):
            return False
        self.TName.set_text(name)
        return True

    #a faire evoluer en liste
    def getMimeType(self):
        return self.TMimeType.get_text()

    #a faire evoluer en liste
    def setMimeType(self, mimetype):
        self.TMimeType.set_text(mimetype)
        return True

    def addAtributeSpace(self, w, nom="New Attribute", type="None", con=""):
        #ajouter eventuellement un contenu directement avec x params
        #print "%s" % len(self.get_children()[0].get_children()[0].get_children())
        boxAtt = gtk.HBox()
        eNom = gtk.Entry()
        eNom.set_text(nom)
        eNom.set_size_request(100, 20)
        eType = gtk.combo_box_new_text()
        eType.append_text("None") # ajouter tous les types etfocus sur le type type
        eContrainte = gtk.Entry() # liste + entry ? bouton + fenetre pour creer ?
        eContrainte.set_text(con)
        eContrainte.set_size_request(50, 20)
        bSuppr = gtk.Button("Remove")
        bSuppr.set_size_request(50, 20)
        boxAtt.pack_start(eNom)
        boxAtt.pack_start(eType)
        boxAtt.pack_start(eContrainte)
        boxAtt.pack_start(bSuppr)
        self.TAtts.append(boxAtt)
        self.TAttsSpace.pack_start(boxAtt)
        self.TAttsSpace.show_all()
        return True	

    def initWithType(self, type):
        if type is None:
            # tout remettre a vide
            self.type=None
            self.setTypeName("")
            self.setTypeId("")
            self.setMimeType("")
            return True
        self.type = type
        self.setTypeName(self.type.title)
        self.setTypeId(self.type.id)
        self.setMimeType(self.type.mimetype)
        #boucle sur les attributs pour creer et remplir les lignes
        #if (self.type.mimetype=='application/x-advene-relaxNG'):
            # appel de la fonction qui parse l'arbre
            # pour chaque element attribut, appel de la fonction qui ajoute une case aux attributs.
        #    pass
        return True

    def saveType(self, button):
        self.type.title=self.getTypeName()
        self.type.mimetype=self.getMimeType()
        #save attributes
        # send controller an event
        # redraw contents

    def cancelType(self, button):
        self.initWithType(self.type)

# FIXME :
# ajouter la gestion d'events 
# sur ajout/modif/suppr de type, refresh les canvas
# sur modifs schema, refresh les canvas
# sur modif contenus, refresh l'explo
# envoyer event sur modifs contenus

class AnnotationGroup (goocanvas.Group):
    def __init__(self, controller=None, canvas=None, schema=None, name=" ", type=None, rx =0, ry=0):
        goocanvas.Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.schema=schema
        self.name=name
        self.type=type
        self.color = "black"
        self.rels=[] # rel groups
        if type is None:
            print "Annotation Type Creation"
            # appeler la creation du type d'annotation
            cr=CreateElementPopup(type_=AnnotationType,
                                    parent=schema,
                                    controller=self.controller)
            at=cr.popup(modal=True)
            if (at==None):
                return None
            self.type=at
            self.name=self.type.title
        nbannot = len(self.type.getAnnotations())
        if (self.controller.get_element_color(self.type) is not None):
            self.color = self.controller.get_element_color(self.type)

        self.rect = goocanvas.Rect (parent = self,
                                    x = rx,
                                    y = ry,
                                    width = 140,
                                    height = 80,
                                    fill_color_rgba = 0x3cb37150,
                                    stroke_color = self.color,
                                    line_width = 2.0)
        self.text = goocanvas.Text (parent = self,
                                    text = self.name + " ("+str(nbannot)+")",
                                    x = rx+5, 
                                    y = ry+10,
                                    width = -1,
                                    anchor = gtk.ANCHOR_W,
                                    font = "Sans Bold 10")
    def remove(self):
        while (len(self.rels)>0):
            self.rels[0].remove()
        self.controller.delete_element(self.type)
        parent = self.get_parent()
        child_num = parent.find_child (self)
        parent.remove_child (child_num)
	
class RelationTypeGroup (goocanvas.Group):
    def __init__(self, controller=None, canvas=None, schema=None, name=" ", type=None, members=[]):
        goocanvas.Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.schema=schema
        self.name=name
        self.type=type
        self.color = "black"
        self.members=members
        if self.type is None:
            print "Relation Type Creation"
            # appeler la creation du type d'annotation
            cr=CreateElementPopup(type_=RelationType,
                                    parent=schema,
                                    controller=self.controller)
            rt=cr.popup(modal=True)
            if (rt==None):
                return None
            self.type=rt
            if (len(self.members)==0):
                pop = get_edit_popup (self.type, self.controller)
                pop.edit(modal=True)
            else:
                # FIXME if more than 2 members
                self.type.hackedMemberTypes=( '#' + self.members[0].id, '#' + self.members[1].id )
        linked = self.type.getHackedMemberTypes()
        #print "%s %s %s %s %s" % (self.type, self.name, self.schema, self.members, linked)
        for i in linked:
            # Add annotations types to members
            typeA = self.getIdFromURI(i)
            typ = helper.get_id(self.controller.package.getAnnotationTypes(), typeA)
            if typ is not None:
                self.members.append(typ)
                #print "%s %s %s %s" % (i, typeA, typ, self.members)
        self.name=self.type.title
        self.color = "black"
        if (self.controller.get_element_color(self.type) is not None):
            self.color = self.controller.get_element_color(self.type)
        temp=[]
        for i in members:
            gr = self.findAnnotationTypeGroup(i.id, canvas)
            x=1
            y=1
            w=0
            h=0
            if gr is not None:
                x = gr.rect.get_bounds().x1
                y = gr.rect.get_bounds().y1
                w = gr.rect.props.width
                h = gr.rect.props.height
                gr.rels.append(self)
            # 8 points of rect
            temp.append([[x+w/2,y],[x+w/2,y+h],[x,y+h/2],[x+w,y+h/2],[x,y],[x+w,y],[x+w,y+h],[x,y+h]])
        if len(temp)<2:
            return None
        # FIXME if more than 2 linked types
        it=0
        x1,y1,x2,y2,d = self.distMin(temp[it],temp[it+1])

        if d==0:
            # verify slot to attach the relation on annotation type before doing that
            p = goocanvas.Points ([(x1, y1), (x1,y1-20), (x1+10, y1-20), (x2+10, y2)])
        else:
            p = goocanvas.Points ([(x1, y1), (x2, y2)])
        #ligne
        self.line = goocanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color = self.color,
                                        line_width = 3.0,
                                        start_arrow = False,
                                        end_arrow = True,
                                        arrow_tip_length =3.0,
                                        arrow_length = 4.0,
                                        arrow_width = 3.0
                                        )
                                        #start_arrow = False,
                                        #end_arrow = True,
        if (d==0):
            self.text = goocanvas.Text (parent = self,
                                        text = self.name,
                                        x = x1+5,
                                        y = y1-10,
                                        width = -1,
                                        anchor = gtk.ANCHOR_CENTER,
                                        font = "Sans Bold 10")	
        else:
            self.text = goocanvas.Text (parent = self,
                                        text = self.name,
                                        x = (x1+x2)/2, 
                                        y = (y1+y2)/2,
                                        width = -1,
                                        anchor = gtk.ANCHOR_CENTER,
                                        font = "Sans Bold 10")

    #FIXME : hack to find id from type's uri
    def getIdFromURI(self, uri):
        return uri[1:]

    def findAnnotationTypeGroup(self, typeId, canvas):
        root = canvas.get_root_item ()
        for i in range(0, root.get_n_children()):
            if hasattr(root.get_child(i), 'type') and root.get_child(i).type.id == typeId:
                return root.get_child(i)
        return None

    # function to calculate min distance between x points
    def distMin(self,l1,l2):
        d=-1
        xd1=xd2=yd1=yd2=0
        for i in range(len(l1)):
            x1 = l1[i][0]
            y1 = l1[i][1]
            for j in range(len(l2)):
                x2 = l2[j][0]
                y2 = l2[j][1]
                nd=sqrt((x2-x1)*(x2-x1)+(y2-y1)*(y2-y1))
                if ((d==-1) or (nd < d)):
                    d = nd
                    xd1 = x1
                    xd2 = x2
                    yd1 = y1
                    yd2 = y2
        return xd1,yd1,xd2,yd2,d

    def redraw(self):
        #print self.members
        temp=[] 
        for i in self.members:
            gr = self.findAnnotationTypeGroup(i.id, self.get_canvas())
            x=1
            y=1
            w=0
            h=0
            if gr is not None:
                x = gr.rect.get_bounds().x1
                y = gr.rect.get_bounds().y1
                w = gr.rect.props.width
                h = gr.rect.props.height
            # 8 points
            temp.append([[x+w/2,y],[x+w/2,y+h],[x,y+h/2],[x+w,y+h/2],[x,y],[x+w,y],[x+w,y+h],[x,y+h]])
        x1,y1,x2,y2,d = self.distMin(temp[0],temp[1])
        if d==0:
            # modifier en fonction du slot
            p = goocanvas.Points ([(x1, y1), (x1,y1-20), (x1+10, y1-20), (x2+10, y2)])
            self.text.translate(x1-10-self.text.get_bounds().x1, y1-15-self.text.get_bounds().y1)
        else:
            p = goocanvas.Points ([(x1, y1), (x2, y2)])
            self.text.translate((x1+x2-20)/2-self.text.get_bounds().x1, (y1+y2-30)/2-self.text.get_bounds().y1)
        self.line.props.points=p

    def remove(self):
        for i in self.members:
            gr = self.findAnnotationTypeGroup(i.id, self.get_canvas())
            if gr is not None:
                gr.rels.remove(self)
            else:
                #Annotation group outside schema
                #we don't remove the link because it doesn't have one
                print "%s n'est pas dans ce schema" % i.id
        #print "removing %s" % self.type
        self.controller.delete_element(self.type)
        parent = self.get_parent()
        child_num = parent.find_child (self)
        parent.remove_child(child_num)
