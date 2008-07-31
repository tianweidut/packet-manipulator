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
import gobject

from gtk import gdk
from higwidgets.higbuttons import HIGArrowButton

#
# Reimplementation of gtk.Layout in python
# Example on how to implement a scrollable container in python
#
# Johan Dahlin <johan@gnome.org>, 2006
#
# Readaption for implementing show/hide animation and only one child by
# Francesco Piccinno <stack.box@gmail.com>, 2008
#
# Requires PyGTK 2.8.0 or later

class Child:
    widget = None
    x = 0
    y = 0

def set_adjustment_upper(adj, upper, always_emit):
    changed = False
    value_changed = False

    min = max(0.0, upper - adj.page_size)

    if upper != adj.upper:
        adj.upper = upper
        changed = True

    if adj.value > min:
        adj.value = min
        value_changed = True

    if changed or always_emit:
        adj.changed()
    if value_changed:
        adj.value_changed()

def new_adj():
    return gtk.Adjustment(0.0, 0.0, 0.0,
                          0.0, 0.0, 0.0)

class Layout(gtk.Container):
    __gsignals__ = {
        'animation-end' : (gobject.SIGNAL_RUN_LAST, None, (gobject.TYPE_BOOLEAN, )),
        'set_scroll_adjustments' : (gobject.SIGNAL_RUN_LAST, None,
                                   (gtk.Adjustment, gtk.Adjustment))
    }

    def __init__(self):
        self._child = None
        self._width = 100
        self._height = 100
        self._hadj = None
        self._vadj = None
        self._bin_window = None
        self._hadj_changed_id = -1
        self._vadj_changed_id = -1

        self._animating = False
        self._to_show = True

        self._current = 0
        self._dest = 0
        self._speed = 5

        self._time_int = 10
        self._time_tot = 300

        gtk.Container.__init__(self)

        if not self._hadj or not self._vadj:
            self._set_adjustments(self._vadj or new_adj(),
                                  self._hadj or new_adj())

    def _move(self, x=0, y=0):
        if not self._child:
            return

        if x != self._child.x or \
           y != self._child.y:

            self._child.x = x
            self._child.y = y

            self.queue_resize()

    def set_size(self, width, height):
        if self._width != width:
            self._width = width
        if self._height != height:
            self._height = height
        if self._hadj:
            set_adjustment_upper(self._hadj, self._width, False)
        if self._vadj:
            set_adjustment_upper(self._vadj, self._height, False)

        if self.flags() & gtk.REALIZED:
            self._bin_window.resize(max(width, self.allocation.width),
                                    max(height, self.allocation.height))

    def do_realize(self):
        self.set_flags(self.flags() | gtk.REALIZED)

        self.window = gdk.Window(
            self.get_parent_window(),
            window_type=gdk.WINDOW_CHILD,
            x=self.allocation.x,
            y=self.allocation.y,
            width=self.allocation.width,
            height=self.allocation.height,
            wclass=gdk.INPUT_OUTPUT,
            colormap=self.get_colormap(),
            event_mask=gdk.VISIBILITY_NOTIFY_MASK)
        self.window.set_user_data(self)

        self._bin_window = gdk.Window(
            self.window,
            window_type=gdk.WINDOW_CHILD,
            x=int(-self._hadj.value),
            y=int(-self._vadj.value),
            width=max(self._width, self.allocation.width),
            height=max(self._height, self.allocation.height),
            colormap=self.get_colormap(),
            wclass=gdk.INPUT_OUTPUT,
            event_mask=(self.get_events() | gdk.EXPOSURE_MASK |
                        gdk.SCROLL_MASK))
        self._bin_window.set_user_data(self)

        self.set_style(self.style.attach(self.window))
        self.style.set_background(self.window, gtk.STATE_NORMAL)
        self.style.set_background(self._bin_window, gtk.STATE_NORMAL)

        if self._child:
            self._child.widget.set_parent_window(self._bin_window)

        self.queue_resize()

    def do_unrealize(self):
        self._bin_window.set_user_data(None)
        self._bin_window.destroy()
        self._bin_window = None
        gtk.Container.do_unrealize(self)

    def _do_style_set(self, style):
        gtk.Widget.do_style_set(self, style)

        if self.flags() & gtk.REALIZED:
            self.style.set_background(self._bin_window, gtk.STATE_NORMAL)

    def do_expose_event(self, event):
        if event.window != self._bin_window:
            return False

        gtk.Container.do_expose_event(self, event)

        return False

    def do_map(self):
        self.set_flags(self.flags() | gtk.MAPPED)

        if self._child:
            flags = self._child.widget.flags()

            if flags & gtk.VISIBLE and not (flags & gtk.MAPPED):
                self._child.widget.map()

        self._bin_window.show()
        self.window.show()

    def do_size_request(self, req):
        req.width = 0
        req.height = 0

        if self._child and (self._animating or self._to_show):
        #if self._child:
            req.width, req.height = self._child.widget.size_request()

    def do_size_allocate(self, allocation):
        self.allocation = allocation

        if self._child:
            rect = gdk.Rectangle(self._child.x, self._child.y,
                                 allocation.width, allocation.height)
            self._child.widget.size_allocate(rect)

        if self.flags() & gtk.REALIZED:
            self.window.move_resize(*allocation)
            self._bin_window.resize(max(self._width, allocation.width),
                                    max(self._height, allocation.height))

        self._hadj.page_size = allocation.width
        self._hadj.page_increment = allocation.width * 0.9
        self._hadj.lower = 0
        set_adjustment_upper(self._hadj,
                             max(allocation.width, self._width), True)

        self._vadj.page_size = allocation.height
        self._vadj.page_increment = allocation.height * 0.9
        self._vadj.lower = 0
        self._vadj.upper = max(allocation.height, self._height)
        set_adjustment_upper(self._vadj,
                             max(allocation.height, self._height), True)

    def do_set_scroll_adjustments(self, hadj, vadj):
        self._set_adjustments(hadj, vadj)

    def do_forall(self, include_internals, callback, data):
        if self._child:
            callback(self._child.widget, data)

    def do_add(self, widget):
        if self._child:
            raise AttributeError

        child = Child()
        child.widget = widget
        child.x, child.y = 0, 0

        self._child = child

        if self.flags() & gtk.REALIZED:
            widget.set_parent_window(self._bin_window)

        widget.set_parent(self)

    def do_remove(self, widget):
        if self._animating:
            raise Exception("Try later please :)")

        if self._child and self._child.widget == widget:
            self._child = None
            widget.unparent()
        else:
            raise AttributeError

    # Private

    def _set_adjustments(self, hadj, vadj):
        if not hadj and self._hadj:
            hadj = new_adj()

        if not vadj and self._vadj:
            vadj = new_adj()

        if self._hadj and self._hadj != hadj:
            self._hadj.disconnect(self._hadj_changed_id)

        if self._vadj and self._vadj != vadj:
            self._vadj.disconnect(self._vadj_changed_id)

        need_adjust = False

        if self._hadj != hadj:
            self._hadj = hadj
            set_adjustment_upper(hadj, self._width, False)
            self._hadj_changed_id = hadj.connect(
                "value-changed",
                self._adjustment_changed)
            need_adjust = True

        if self._vadj != vadj:
            self._vadj = vadj
            set_adjustment_upper(vadj, self._height, False)
            self._vadj_changed_id = vadj.connect(
                "value-changed",
                self._adjustment_changed)
            need_adjust = True

        if need_adjust and vadj and hadj:
            self._adjustment_changed()

    def _adjustment_changed(self, adj=None):
        if self.flags() & gtk.REALIZED:
            self._bin_window.move(int(-self._hadj.value),
                                  int(-self._vadj.value))
            self._bin_window.process_updates(True)

    def _do_animation(self):
        if not self._child:
            return False

        if not self._child.widget.flags() & gtk.VISIBLE:
            self._child.widget.show()

        if self._to_show:
            if self._current < 0:
                self._current += self._speed
                self._move(0, self._current)

                return True

            self._current = 0
            self._move(0, self._current)
        else:
            if self._current > self._dest:
                self._current -= self._speed
                self._move(0, self._current)

                return True

            self._current = -self.allocation.height
            self._move(0, self._current)

            self.hide()

        self.emit('animation-end', self._to_show)
        self._child.widget.set_sensitive(True)
        return False

    def toggle_animation(self):
        if self._animating or not self._child:
            return False

        self._to_show = not self._to_show
        self._speed = max(self.allocation.height / (self._time_tot / self._time_int), 1)
        self._child.widget.set_sensitive(False)

        if self._to_show:
            self.show()
            self.set_size_request(-1, -1)
            self._dest = 0
        else:
            self.set_size_request(0, 0)
            self._dest = -self.allocation.height

        gobject.timeout_add(self._time_int, self._do_animation)

        return True

