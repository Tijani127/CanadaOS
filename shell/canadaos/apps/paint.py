"""Paint app — draw with Canadian colours, eh."""
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk  # noqa: F401

import cairo

from . import base


class ColorSwatch(Gtk.Box):
    """Clickable colour chip (drawn, so we can use any colour)."""

    def __init__(self, name, hexcolor, selected=False, on_pick=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.hexcolor = hexcolor
        self._selected = selected
        self._on_pick = on_pick

        da = Gtk.DrawingArea()
        da.set_size_request(26, 26)
        da.add_css_class("paint-swatch")
        if selected:
            da.add_css_class("paint-swatch-active")
        da.set_draw_func(self._draw, None)
        self._da = da
        self.append(da)

        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self._clicked)
        da.add_controller(gesture)

        tip = Gtk.Accessible  # noqa: F841 — title via tooltip
        da.set_tooltip_text("{} ({})".format(name, hexcolor))

    def _draw(self, area, cr, w, h, data):
        r, g, b = self._rgb()
        cr.set_source_rgb(r, g, b)
        cr.rectangle(1, 1, w - 2, h - 2)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, 0.18)
        cr.rectangle(1, 1, w - 2, h // 3)
        cr.fill()

    def _rgb(self):
        h = self.hexcolor.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def _clicked(self, gesture, n, x, y):
        if self._on_pick:
            self._on_pick(self)


class Paint(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        base_utils = base
        self.add_css_class("app-root")
        self.win = win
        self.surface = None
        self.color = "#d52b1e"
        self.brush = 4
        self.drawing = False
        self.last = None
        self.swatches = []

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.palette_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.append(self.palette_box)
        for name, hex_c in base.CANADIAN_COLORS:
            sw = ColorSwatch(name, hex_c, selected=(hex_c == self.color), on_pick=self.pick)
            self.swatches.append(sw)
            self.palette_box.append(sw)

        # brush size
        self.size_adj = Gtk.Adjustment(value=4, lower=1, upper=40)
        spin = Gtk.SpinButton(adjustment=self.size_adj)
        spin.set_value(4)
        spin.connect("value-changed", lambda s: setattr(self, "brush", int(s.get_value())))
        toolbar.append(spin)

        self.eraser = Gtk.ToggleButton(label="Eraser 🧽")
        self.eraser.connect("toggled", lambda b: self._toggle_eraser(b))
        toolbar.append(self.eraser)

        toolbar.append(base_utils.button("Clear 🧹", lambda *_: self.clear()))
        self.save_btn = base_utils.button("Save PNG 💾", lambda *_: self.save())
        toolbar.append(self.save_btn)

        self.area = Gtk.DrawingArea()
        self.area.set_vexpand(True)
        self.area.set_hexpand(True)
        self.area.add_css_class("paint-area")
        self.area.set_draw_func(self._on_draw, None)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self.area.add_controller(motion)
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_press)
        click.connect("released", self._on_release)
        self.area.add_controller(click)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.area)

        self.append(toolbar)
        self.append(scroller)
        self.append(base_utils.status_bar("🎨 Paint — maple red saved your masterpieces, eh"))

    def _toggle_eraser(self, b):
        self.color = "#f4f7fa" if b.get_active() else "#d52b1e"
        for sw in self.swatches:
            active = (not b.get_active()) and sw.hexcolor == self.color
            sw._da.get_first_child()  # noop, kept simple
            self._set_active(sw, active)

    def _set_active(self, swatch, active):
        for cls in ("paint-swatch-active",):
            if swatch._da.has_css_class(cls):
                swatch._da.remove_css_class(cls)
        if active:
            swatch._da.add_css_class("paint-swatch-active")

    def pick(self, swatch):
        self.color = swatch.hexcolor
        self.eraser.set_active(False)
        for s in self.swatches:
            self._set_active(s, s is swatch)

    def clear(self):
        self.surface = None
        self.area.queue_draw()

    def _ensure_surface(self, w, h):
        if self.surface is None or w > self.surface.get_width() or h > self.surface.get_height():
            old = self.surface
            new = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, w), max(1, h))
            if old is not None:
                cr = cairo.Context(new)
                cr.set_source_surface(old, 0, 0)
                cr.paint()
            self.surface = new

    def _stroke_to(self, x, y):
        if self.surface is None:
            return
        h = self.hexcolor_rgb()
        cr = cairo.Context(self.surface)
        cr.set_source_rgba(*h)
        cr.set_line_width(self.brush)
        cr.set_line_cap(cairo.LineCap.ROUND)
        cr.set_line_join(cairo.LineJoin.ROUND)
        if self.last:
            cr.move_to(*self.last)
            cr.line_to(x, y)
            cr.stroke()
        else:
            cr.arc(x, y, self.brush / 2, 0, 6.28318)
            cr.fill()
        self.last = (x, y)
        self.area.queue_draw()

    def hexcolor_rgb(self):
        h = self.color.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def _on_draw(self, area, cr, w, h, data=None):
        cr.set_source_rgb(0.96, 0.97, 0.98)  # snow-ish canvas
        cr.paint()
        if self.surface:
            cr.set_source_surface(self.surface, 0, 0)
            cr.paint()

    def _on_motion(self, ctl, x, y):
        if self.drawing:
            self._stroke_to(x, y)

    def _on_press(self, gesture, n, x, y):
        self.drawing = True
        self._ensure_surface(gesture.get_widget().get_allocated_width(),
                             gesture.get_widget().get_allocated_height())
        self._stroke_to(x, y)

    def _on_release(self, gesture, n, x, y):
        self.drawing = False
        self.last = None

    def save(self):
        def done(path):
            if not path:
                return
            try:
                self.surface.write_to_png(path)
            except AttributeError:
                pass
        base.choose_save_file(self.win, done, suggested="artwork.png")


def build(win, opts=None):
    return Paint(win, opts=opts)
