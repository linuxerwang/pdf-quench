#! /usr/bin/python
# -*- coding: utf-8 -*-

"""

 Pdf-Quench 1.0.0 - A visual tool for cropping pdf files.
 Copyright (C) 2011 Zhong Wang
 <https://code.google.com/p/pdf-quench/>

 This program is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License along
 with this program; if not, write to the Free Software Foundation, Inc.,
 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GooCanvas', '2.0')
gi.require_version('Poppler', '0.18')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
import cairo
from gi.repository import Gtk, GooCanvas, Pango, Poppler, Gdk, GdkPixbuf
from collections import namedtuple
import os
import sys

# Temporary workaround to avoid the "maximum recursion depth exceeded" error.
sys.setrecursionlimit(65536)

sys.path.append('/usr/share/pdf-quench')
from PyPDF2 import PdfFileWriter, PdfFileReader


VERSION = '1.0.2'
LAST_OPEN_FOLDER   = None
NEXT_INDEX = 0
CROP_SETTING_NAMES = set(['x', 'y', 'w', 'h'])
ZOOM_LEVELS = (0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
DEFAULT_ZOOM_LEVEL = 3


def next_index():
  global NEXT_INDEX
  index = NEXT_INDEX
  NEXT_INDEX += 1
  return index


class CropSetting(object):
  def __init__(self, parent=None):
    self.__parent = parent
    self.__params = {}


  def __getitem__(self, name):
    if name in CROP_SETTING_NAMES:
      return self.__params[name]
    else:
      raise KeyError()


  def __setitem__(self, name, value):
    if name in CROP_SETTING_NAMES:
      self.__params[name] = value
    else:
      raise KeyError()


  def empty(self):
    return len(self.__params) == 0


  def __get_effective_crop_setting(self):
    if self.__params:
      return self
    elif self.__parent:
      return self.__parent.__get_effective_crop_setting()
    else:
      return self

  effective_crop_setting = property(__get_effective_crop_setting)


  def __get_parent_crop_setting(self):
    return self.__parent

  parent_crop_setting = property(__get_parent_crop_setting)


class PageInfo(object):
  def __init__(self, pagenum, crop_setting, size):
    self.__pagenum = pagenum
    self.__crop_setting = crop_setting
    self.__deleted = False
    self.__poppler_size = size


  @property
  def pagenum(self):
    return self.__pagenum

  @property
  def crop_setting(self):
    return self.__crop_setting

  @property
  def deleted(self):
    return self.__deleted

  @property
  def size(self):
    return self.__poppler_size


class Resizer(GooCanvas.CanvasEllipse):
  def __init__(self, parent, rect, x, y):
    self._rect = rect
    GooCanvas.CanvasEllipse.__init__(self,
                                     parent=parent,
                                     center_x=x,
                                     center_y=y,
                                     radius_x=5,
                                     radius_y=5,
                                     stroke_color="red",
                                     fill_color="blue",
                                     line_width=1.0)
    self.connect("motion_notify_event", self.__on_motion_notify)
    self.connect("button_press_event", self.__on_button_press)
    self.connect("button_release_event", self.__on_button_release)
    self.connect("enter_notify_event", self.__on_mouse_enter)
    self.connect("leave_notify_event", self.__on_mouse_leave)
    self.__dragging = False
    self._cursor = None
    self._dx_listeners = []
    self._dx2_listeners = []
    self._dy_listeners = []
    self._dy2_listeners = []
    self._dxdy_listeners = []
    self._dx2dy_listeners = []
    self._dxdy2_listeners = []


  def set_listeners(self,
                    dx_listeners=[],
                    dx2_listeners=[],
                    dy_listeners=[],
                    dy2_listeners=[],
                    dx2dy_listeners=[],
                    dxdy2_listeners=[]):
    self._dx_listeners.extend(dx_listeners)
    self._dx2_listeners.extend(dx2_listeners)
    self._dy_listeners.extend(dy_listeners)
    self._dy2_listeners.extend(dy2_listeners)
    self._dx2dy_listeners.extend(dx2dy_listeners)
    self._dxdy2_listeners.extend(dxdy2_listeners)


  def __on_motion_notify(self, item, target, event):
    if self.__dragging and (event.state & Gdk.ModifierType.BUTTON1_MASK):
      # don't allow it move out of page
      bound = item.get_canvas().page_region
      if (event.x < bound.x or
          event.y < bound.y or
          event.x > bound.x + bound.width or
          event.y > bound.y + bound.height):
        return True

      x = self._rect.get_property('x')
      y = self._rect.get_property('y')
      w = self._rect.get_property('width')
      h = self._rect.get_property('height')
      dx = event.x - self.__drag_x
      dy = event.y - self.__drag_y
      if self._sync_to_cropping_box(x, y, w, h, dx, dy):
        for listener in self._dx_listeners:
          listener.props.x = listener.props.x + dx
        for listener in self._dx2_listeners:
          listener.props.x = listener.props.x + dx/2.0
        for listener in self._dy_listeners:
          listener.props.y = listener.props.y + dy
        for listener in self._dy2_listeners:
          listener.props.y = listener.props.y + dy/2.0
        for listener in self._dxdy_listeners:
          listener.props.x = listener.props.x + dx
          listener.props.y = listener.props.y + dy
        for listener in self._dx2dy_listeners:
          listener.props.x = listener.props.x + dx/2.0
          listener.props.y = listener.props.y + dy
        for listener in self._dxdy2_listeners:
          listener.props.x = listener.props.x + dx
          listener.props.y = listener.props.y + dy/2.0
      self.__drag_x = event.x
      self.__drag_y = event.y

    return True


  def __on_button_press(self, item, target, event):
    if event.button == 1:
      self.__drag_x = event.x
      self.__drag_y = event.y
      item.get_canvas().pointer_grab(
          item,
          Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK,
          self._cursor,
          event.time)
      self.__dragging = True

    return True


  def __on_button_release(self, item, target, event):
    canvas = item.get_canvas()
    canvas.pointer_ungrab(item, event.time)
    page_info = canvas.page_info
    crop_setting = page_info.crop_setting.effective_crop_setting
    crop_setting['x'] = self._rect.props.x
    crop_setting['y'] = self._rect.props.y
    crop_setting['w'] = self._rect.props.width
    crop_setting['h'] = self._rect.props.height
    self.__dragging = False


  def __on_mouse_enter(self, item, target, event):
    item.get_canvas().get_window().set_cursor(self._cursor)


  def __on_mouse_leave(self, item, target, event):
    item.get_canvas().get_window().set_cursor(None)


class UResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dy_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.TOP_SIDE)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', (x0 + x1) / 2.0)
    self.set_property('center-y', y0)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    hh = h - dy
    if hh > 50 or hh > h:
      self._rect.set_property('y', y + dy)
      self._rect.set_property('height', hh)
      return True

    return False


class RResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dx_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.RIGHT_SIDE)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', x1)
    self.set_property('center-y', (y0 + y1) / 2.0)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    ww = w + dx
    if ww > 50 or ww > w:
      self._rect.set_property('width', ww)
      return True

    return False


class BResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dy_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.BOTTOM_SIDE)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', (x0 + x1) / 2.0)
    self.set_property('center-y', y1)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    hh = h + dy
    if hh > 50 or hh > h:
      self._rect.set_property('height', hh)
      return True

    return False


class LResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dx_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.LEFT_SIDE)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', x0)
    self.set_property('center-y', (y0 + y1) / 2.0)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    ww = w - dx
    if ww > 50 or ww > w:
      self._rect.set_property('x', x + dx)
      self._rect.set_property('width', ww)
      return True

    return False


class ULResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dxdy_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.TOP_LEFT_CORNER)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', x0)
    self.set_property('center-y', y0)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    ww = w - dx
    hh = h - dy
    if (ww > 50 or ww > w) and (hh > 50 or hh > h):
      self._rect.set_property('x', x + dx)
      self._rect.set_property('y', y + dy)
      self._rect.set_property('width', ww)
      self._rect.set_property('height', hh)
      return True

    return False


class URResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dxdy_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.TOP_RIGHT_CORNER)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', x1)
    self.set_property('center-y', y0)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    ww = w + dx
    hh = h - dy
    if (ww > 50 or ww > w) and (hh > 50 or hh > h):
      self._rect.set_property('y', y + dy)
      self._rect.set_property('width', ww)
      self._rect.set_property('height', hh)
      return True

    return False


class BLResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dxdy_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.BOTTOM_LEFT_CORNER)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', x0)
    self.set_property('center-y', y1)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    ww = w - dx
    hh = h + dy
    if (ww > 50 or ww > w) and (hh > 50 or hh > h):
      self._rect.set_property('x', x + dx)
      self._rect.set_property('width', ww)
      self._rect.set_property('height', hh)
      return True

    return False


class BRResizer(Resizer):
  def __init__(self, parent, rect, x, y):
    Resizer.__init__(self, parent, rect, x, y)
    self._dxdy_listeners.append(self)
    self._cursor = Gdk.Cursor(Gdk.CursorType.BOTTOM_RIGHT_CORNER)


  def sync_from_cropping_box(self, x0, y0, x1, y1):
    self.set_property('center-x', x1)
    self.set_property('center-y', y1)


  def _sync_to_cropping_box(self, x, y, w, h, dx, dy):
    ww = w + dx
    hh = h + dy
    if (ww > 50 or ww > w) and (hh > 50 or hh > h):
      self._rect.set_property('width', ww)
      self._rect.set_property('height', hh)
      return True

    return False


class CroppingBox(GooCanvas.CanvasGroup):
  def __init__(self, parent, x, y, w, h, stroke=0x66CCFF55, fill=0xFFEECC66):
    self.__dragging = False
    self.__drag_x = None
    self.__drag_y = None
    GooCanvas.CanvasGroup.__init__(self, parent=parent)
    self.__rect = GooCanvas.CanvasRect(
        parent=self,
        x=x, y=y, width=w, height=h,
        stroke_color_rgba=stroke,
        fill_color_rgba=fill,
        line_width=2.0)
    self.connect("motion_notify_event", self.__on_motion_notify)
    self.connect("button_press_event", self.__on_button_press)
    self.connect("button_release_event", self.__on_button_release)
    self.__resizers = [
      UResizer(self, self.__rect, x + w/2.0, y),
      RResizer(self, self.__rect, x + w, y + h/2.0),
      BResizer(self, self.__rect, x + w/2.0, y + h),
      LResizer(self, self.__rect, x, y + h/2.0),
      ULResizer(self, self.__rect, x, y),
      URResizer(self, self.__rect, x + w, y),
      BRResizer(self, self.__rect, x + w, y + h),
      BLResizer(self, self.__rect, x, y + h),
    ]
    self.__resizers[0].set_listeners(
        dy_listeners=[self.__resizers[i] for i in (4, 5)],
        dy2_listeners=[self.__resizers[i] for i in (1, 3)])
    self.__resizers[1].set_listeners(
        dx_listeners=[self.__resizers[i] for i in (5, 6)],
        dx2_listeners=[self.__resizers[i] for i in (0, 2)])
    self.__resizers[2].set_listeners(
        dy_listeners=[self.__resizers[i] for i in (6, 7)],
        dy2_listeners=[self.__resizers[i] for i in (1, 3)])
    self.__resizers[3].set_listeners(
        dx_listeners=[self.__resizers[i] for i in (4, 7)],
        dx2_listeners=[self.__resizers[i] for i in (0, 2)])
    self.__resizers[4].set_listeners(
        dx_listeners=[self.__resizers[7]],
        dx2_listeners=[self.__resizers[2]],
        dy_listeners=[self.__resizers[5]],
        dy2_listeners=[self.__resizers[1]],
        dx2dy_listeners=[self.__resizers[0]],
        dxdy2_listeners=[self.__resizers[3]])
    self.__resizers[5].set_listeners(
        dx_listeners=[self.__resizers[6]],
        dx2_listeners=[self.__resizers[2]],
        dy_listeners=[self.__resizers[4]],
        dy2_listeners=[self.__resizers[3]],
        dx2dy_listeners=[self.__resizers[0]],
        dxdy2_listeners=[self.__resizers[1]])
    self.__resizers[6].set_listeners(
        dx_listeners=[self.__resizers[5]],
        dx2_listeners=[self.__resizers[0]],
        dy_listeners=[self.__resizers[7]],
        dy2_listeners=[self.__resizers[3]],
        dx2dy_listeners=[self.__resizers[2]],
        dxdy2_listeners=[self.__resizers[1]])
    self.__resizers[7].set_listeners(
        dx_listeners=[self.__resizers[4]],
        dx2_listeners=[self.__resizers[0]],
        dy_listeners=[self.__resizers[6]],
        dy2_listeners=[self.__resizers[1]],
        dx2dy_listeners=[self.__resizers[2]],
        dxdy2_listeners=[self.__resizers[3]])


  def __on_motion_notify(self, item, target, event):
    if self.__dragging and (event.state & Gdk.ModifierType.BUTTON1_MASK):
      # don't allow it move out of page
      bound = item.get_canvas().page_region
      if (event.x < bound.x or
          event.y < bound.y or
          event.x > bound.x + bound.width or
          event.y > bound.y + bound.height):
        return True

      dx = event.x - self.__drag_x
      dy = event.y - self.__drag_y
      self.__rect.props.x = self.__rect.props.x + dx
      self.__rect.props.y = self.__rect.props.y + dy
      for resizer in self.__resizers:
        resizer.props.x = resizer.props.x + dx
        resizer.props.y = resizer.props.y + dy
      self.__drag_x = event.x
      self.__drag_y = event.y
      page_info = item.get_canvas().page_info
      crop_setting = page_info.crop_setting.effective_crop_setting
      crop_setting['x'] = self.__rect.props.x
      crop_setting['y'] = self.__rect.props.y
      crop_setting['w'] = self.__rect.props.width
      crop_setting['h'] = self.__rect.props.height

    return True


  def __on_button_press(self, item, target, event):
    if event.button == 1:
      self.__drag_x = event.x
      self.__drag_y = event.y

      fleur = Gdk.Cursor(Gdk.CursorType.FLEUR)
      item.get_canvas().pointer_grab(
          item,
          Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK,
          fleur,
          event.time)
      self.__dragging = True

    return True


  def __on_button_release(self, item, target, event):
    if event.button == 1:
      item.get_canvas().pointer_ungrab(item, event.time)
      self.__dragging = False
    return True


  def update(self):
    page_info = self.get_canvas().page_info
    crop_setting = page_info.crop_setting.effective_crop_setting
    if not crop_setting.empty():
      x, y, w, h = (crop_setting['x'],
                    crop_setting['y'],
                    crop_setting['w'],
                    crop_setting['h'])
      self.__rect.set_property('x', x)
      self.__rect.set_property('y', y)
      self.__rect.set_property('width', w)
      self.__rect.set_property('height', h)
      for resizer in self.__resizers:
        resizer.sync_from_cropping_box(x, y, x+w, y+h)


class PdfView(GooCanvas.CanvasImage):
  def __init__(self,):
    self.__cropping_box = None
    self.__dragging = False
    self.__start_x = None
    self.__start_y = None
    self.__rubberband = None
    GooCanvas.CanvasImage.__init__(self, pixbuf=None, x=0, y=0)
    self.connect("motion_notify_event", self.__on_motion_notify)
    self.connect("button_press_event", self.__on_button_press)
    self.connect("button_release_event", self.__on_button_release)


  def __on_motion_notify(self, item, target, event):
    if self.__dragging:
      # don't allow it move out of page
      bound = item.get_canvas().page_region
      if (event.x < bound.x or
          event.y < bound.y or
          event.x > bound.x + bound.width or
          event.y > bound.y + bound.height):
        return True

      if event.x > self.__start_x:
        self.__rubberband.props.width = event.x - self.__start_x
      else:
        self.__rubberband.props.x = event.x
        self.__rubberband.props.width = self.__start_x - event.x

      if event.y > self.__start_y:
        self.__rubberband.props.height = event.y - self.__start_y
      else:
        self.__rubberband.props.y = event.y
        self.__rubberband.props.height = self.__start_y - event.y

    return True


  def __on_button_press(self, item, target, event):
    if event.button == 1 and not self.__cropping_box:
      canvas = item.get_canvas()
      self.__dragging = True
      self.__start_x = event.x
      self.__start_y = event.y
      self.__rubberband = GooCanvas.CanvasRect(
          x=event.x, y=event.y, width=0, height=0,
          stroke_color_rgba=0x66CCFF55,
          fill_color_rgba=0xFFEECC66,
          line_width=2.0)
      canvas.get_root_item().add_child(self.__rubberband, next_index())
      fleur = Gdk.Cursor(Gdk.CursorType.FLEUR)
      canvas.pointer_grab(
          item,
          Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK,
          fleur,
          event.time)

    return True


  def __on_button_release(self, item, target, event):
    if event.button == 1 and self.__dragging:
      self.__dragging = False
      canvas = item.get_canvas()
      canvas.pointer_ungrab(item, event.time)
      x, y, w, h = (self.__rubberband.props.x,
                    self.__rubberband.props.y,
                    self.__rubberband.props.width,
                    self.__rubberband.props.height)
      self.__rubberband.remove()

      if w < 10:
        w = 10
      if h < 10:
        h = 10

      page_info = canvas.page_info
      crop_setting = page_info.crop_setting.effective_crop_setting
      crop_setting['x'] = x
      crop_setting['y'] = y
      crop_setting['w'] = w
      crop_setting['h'] = h
      self.__cropping_box = CroppingBox(canvas.get_root_item(), x, y, w, h)

    return True


  def redraw(self, page_info=None, pixbuf=None):
    if pixbuf:
      self.get_canvas().page_info = page_info
      self.props.pixbuf = pixbuf
      if self.__cropping_box:
        self.__cropping_box.update()
    else:
      self.props.pixbuf = None


class MainWindow(Gtk.Window):
  def __init__(self):
    Gtk.Window.__init__(self, title='PDF Quench {}'.format(VERSION))
    self.set_title('PDF Quench %s' % VERSION)
    self.set_default_size(900, 800)
    self.connect('delete_event', self.__on_delete_window)

    vbox = Gtk.VBox()
    self.add(vbox)

    # toolbar
    toolbar = Gtk.Toolbar()
    buttons = (
        (Gtk.ToolButton.new(Gtk.Image.new_from_icon_name("document-open",
                                                         Gtk.IconSize.SMALL_TOOLBAR)),
         self.__open_btn_clicked, 'Open'),
        (Gtk.ToolButton.new(Gtk.Image.new_from_icon_name("document-save",
                                                         Gtk.IconSize.SMALL_TOOLBAR)),
         self.__save_btn_clicked, 'Save'),
        (Gtk.ToolButton.new(Gtk.Image.new_from_icon_name("zoom-in",
                                                         Gtk.IconSize.SMALL_TOOLBAR)),
         self.__on_zoom_in_btn_clicked,
         'Zoom In'),
        (Gtk.ToolButton.new(Gtk.Image.new_from_icon_name("zoom-out",
                                                         Gtk.IconSize.SMALL_TOOLBAR)),
         self.__on_zoom_out_btn_clicked,
         'Zoom Out'),
    )
    for button, callback, tooltip in buttons:
      button.set_tooltip_text(tooltip)
      button.connect_after('clicked', callback)
      toolbar.insert(button, -1)
    vbox.pack_start(toolbar, expand=False, fill=False, padding=0)

    # main component
    paned = Gtk.HPaned()
    paned.set_position(100)
    vbox.pack_start(paned, expand=True, fill=True, padding=0)

    self.__pages_model = Gtk.ListStore(str, object)
    self.__pages_view = Gtk.TreeView.new_with_model(self.__pages_model)
    self.__pages_view.set_enable_search(False)
    self.__pages_view.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
    self.__pages_view.get_selection().connect_after(
        'changed', self.__on_page_selected)

    # columns
    column = Gtk.TreeViewColumn()
    column.set_title('Pages')
    column.set_sizing(Gtk.TreeViewColumnSizing.AUTOSIZE)
    renderer = Gtk.CellRendererText()
    column.pack_start(renderer, False)
    column.add_attribute(renderer, 'text', 0)
    column.set_cell_data_func(renderer, self.__render_page_number)
    self.__pages_view.append_column(column)

    sw = Gtk.ScrolledWindow()
    sw.add(self.__pages_view)
    paned.add1(sw)

    self.__zoom_level = DEFAULT_ZOOM_LEVEL
    self.__canvas = GooCanvas.Canvas()
    self.__canvas.set_scale(ZOOM_LEVELS[DEFAULT_ZOOM_LEVEL])
    self.__canvas.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(240/255,240/255,240/255))
    self.__dragging = False

    frame = Gtk.Frame()
    frame.set_shadow_type(Gtk.ShadowType.ETCHED_OUT)
    frame.set_border_width(10)
    paned.add2(frame)

    sw = Gtk.ScrolledWindow()
    sw.add(self.__canvas)
    frame.add(sw)

    accels = Gtk.AccelGroup()
    accels.connect(ord('o'),
                   Gdk.ModifierType.CONTROL_MASK,
                   Gtk.AccelFlags.LOCKED,
                   self.__on_ctrl_o_pressed)
    accels.connect(ord('O'),
                   Gdk.ModifierType.CONTROL_MASK,
                   Gtk.AccelFlags.LOCKED,
                   self.__on_ctrl_o_pressed)
    accels.connect(ord('s'),
                   Gdk.ModifierType.CONTROL_MASK,
                   Gtk.AccelFlags.LOCKED,
                   self.__on_ctrl_s_pressed)
    accels.connect(ord('S'),
                   Gdk.ModifierType.CONTROL_MASK,
                   Gtk.AccelFlags.LOCKED,
                   self.__on_ctrl_s_pressed)
    accels.connect(ord('+'),
                   0,
                   Gtk.AccelFlags.LOCKED,
                   self.__on_zoom_in_pressed)
    accels.connect(ord('-'),
                   0,
                   Gtk.AccelFlags.LOCKED,
                   self.__on_zoom_out_pressed)
    self.add_accel_group(accels)

    self.__current_page = None
    self.__pdf_filename = None
    self.__pdf_document = None
    self.__n_pages = None
    self.__pdf_view = None
    self.__default_crop = CropSetting()
    self.__odd_crop = CropSetting(self.__default_crop)
    self.__even_crop = CropSetting(self.__default_crop)


  def __on_delete_window(self, window, event):
    Gtk.main_quit()


  def __open_btn_clicked(self, button):
    return self.__open_file()


  def __save_btn_clicked(self, button):
    return self.__save_file()


  def __on_ctrl_o_pressed(self, accel_group, acceleratable, keyval, modifier):
    return self.__open_file()


  def __on_ctrl_s_pressed(self, accel_group, acceleratable, keyval, modifier):
    return self.__save_file()


  def __on_zoom_in_btn_clicked(self, button):
    return self.__zoom_in_page()


  def __on_zoom_out_btn_clicked(self, button):
    return self.__zoom_out_page()


  def __on_zoom_in_pressed(self, accel_group, acceleratable, keyval, modifier):
    return self.__zoom_in_page()


  def __on_zoom_out_pressed(self, accel_group, acceleratable, keyval, modifier):
    return self.__zoom_out_page()


  def __render_page_number(self, column, cell, model, tree_iter, data):
    if self.__pages_view.get_selection().iter_is_selected(tree_iter):
      cell.set_property('weight', Pango.Weight.BOLD)
    else:
      cell.set_property('weight', Pango.Weight.NORMAL)


  def __zoom_in_page(self):
    if self.__pdf_document and self.__zoom_level < len(ZOOM_LEVELS) - 1:
      self.__zoom_level += 1
      self.__canvas.set_scale(ZOOM_LEVELS[self.__zoom_level])
      self.__on_page_selected()
      return True


  def __zoom_out_page(self):
    if self.__pdf_document and self.__zoom_level > 0:
      self.__zoom_level -= 1
      self.__canvas.set_scale(ZOOM_LEVELS[self.__zoom_level])
      self.__on_page_selected()
      return True


  def __open_file(self):
    dialog = Gtk.FileChooserDialog(title='Load pdf file',
                                   parent=self,
                                   action=Gtk.FileChooserAction.OPEN,
                                   buttons=(Gtk.STOCK_CANCEL,
                                            Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_OK,
                                            Gtk.ResponseType.OK))
    global LAST_OPEN_FOLDER
    if LAST_OPEN_FOLDER:
      dialog.set_current_folder(LAST_OPEN_FOLDER)
    else:
      dialog.set_current_folder(os.getcwd())
    file_filter = Gtk.FileFilter()
    file_filter.add_pattern("*.pdf")
    dialog.set_filter(file_filter)
    pdf_file_name = None

    try:
      response = dialog.run()
      if response == Gtk.ResponseType.OK:
        pdf_file_name = dialog.get_filename()
        LAST_OPEN_FOLDER = os.path.dirname(pdf_file_name)
      dialog.hide()
    finally:
      dialog.destroy()

    if pdf_file_name:
      self.__load_pdf_file(pdf_file_name)
      self.__pages_view.get_selection().select_iter(
          self.__pages_model.get_iter_first())

    return True


  def __save_file(self):
    if not self.__pdf_document:
      return True

    dialog = Gtk.FileChooserDialog(title='Export pdf file',
                                   parent=self,
                                   action=Gtk.FileChooserAction.SAVE,
                                   buttons=(Gtk.STOCK_CANCEL,
                                            Gtk.ResponseType.CANCEL,
                                            Gtk.STOCK_OK,
                                            Gtk.ResponseType.OK))
    global LAST_OPEN_FOLDER
    if LAST_OPEN_FOLDER:
      dialog.set_current_folder(LAST_OPEN_FOLDER)
    else:
      dialog.set_current_folder(os.getcwd())
    print(LAST_OPEN_FOLDER)
    file_filter = Gtk.FileFilter()
    file_filter.add_pattern("*.pdf")
    dialog.set_filter(file_filter)

    new_pdf_file_name = None
    try:
      response = dialog.run()
      if response == Gtk.ResponseType.OK:
        new_pdf_file_name = dialog.get_filename()
        LAST_OPEN_FOLDER = os.path.dirname(new_pdf_file_name)
    finally:
      dialog.destroy()

    if os.path.exists(new_pdf_file_name):
      msg_dialog = Gtk.MessageDialog(self,0,Gtk.MessageType.ERROR,Gtk.ButtonsType.CANCEL)
      msg_dialog.set_markup('File exists!')
      msg_dialog.run()
      msg_dialog.destroy()
      return True

    with open(self.__pdf_filename, 'rb') as in_fh:
      reader = PdfFileReader(in_fh)
      out_file = PdfFileWriter()
      for row in self.__pages_model:
        page_info = row[1]
        if not page_info.deleted:
          page = reader.getPage(page_info.pagenum)
          crop_setting = page_info.crop_setting.effective_crop_setting
          if not crop_setting.empty():
            x, y, w, h = (crop_setting['x'],
                          crop_setting['y'],
                          crop_setting['w'],
                          crop_setting['h'])
            # scale it, convert to real poppler page coordinates
            scale = self.__canvas.get_scale()
            x1, y1, w1, h1 = (x / scale, y / scale, w / scale, h / scale)
            # it's strange but cropBox.height != cropBox.upper_left_y -
            # cropBox.upper_left_x.  we should use the latter.
            h0 = float(page.cropBox.getUpperLeft_y() -
                       page.cropBox.getLowerLeft_y())
            w0 = float(page.cropBox.getUpperRight_x() -
                       page.cropBox.getUpperLeft_x())

            # convert poppler coordinates to pyPdf coordinates
            rotateAngle = page.get("/Rotate", 0)
            if rotateAngle < 0:
              rotateAngle = 360 + currentAngle
            if rotateAngle == 0:
              x1, y1 = x1, h0 - y1 - h1
            elif rotateAngle == 90:
              x1, y1, w1, h1 = y1, x1, h1, w1
            elif rotateAngle == 180:
              pass
            elif rotateAngle == 270:
              x1, y1 = h0 - y1 - h1, w0 - x1 - w1
            else:
              raise Exception('Invalid rotate angle: ' + rotateAngle)

            # poppler API provides only width and height while pyPdf
            # provides far more size information.  poppler width and height
            # doesn't always match pyPdf mediaBox.  Instead, we need to use
            # pyPdf cropBox size to rectify the calculated cropping box.
            x1, y1 = (x1 + float(page.cropBox.getLowerLeft_x()),
                      y1 + float(page.cropBox.getLowerLeft_y()))

            # now let's crop it.
            page.cropBox.lowerLeft = (x1, y1)
            page.cropBox.upperRight = (x1+w1, y1+h1)
            page.mediaBox.lowerLeft = page.cropBox.lowerLeft
            page.mediaBox.upperRight = page.cropBox.upperRight
          out_file.addPage(page)
      out_file.write(open(new_pdf_file_name, 'wb'))

    return True


  def external_load_pdf_file(self, filename):
    self.__load_pdf_file(filename)
    self.__pages_view.get_selection().select_iter(self.__pages_model.get_iter_first())


  def __load_pdf_file(self, filename):
    self.__pdf_filename = filename
    LAST_OPEN_FOLDER = os.path.dirname(filename)

    filename = os.path.abspath(filename)
    self.__pdf_document = Poppler.Document.new_from_file(
      'file://%s' % filename, None)
    self.__n_pages = self.__pdf_document.get_n_pages()

    self.__pages_model.clear()
    for i in range(self.__n_pages):
      if i % 2 == 0:
        size = self.__pdf_document.get_page(i).get_size()
        self.__pages_model.append(
            [str(i+1),
             PageInfo(i, CropSetting(self.__odd_crop), size)])
      else:
        self.__pages_model.append(
            [str(i+1), PageInfo(i, CropSetting(self.__even_crop), size)])

    if not self.__pdf_view:
      self.__pdf_view = PdfView()
      self.__canvas.get_root_item().add_child(self.__pdf_view, next_index())


  def __on_page_selected(self, selection=None):
    if not selection:
      selection = self.__pages_view.get_selection()

    tree_store, tree_iter = selection.get_selected()
    if tree_iter:
      page_info = tree_store[tree_iter][1]
      self.__current_page = self.__pdf_document.get_page(page_info.pagenum)
      page_width, page_height = self.__current_page.get_size()
      w, h = int(page_width), int(page_height)
      scale = self.__canvas.get_scale()
      w, h = int(w * scale), int(h * scale)
      self.__canvas.set_bounds(0, 0, w, h)

      self.__canvas.page_region = Gdk.Rectangle()
      self.__canvas.page_region.width, self.__canvas.page_region.height = w, h
      pw, ph = page_width, page_height
      page = self.__current_page
      # Render to a pixmap
      scale = min(w/pw, h/ph)
      surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
      context = cairo.Context(surface)
      context.scale(scale, scale)
      context.save()
      page.render(context)
      context.restore()
      # Convert pixmap to pixbuf
      pixbuf  = Gdk.pixbuf_get_from_surface (surface, 0, 0, w, h)
      self.__pdf_view.redraw(page_info, pixbuf)
    else:
      self.__pdf_view.redraw()


if __name__ == '__main__':
  window = MainWindow()
  if (len(sys.argv) > 1):
    window.external_load_pdf_file(sys.argv[1])
  window.show_all()
  Gtk.main()
