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
# along with Advene; if not, write to the Free Software
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
        sw.set_size_request(640, 480)
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
                    #FIXME need to find a way to find the good tab (new notebookclass ?
                    if (book[1][i]==sc):
                        lrem.append(book[0].get_nth_page(i))
                for tab in lrem:
                    self.removeSchemaArea(w, tab, book)
                lenB = lenB-1
            return True
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
            print "erreur remove book %s" % indB
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
            print "error schema"
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

    def addSchemaArea(self, nom, schema, book):
        ongLab = gtk.Label(nom)
        ong = self.create_canvas_primitives(nom, schema)
        hb=gtk.HBox()
        color = self.controller.get_element_color(schema)
        e=gtk.EventBox()
        if (color is not None):
            e.modify_bg(gtk.STATE_NORMAL,gtk.gdk.color_parse(color))
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

    def getRelTypeFromGroup(self, grp):
        typeid = grp.get_child(2).props.text
        rtype = None
        for Rt in self.controller.package.getRelationTypes():
            if Rt.getId() == typeid:
                rtype = Rt
                break
        return rtype

    #hack pour recup l'id des types d'annotation lies a un type de relation
    def getIdFromURI(self, uri):
        return uri[1:]

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

    def addRelationTypeGroup(self, canvas, schema, name=" ", type=None):
        # determiner ce que lie la ligne pour chopper les coordonnees des rects et la placer ou il faut
        # si les 2 types sont le meme : fleche a 4 points pour faire demi tour
        # si le type de dest n'est pas dans le schema : mettre en evidence
        # sinon determiner les 2 faces les plus proches et tracer une ligne.
        if type is None:
            print "creation type rel"
            # appeler la creation du type d'annotation
            cr=CreateElementPopup(type_=RelationType,
                                  parent=schema,
                                  controller=self.controller)
            rt=cr.popup(modal=True)
            if (rt==None):
                return False
            if rt:
                pop = get_edit_popup (rt, self.controller)
                pop.edit(modal=True)
            type=rt
            name=type.getTitle()
        root = canvas.get_root_item ()
        cvgroup = goocanvas.Group(parent = root)
        color = "black"
        if (self.controller.get_element_color(type) is not None):
            color = self.controller.get_element_color(type)
        #ca renvoie les uri ...
        linked = type.getHackedMemberTypes()
        temp=[]
        for i in linked:
            # on recup le type d'A.
            typeA = self.getIdFromURI(i)
            # on cherche le groupe du type d'A.
            gr = self.findAnnotationTypeGroup(typeA, canvas)
            x=1
            y=1
            w=0
            h=0
            if gr is not None:
                # on prend le rect
                x = gr.get_child(0).get_bounds().x1
                y = gr.get_child(0).get_bounds().y1
                w = gr.get_child(0).props.width
                h = gr.get_child(0).props.height
                # on ajoute une reference au type pour que la relation soit redessinee si on bouge l'annotation.
                goocanvas.Text (parent = gr,
                                   text = type.getId(),
                                   x = x,
                                   y = y,
                                   visibility=goocanvas.ITEM_HIDDEN)
            # on stocke les 4 milieux de cotes et les 4 angles aussi
            temp.append([[x+w/2,y],[x+w/2,y+h],[x,y+h/2],[x+w,y+h/2],[x,y],[x+w,y],[x+w,y+h],[x,y+h]])
        # a modif si plus de 2 types lies.
        it=0
        x1,y1,x2,y2,d = self.distMin(temp[it],temp[it+1])

        if d==0:
            p = goocanvas.Points ([(x1, y1), (x1,y1-20), (x1+10, y1-20), (x2+10, y2)])
        else:
            p = goocanvas.Points ([(x1, y1), (x2, y2)])
