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
import pango
import gobject

from os import unlink
from datetime import datetime

from PM.Core.I18N import _
from PM.Core.Logger import log
from PM.Core.Atoms import strip_tags

from PM.Gui.Core.App import PMApp
from PM.Gui.Core.Icons import get_pixbuf
from PM.Gui.Pages.Base import Perspective
from PM.Gui.Widgets.FilterEntry import FilterEntry
from PM.Manager.PreferenceManager import Prefs

from PM.higwidgets.higdialogs import HIGAlertDialog

ICONS = [gtk.STOCK_DIALOG_INFO,
         gtk.STOCK_DIALOG_WARNING,
         gtk.STOCK_DIALOG_ERROR]

# To convert STATUS_* to ICONS
STATUS = (2, 2, 2, 2, 1, 1, 0, 0, 0)
STATUS_STRING = ('emerg', 'alert', 'crit', 'err', 'warn', 'notice', 'info',
                 'debug', 'none')

COL_SEV, COL_TIME, COL_FAC, COL_MSG = range(4)

class AuditOutputTree(gtk.TreeView):
    def __init__(self):
        self.store = gtk.ListStore(int, object, str, str)

        self.filter_txt = ''
        self.filter_model = self.store.filter_new()
        self.filter_model.set_visible_func(self.__filter_func)

        gtk.TreeView.__init__(self, self.filter_model)

        self.insert_column_with_data_func(-1, '', gtk.CellRendererPixbuf(),
                                          self.__pix_func)
        self.insert_column_with_attributes(-1, _('Time'),
                                           gtk.CellRendererText())
        self.insert_column_with_attributes(-1, _('Facility'),
                                           gtk.CellRendererText(), text=COL_FAC)
        self.insert_column_with_attributes(-1, _('Record'),
                                           gtk.CellRendererText(),
                                           markup=COL_MSG)

        col = self.get_column(COL_TIME)
        col.set_cell_data_func(col.get_cell_renderers()[0], self.__time_func)
        col.set_resizable(True)

        col = self.get_column(COL_FAC)
        col.set_resizable(True)

        rend = col.get_cell_renderers()[0]
        rend.set_property('weight', pango.WEIGHT_BOLD)

        col = self.get_column(COL_MSG)
        col.set_expand(True)
        col.set_resizable(True)

        self.set_rules_hint(True)
        #self.set_headers_visible(False)
        self.set_rubber_banding(True)

        sel = self.get_selection()
        sel.set_mode(gtk.SELECTION_MULTIPLE)

        self.menu = gtk.Menu()

        for name, label, tooltip, stock, callback in (
            ('copy', _('Copy selected rows'),
             _('Copy selected rows into the clipboard'), gtk.STOCK_COPY,
             (self.__on_copy, )),
            ('savesel', _('Save selected rows'),
             _('Save selected rows into a log file'), gtk.STOCK_SAVE,
             (self.on_save_log, True))
        ):
            action = gtk.Action(name, label, tooltip, stock)
            action.connect('activate', *callback)
            item = action.create_menu_item()
            item.show()

            self.menu.append(item)

        self.time_format = None

        Prefs()['gui.maintab.auditoutputview.timeformat'].connect(
            self.__on_time_format_changed, True
        )
        Prefs()['gui.maintab.auditoutputview.font'].connect(
            self.__on_font_changed, True
        )

        self.connect('button-press-event', self.__on_button_press)

    def __time_func(self, col, cell, model, iter):
        value = model.get_value(iter, 1)

        if self.time_format:
            try:
                cell.set_property('text', value.strftime(self.time_format))
                return
            except Exception, err:
                pass

        cell.set_property('text', str(value))

    def __on_time_format_changed(self, value):
        self.time_format = value

        def update(model, path, iter):
            model.row_changed(path, iter)

        self.store.foreach(update)

    def __on_font_changed(self, value):
        self.modify_font(pango.FontDescription(value))

    def __pix_func(self, col, cell, model, iter):
        value = model.get_value(iter, 0)
        cell.set_property('stock-id', ICONS[STATUS[value]])

    def user_msg(self, msg, severity=5, facility=None):
        self.store.append([severity, datetime.now(), facility, msg])

    def on_save_log(self, action, selection=False):
        if selection:
            model, rows = self.get_selection().get_selected_rows()

            if not rows:
                return

        dialog = gtk.FileChooserDialog(_('Save log file'), PMApp().main_window,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_SAVE, gtk.RESPONSE_ACCEPT,
                                        gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))

        afilter = gtk.FileFilter()
        afilter.add_pattern('*.txt')
        afilter.add_pattern('*.log')
        afilter.add_mime_type('text/plain')
        afilter.set_name('ASCII log file')

        dialog.add_filter(afilter)

        xfilter = gtk.FileFilter()
        xfilter.add_pattern('*.xml')
        xfilter.add_mime_type('text/html')
        xfilter.set_name('XML log file')

        dialog.add_filter(xfilter)

        if dialog.run() == gtk.RESPONSE_ACCEPT:
            outname = dialog.get_filename()
            type = (dialog.get_filter() is xfilter and 1 or 0)

            try:
                f = open(outname, 'w')

                if type == 1:
                    f.write('<?xml version="1.0"?>\n<auditlog>\n')
                    sep = ' '
                else:
                    sep = ''

                if selection:
                    for path in rows:
                        iter = model.get_iter(path)
                        f.write(sep + \
                                self.get_row_txt(model, iter, type) + \
                                '\n')
                else:
                    def dump(model, path, iter, f):
                        f.write(sep + \
                                self.get_row_txt(model, iter, type) + \
                                '\n')

                    self.store.foreach(dump, f)

                if type == 1:
                    f.write('</auditlog>\n')

                f.close()

            except Exception, err:
                try:
                    unlink(outname)
                except:
                    pass

                d = HIGAlertDialog(PMApp().main_window, gtk.DIALOG_MODAL,
                                   gtk.MESSAGE_ERROR,
                                   message_format=_('Error while saving log '
                                                    'file to %s') % outname,
                                   secondary_text=str(err))
                d.run()
                d.hide()
                d.destroy()

        dialog.hide()
        dialog.destroy()

    def __on_copy(self, action):
        sel = self.get_selection()
        model, rows = sel.get_selected_rows()

        out = ''

        for path in rows:
            out += self.get_row_txt(model, model.get_iter(path))

        gtk.clipboard_get().set_text(out)

    def get_row_txt(self, model, iter, type=0):
        svrtid = model.get_value(iter, COL_SEV)
        datetm = model.get_value(iter, COL_TIME)
        facili = model.get_value(iter, COL_FAC)
        logmsg = model.get_value(iter, COL_MSG)

        datetm = str(datetm)

        if type == 0: # simple text
            logmsg = strip_tags(logmsg)

            if facili:
                svrtid = facili + '.' + STATUS_STRING[svrtid]
            else:
                svrtid = STATUS_STRING[svrtid]

            return ' '.join((datetm, svrtid, logmsg))

        if type == 1: # xml
            out = '<logrecord time="' + datetm + '" '

            if facili:
                out += 'facility="' + facili + '" '

            out += 'severity="' + str(svrtid) + '">' + logmsg + '</logrecord>'

            return out

    def __on_button_press(self, widget, evt):
        if evt.button != 3:
            return

        sel = self.get_selection()
        model, rows = sel.get_selected_rows()

        if not rows:
            return

        self.menu.popup(None, None, None, evt.button, evt.time)

    def __filter_func(self, model, iter):
        if not self.filter_txt:
            return True

        facility = model.get_value(iter, COL_FAC)

        if self.filter_txt in facility:
            return True

        msg = strip_tags(model.get_value(iter, COL_MSG))

        if self.filter_txt in msg:
            return True

        return False

    def filter(self, txt):
        self.filter_txt = txt or ''
        self.filter_model.refilter()