Layout.set_set_scroll_adjustments_signal('set-scroll-adjustments')

class AnimatedExpander(gtk.VBox):
    __gtype_name__ = "AnimatedExpander"
    
    def __init__(self, label=None, image=gtk.STOCK_PROPERTIES):
        super(AnimatedExpander, self).__init__(False, 2)
        
        # What we need is the arrow button a label with markup and
        # optionally a close button :)
        
        self._arrow = HIGArrowButton(gtk.ORIENTATION_VERTICAL)
        self._arrow.set_relief(gtk.RELIEF_NONE)
        self._arrow.connect('clicked', self.__on_toggle)
        
        self._label = gtk.Label()
        self._label.set_alignment(0, 0.5)
        self.label = label
        
        self._image = gtk.Image()
        self.image = image
        
        # The layout part
        self._layout = Layout()
        
        # Pack all
        hbox = gtk.HBox(False, 2)
        hbox.pack_start(self._arrow, False, False)
        hbox.pack_start(self._image, False, False)
        hbox.pack_start(self._label)
        
        frame = gtk.Frame()
        frame.add(hbox)
        
        self._happy_box = gtk.EventBox()
        self._happy_box.add(frame)
        
        self.pack_start(self._happy_box, False, False)
        self.pack_start(self._layout)
        
        self.show_all()

    def do_realize(self):
        gtk.VBox.do_realize(self)

        bg_color = gtk.gdk.color_parse("#FFFFDC")
        gtk.gdk.colormap_get_system().alloc_color(bg_color)

        self._happy_box.modify_bg(gtk.STATE_NORMAL, bg_color)

    def add_widget(self, widget, show=False):
        """
        Add a widget to the expander.

        @param widget the widget to add
        @param show if the widget should be showed
        """

        #FIXME: this
        self._layout.add(widget)

    def add(self, widget):
        self.add_widget(widget, True)

    def get_label(self):
        return self._label.get_text()

    def set_label(self, txt):
        if not txt:
            txt = ""

        self._label.set_text(txt)
        self._label.set_use_markup(True)

    def __on_toggle(self, btn):
        if self._layout.toggle_animation():
            self._arrow.set_active(not self._arrow.get_active())
    
    def get_image(self):
        return self._image
    
    def set_image(self, stock):
        self._image.set_from_stock(stock, gtk.ICON_SIZE_BUTTON)

    label = property(get_label, set_label)
    image = property(get_image, set_image)