#ligne
        item = goocanvas.Polyline (parent = cvgroup,
                                        close_path = False,
                                        points = p,
                                        stroke_color = color,
                                        line_width = 3.0,
                                        start_arrow = True,
                                        end_arrow = True)
                                        #start_arrow = False,
                                        #end_arrow = False,
                                        #arrow_tip_length =3.0,
                                        #arrow_length = 4.0,
                                        #arrow_width = 3.5
        if (d==0):
            itemL = goocanvas.Text (parent = cvgroup,
                               text = name,
                               x = x1+5,
                               y = y1-10,
                               width = -1,
                               anchor = gtk.ANCHOR_CENTER,
                               font = "Sans Bold 10")
        else:
            itemL = goocanvas.Text (parent = cvgroup,
                               text = name,
                               x = (x1+x2)/2,
                               y = (y1+y2)/2,
                               width = -1,
                               anchor = gtk.ANCHOR_CENTER,
                               font = "Sans Bold 10")
        #pour conserver la relation au type
        if type is not None:
                itemLC = goocanvas.Text (parent = cvgroup,
                                   text = type.getId(),
                                   x = x1,
                                   y = y1,
                                   visibility=goocanvas.ITEM_HIDDEN)
        self.setup_rel_signals (cvgroup)
        return cvgroup

    def findRelationTypeGroup(self, typeId, canvas):
        #cherche le groupe correspondant a l'id
        root = canvas.get_root_item ()
        for i in range(0, root.get_n_children()):
            if root.get_child(i).get_n_children()>=3: # sinon il est en construction...
                ite=root.get_child(i).get_child(2)
                if isinstance(ite,goocanvas.Text):
                    if ite.props.text == typeId:
                        return ite.get_parent()
        return None


    def rel_redraw(self, rtg):
        #redessine la relation
        rtype = self.getRelTypeFromGroup(rtg)
        linked = rtype.getHackedMemberTypes()
        temp=[]
        for i in linked:
            # on recup le type d'A.
            typeA = self.getIdFromURI(i)
            # on cherche le groupe du type d'A.
            gr = self.findAnnotationTypeGroup(typeA, rtg.get_canvas())
            x=1
            y=1
            w=0
            h=0
            if gr is not None:
                # on prend le rect
                x = gr.get_child(0).get_bounds().x1
                y = gr.get_child(0).get_bounds().y1
                w = gr.get_child(0).props.width
                h = gr.get_child(0).props.height
            # on stocke les 4 milieux de cotes (les 4 angles aussi ?)
            temp.append([[x+w/2,y],[x+w/2,y+h],[x,y+h/2],[x+w,y+h/2],[x,y],[x+w,y],[x+w,y+h],[x,y+h]])
        x1,y1,x2,y2,d = self.distMin(temp[0],temp[1])
        if d==0:
            p = goocanvas.Points ([(x1, y1), (x1,y1-20), (x1+10, y1-20), (x2+10, y2)])
            rtg.get_child(1).translate(x1-10-rtg.get_child(1).get_bounds().x1, y1-15-rtg.get_child(1).get_bounds().y1)
        else:
            p = goocanvas.Points ([(x1, y1), (x2, y2)])
            rtg.get_child(1).translate((x1+x2-20)/2-rtg.get_child(1).get_bounds().x1, (y1+y2-30)/2-rtg.get_child(1).get_bounds().y1)
        rtg.get_child(0).props.points=p

    def removeRelationTypeGroup(self, group):
        #retire tout le groupe du schemaArea
        # retire aussi ses references dans les annotations types
        rtype = self.getRelTypeFromGroup(group)
        typeId = rtype.getId()
        linked = rtype.getHackedMemberTypes()
        for i in linked:
            # on recup le type d'A.
            typeA = self.getIdFromURI(i)
            # on cherche le groupe du type d'A.
            gr = self.findAnnotationTypeGroup(typeA, group.get_canvas())
            #on cherche la ref a la relation et on l'efface
            if gr is not None:
                for j in range(3,gr.get_n_children()):
                    ite=gr.get_child(j)
                    if isinstance(ite,goocanvas.Text):
                        if ite.props.text == typeId:
                            gr.remove_child(j)
                            break
            else:
                #c'est une relation vers un type externe au schema, a supprimer dans adv2
                print "%s n'est pas dans ce schema" % typeA
        idRt = group.get_child(2).props.text
        typ = self.controller.package.get_element_by_id(idRt)
        self.controller.delete_element(typ)
        parent = group.get_parent()
        child_num = parent.find_child (group)
        parent.remove_child (child_num)

    def addAnnotationTypeGroup(self, canvas, schema, name=" ", type=None, rx =20, ry=30):
        if type is None:
            print "creation type annot"
            # appeler la creation du type d'annotation
            cr=CreateElementPopup(type_=AnnotationType,
                                  parent=schema,
                                  controller=self.controller)
            at=cr.popup(modal=True)
            if (at==None):
                return False
            type=at
            name=type.getTitle()