class AuditOutput(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self, False, 2)

        self.entry = FilterEntry()
        self.tree = AuditOutputTree()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.add(self.tree)

        self.toolbar = gtk.Toolbar()
        self.toolbar.set_style(gtk.TOOLBAR_ICONS)

        action = gtk.Action('save', _('Save log'),
                            _('Save log to file'), gtk.STOCK_SAVE)
        action.connect('activate', self.tree.on_save_log)

        item = action.create_tool_item()
        self.toolbar.insert(item, -1)

        item = gtk.ToolItem()
        item.add(self.entry)
        item.set_expand(True)

        self.toolbar.insert(item, -1)

        self.pack_start(self.toolbar, False, False)
        self.pack_end(sw)

        self.entry.get_entry().connect('changed', self.__on_filter)

    def __on_filter(self, widget):
        self.tree.filter(widget.get_text())

class AuditOutputPage(Perspective):
    icon = gtk.STOCK_INDEX
    title = _('Audit status')

    def create_ui(self):
        self.output = AuditOutput()
        self.user_msg(_('<tt>New audit started at <i>%s</i></tt>') \
                      % str(datetime.now()),
                      8, 'AuditManager')

        self.pack_start(self.output)
        self.show_all()

    def user_msg(self, msg, severity=5, facility=None):
        "wrapper to simplify the code"
        self.output.tree.user_msg(msg, severity, facility)
