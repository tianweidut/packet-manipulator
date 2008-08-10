#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2008 Adriano Monteiro Marques
#
# Author: Francesco Piccinno <stack.box@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

import gtk
import Backend

from widgets.HexView import HexView
from widgets.Expander import AnimatedExpander
from widgets.Sniff import SniffPage

from views import UmitView
from Icons import get_pixbuf

from Manager.PreferenceManager import Prefs

class ProtocolHierarchy(gtk.ScrolledWindow):
    def __init__(self, parent):
        gtk.ScrolledWindow.__init__(self)

        self.__create_widgets()
        self.__pack_widgets()
        self.__connect_signals()

        self.session = parent
        self.proto_icon = get_pixbuf('protocol_small')

        self.reload()

    def reload(self):
        self.store.clear()

        if not self.session.packet:
            return

        root = None

        # We pray to be ordered :(
        for proto in Backend.get_packet_protos(self.session.packet):
            root = self.store.append(root, [self.proto_icon, Backend.get_proto_name(proto), proto])

        self.tree.expand_all()

    def __create_widgets(self):
        # Icon / string (like TCP packet with some info?) / hidden
        self.store = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self.tree = gtk.TreeView(self.store)

        pix = gtk.CellRendererPixbuf()
        txt = gtk.CellRendererText()

        col = gtk.TreeViewColumn('Name')

        col.pack_start(pix, False)
        col.pack_start(txt, True)

        col.set_attributes(pix, pixbuf=0)
        col.set_attributes(txt, text=1)

        self.tree.append_column(col)

        self.tree.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)
        self.tree.set_rules_hint(True)

    def __pack_widgets(self):
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_ETCHED_IN)

        self.add(self.tree)

    def __connect_signals(self):
        self.tree.enable_model_drag_dest([('text/plain', 0, 0)], gtk.gdk.ACTION_COPY)
        self.tree.connect('drag-data-received', self.__on_drag_data)

    def __on_drag_data(self, widget, ctx, x, y, data, info, time):
        if data and data.format == 8:
            ret = self.view.get_dest_row_at_pos(x, y)

            if not ret:
                self.store.append(None, [None, data.data, data.data, None])
            else:
                path, pos = ret
                print path, pos

            ctx.finish(True, False, time)
        else:
            ctx.finish(False, False, time)

    def get_active_protocol(self):
        """
        Return the selected protocol or the most
        important protocol if no selection.

        @return a tuple Packet, Protocol or None, None
        """

        model, iter = self.tree.get_selection().get_selected()

        if not iter:
            return None, None

        obj = model.get_value(iter, 2)
        
        assert (Backend.is_proto(obj), "Should be a Protocol instance.")

        return self.session.packet, obj


class PacketPage(gtk.VPaned):
    def __init__(self, parent):
        super(PacketPage, self).__init__()

        self.session = parent

        self.proto_hierarchy = ProtocolHierarchy(self.session)
        self.hexview = HexView()

        self.pack1(self.proto_hierarchy, True, False)
        self.pack2(self.hexview, True, False)

        Prefs()['gui.maintab.hexview.font'].connect(self.hexview.modify_font)
        Prefs()['gui.maintab.hexview.bpl'].connect(self.hexview.set_bpl)

    def redraw_hexview(self):
        """
        Redraws the hexview
        """
        if self.session.packet:
            self.hexview.payload = Backend.get_packet_raw(self.session.packet)
        else:
            print "redraw_hexview(): no packet!!!"
            self.hexview.payload = ""

    def reload(self):
        self.redraw_hexview()
        self.proto_hierarchy.reload()

class SessionPage(gtk.VBox):
    def __init__(self, iface=None, args={}, fname=None, packet=None):
        gtk.VBox.__init__(self)

        assert(iface or fname or packet)

        if iface:
            self.packet = None
            self.sniff_page = SniffPage(self, Backend.SniffContext(iface, **args))
            self._label = gtk.Label("* Capturing on %s" % iface)

        elif fname:
            self.packet = None
            self.sniff_page = SniffPage(self, Backend.SniffContext(iface=None, capfile=fname))
            self._label = gtk.Label(fname)

        else:
            if isinstance(packet, basestring):
                packet = Backend.get_proto(packet)()
                packet = Backend.MetaPacket(packet)

            self.packet = packet
            self.sniff_page = SniffPage(self)
            self._label = gtk.Label("*" + packet.get_protocol_str())

        self.set_border_width(4)

        self.vpaned = gtk.VPaned()
        self.sniff_expander = AnimatedExpander("Sniff perspective", 'sniff_small')
        self.packet_expander = AnimatedExpander("Packet perspective", 'packet_small')

        self.packet_page = PacketPage(self)

        self.vpaned.pack1(self.sniff_expander, True, False)
        self.vpaned.pack2(self.packet_expander, True, False)

        self.sniff_expander.add(self.sniff_page)
        self.packet_expander.add(self.packet_page)

        self.packet_page.reload()

        self.pack_start(self.vpaned)
        self.show_all()

    def set_active_packet(self, packet):
        self.packet = packet
        self.packet_page.reload()

    def get_label(self):
        return self._label

    label = property(get_label)

class SessionNotebook(gtk.Notebook):
    def __init__(self):
        gtk.Notebook.__init__(self)

        self.set_show_border(False)
        self.set_scrollable(True)

        # We have a static page to manage the packets
        # selected from sniff perspective
        self.view_page = None

    def create_edit_session(self, proto_name):
        session = SessionPage(packet=proto_name)
        self.append_page(session, session.label)
        self.set_tab_reorderable(session, True)

    def create_sniff_session(self, iface, args):
        session = SessionPage(iface, args)
        self.append_page(session, session.label)
        self.set_tab_reorderable(session, True)

    def create_offline_session(self, fname):
        session = SessionPage(fname=fname)
        self.append_page(session, session.label)
        self.set_tab_reorderable(session, True)

    def get_current_session(self):
        """
        Get the current SessionPage

        @return a SessionPage instance or None
        """

        idx = self.get_current_page()
        obj = self.get_nth_page(idx)

        if obj and isinstance(obj, SessionPage):
            return obj

        return None

class MainTab(UmitView):
    tab_position = None
    label_text = "MainTab"

    def __create_widgets(self):
        "Create the widgets"
        self.vbox = gtk.VBox(False, 2)
        self.session_notebook = SessionNotebook()

    def __pack_widgets(self):
        "Pack the widgets"

        self.vbox.pack_start(self.session_notebook)

        self.session_notebook.drag_dest_set(
            gtk.DEST_DEFAULT_ALL,
            [('text/plain', 0, 0)],
            gtk.gdk.ACTION_COPY
        )

        self._main_widget.add(self.vbox)
        self._main_widget.show_all()

    def __connect_signals(self):
        self.session_notebook.connect('drag-data-received', self.__on_drag_data)

    def create_ui(self):
        "Create the ui"
        self.__create_widgets()
        self.__pack_widgets()
        self.__connect_signals()

    def get_current_session(self):
        "@returns the current SessionPage or None"
        page = self.get_current_page()

        if page and isinstance(page, SessionPage):
            return page
        return None

    def get_current_page(self):
        "@return the current page in notebook or None"

        idx = self.session_notebook.get_current_page()
        return self.session_notebook.get_nth_page(idx)

    #===========================================================================

    def __on_drag_data(self, widget, ctx, x, y, data, info, time):
        "drag-data-received callback"

        if data and data.format == 8:
            proto = data.data

            if Backend.get_proto(proto):
                self.session_notebook.create_edit_session(data.data)
                ctx.finish(True, False, time)
                return True

        ctx.finish(False, False, time)