# appel edition nouveau type...
        root = canvas.get_root_item ()
        cvgroup = goocanvas.Group(parent = root)
        color = "black"
        nbannot = len(type.getAnnotations())
        if (self.controller.get_element_color(type) is not None):
            color = self.controller.get_element_color(type)
        item = goocanvas.Rect (parent = cvgroup,
                               x = rx,
                               y = ry,
                               width = 140,
                               height = 80,
                               fill_color_rgba = 0x3cb37150,
                               stroke_color = color,
                               line_width = 2.0)
        itemL = goocanvas.Text (parent = cvgroup,
                               text = name + " ("+str(nbannot)+")",
                               x = rx+5,
                               y = ry+10,
                               width = -1,
                               anchor = gtk.ANCHOR_W,
                               font = "Sans Bold 10")
        #lable invisible pour conserver la relation au type

        itemLC = goocanvas.Text (parent = cvgroup,
                                   text = type.getId(),
                                   x = rx,
                                   y = ry,
                                   visibility=goocanvas.ITEM_HIDDEN)
        self.setup_annot_signals(cvgroup, schema)
        return cvgroup

    def findAnnotationTypeGroup(self, typeId, canvas):
        #trouve le groupe correspondant a l'id
        root = canvas.get_root_item ()
        for i in range(0, root.get_n_children()):
            if root.get_child(i).get_n_children()>=3: # sinon il est en construction...
                ite=root.get_child(i).get_child(2)
                if isinstance(ite,goocanvas.Text):
                    if ite.props.text == typeId:
                        return ite.get_parent()
        return None

    def removeAnnotationTypeGroup(self, group, schema):
        #retire tout le groupe du schemaArea
        # on commence par efacer les types de relation lies
        # ajouter un warning pour prevenir qu'on va effacer les rels associees ?
        while (group.get_n_children()>3):
            ite=group.get_child(3)
            if isinstance(ite,goocanvas.Text):
                rgr = self.findRelationTypeGroup(ite.props.text, group.get_canvas())
                if rgr is not None:
                    self.removeRelationTypeGroup(rgr)
        idAt = group.get_child(2).props.text
        typ = self.controller.package.get_element_by_id(idAt)
        self.controller.delete_element(typ)
        parent = group.get_parent()
        child_num = parent.find_child (group)
        parent.remove_child (child_num)

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
        if event.button == 1:
            #on remplit l'explo
            self.TE.initWithType(item.get_child(2).props.text,"rt")# label du type
            self.drawFocusOn(item.get_child(0))
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
            def menuRem(item, line):
                self.removeRelationTypeGroup(line)
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


    def annot_on_motion_notify (self, item, target, event):
        if (self.dragging == True) and (event.state & gtk.gdk.BUTTON1_MASK):
            new_x = event.x
            new_y = event.y
            item.translate (new_x - self.drag_x, new_y - self.drag_y)
            # on check si des relations sont liees, auquel cas on les redessine
            for i in range(3,item.get_n_children()):
                rtg = self.findRelationTypeGroup(item.get_child(i).props.text, item.get_canvas())
                self.rel_redraw(rtg)
        return True

    def annot_on_button_press (self, item, target, event, schema):
        if event.button == 1:
            self.TE.initWithType(item.get_child(2).props.text,"at")# id du type
            self.drawFocusOn(item.get_child(0))
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
            def menuRem(w, rect, schema):
                self.removeAnnotationTypeGroup(rect, schema)
                return True
            def menuNew(w, rect, schema):
                #creation du type, ajout des types annots en membre
                #self.addRelationTypeGroup()
                return True
            menu = gtk.Menu()
            itemM = gtk.MenuItem(_("Remove Annotation Type"))
            itemM.connect("activate", menuRem, item, schema )
            menu.append(itemM)
            itemM = gtk.MenuItem(_("Create Relation Type between this one and..."))
            #sous menu avec les types d'annots tries par schema, celui la en premier
            #
            #itemM.connect("activate", menuNew, item, schema )
            menu.append(itemM)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def annot_on_button_release (self, item, target, event):
        canvas = item.get_canvas ()
        canvas.pointer_ungrab (item, event.time)
        self.dragging = False
        # on check si des relations sont liees, auquel cas on les redessine
        for i in range(3,item.get_n_children()):
            rtg = self.findRelationTypeGroup(item.get_child(i).props.text, canvas)
            if rtg is not None:
                self.rel_redraw(rtg)

    def on_background_button_press (self, item, target, event, schema):

        self.TE.initWithType(None)
        canvas = item.get_canvas ()
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
            itemM = gtk.MenuItem(_("Add Annotation Type"))
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
        root = canvas.get_root_item()
        for i in range(root.get_n_children()):
            ite=root.get_child(i).get_child(0)
            if ite==item:
                ite.props.line_width = 4.0
            else:
                ite.props.line_width = 2.0

    def create_canvas_primitives (self, nom, schema):
        #if (self.controller.get_element_color(schema) is not None):
        #    bg_color = self.controller.get_element_color(schema)
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