gobject.type_register(AnimatedExpander)

class ToolPage(AnimatedExpander):
    def __init__(self, parent, label=None, image=gtk.STOCK_PROPERTIES):
        super(ToolPage, self).__init__(label, image)

        self._parent = parent
        self._active = False

        self._layout.connect('animation-end', lambda w, v: self.set_active(v))

    def get_active(self):
        return self._active

    def set_active(self, val):
        self._active = val
        self._parent.realloc(self)

class ToolBox(gtk.VBox):
    def __init__(self):
        super(ToolBox, self).__init__(False, 2)
        self.set_border_width(4)

        self._active_page = None
        self._pages = []

    def append_page(self, child, txt):
        page = ToolPage(self, txt)
        page.add(child)

        self._pages.append(page)


        self._active_page = page
        self.pack_start(page, True, True)

    def realloc(self, page):
        if page.get_active():
            self.set_child_packing(page, True, True, 0, gtk.PACK_START)

            if self._active_page:
                self._active_page.set_active(False)
                self._active_page = page
        else:
            self.set_child_packing(page, False, False, 0, gtk.PACK_START)

def main(klass):
    w = gtk.Window()
    vbox = gtk.VBox()

    sw = gtk.ScrolledWindow()
    sw.add(gtk.TextView())
    sw.set_size_request(400, 400)
    
    exp = klass("miao")
    exp.add(sw)

    vbox.pack_start(exp, False, False)

    sw = gtk.ScrolledWindow()
    sw.add(gtk.TextView())
    
    exp = klass("miao")
    exp.add(sw)
    vbox.pack_start(exp)

    vbox.pack_start(gtk.Label("mias"), False, False)
    w.add(vbox)
    w.show_all()

def toolbox():
    w = gtk.Window()
    box = ToolBox()
    box.append_page(gtk.Label("Testing"), "miao")
    box.append_page(gtk.Label("Testing"), "miao")
    w.add(box)
    w.show_all()

if __name__ == "__main__":
    #main(AnimatedExpander)
    #main(gtk.Expander)
    toolbox()
    gtk.main()