#classe pour l'explorateur de types
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
        boutonSave = gtk.Button("Save")
        #boutonSave.connect("clicked", self.saveType )
        boutonCancel = gtk.Button("Cancel")
        #boutonCancel.connect("clicked", self.cancelType )
        espaceBoutons.pack_end(boutonCancel, expand=False, fill=False)
        espaceBoutons.pack_end(boutonSave, expand=False, fill=False)
        vbox.pack_start(labelTypeExplorer, expand=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(hboxId, expand=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(hboxNom, expand=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(hboxMime, expand=False, fill=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(hboxAddAtt, expand=False, fill=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
        vbox.pack_start(labelAtt, expand=False, fill=False)
        vbox.pack_start(espaceAtt, expand=False, fill=False)
        vbox.pack_start(gtk.HSeparator(), expand=False)
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

    def initWithType(self, typeid, rat="None"):
        if typeid is None:
            # tout remettre a vide
            self.type=None
            self.setTypeName("")
            self.setTypeId("")
            self.setMimeType("")
            return False
        if rat=="at":
            self.type = helper.get_id(self.controller.package.getAnnotationTypes(), typeid)
        elif rat=="rt":
            self.type = helper.get_id(self.controller.package.getRelationTypes(), typeid)
        else:
            print "Not an annotation or relation Type"
            return False
        self.setTypeName(self.type.getTitle())
        self.setTypeId(self.type.getId())
        self.setMimeType(self.type.getMimetype())
        #boucle sur les attributs pour creer et remplir les lignes
        if (self.type.getMimetype()=='application/x-advene-relaxNG'):
            # appel de la fonction qui parse l'arbre
            # pour chaque element attribut, appel de la fonction qui ajoute une case aux attributs.
            pass

        return True


