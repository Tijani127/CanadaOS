"""Hockey Arena — puck shootout mini-game + scoreboard."""
import math
import random

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

# cairo must be imported once in the process before draw callbacks run,
# or PyGObject refuses to hand callbacks a cairo.Context.
try:
    import cairo  # noqa: F401
except ImportError:  # pragma: no cover
    pass

from . import base
from .base import app_root, button, row_label, run_async

W, H = 640, 480


class Arena(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add_css_class("app-root")
        self.win = win

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = row_label("🏒 Shootout vs the Goalie", "app-title")
        left.append(title)

        self.state = "ready"
        self.puck = (W * 0.5, H - 60)
        self.target = None
        self.goalie_t = 0.0
        self.goalie_x = W * 0.5
        self.shots = 0
        self.goals = 0
        self.streak = 0
        self.flash = None
        self.flash_until = 0
        self.aim = None

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(W, H)
        self.area.set_hexpand(True)
        self.area.set_vexpand(True)
        self.area.add_css_class("rink")
        self.area.set_draw_func(self._draw, None)

        click = Gtk.GestureClick()
        click.connect("pressed", self._shot)
        self.area.add_controller(click)
        hover = Gtk.EventControllerMotion()
        hover.connect("motion", self._aim)
        hover.connect("leave", self._aim_leave)
        self.area.add_controller(hover)
        left.append(self.area)

        left.append(row_label("Aim inside the net and click to shoot — the goalie learns as you score.",
                              "muted-label"))

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        right.append(row_label("Boxscore", "section-title"))
        self.score_label = row_label("Shots 0 · Goals 0", "muted-label")
        right.append(self.score_label)
        right.append(button("🚨 GO LEAFS GO 🚨",
                            lambda *_: base.info_dialog(self.win, "📣 Applause",
                                                        "Loudly. That's the whole feature.")))
        right.append(button("Reset match", lambda *_: self.reset()))

        scores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scores.append(row_label("Tonight's scoreboard", "section-title"))
        self.scores_label = row_label("Fetching…", "muted-label")
        self.scores_label.set_wrap(True)
        scores.append(self.scores_label)
        scores.append(button("Refresh scores", lambda *_: self.fetch_scores()))
        right.append(scores)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        right.append(spacer)

        self.append(left)
        self.append(right)

        GLib.timeout_add(33, self._tick)

    def reset(self):
        self.shots = 0
        self.goals = 0
        self.streak = 0
        self.state = "ready"
        self.puck = (W * 0.5, H - 60)
        self.target = None
        self.flash = None
        self._score()

    def _score(self):
        self.score_label.set_text("Shots {} · Goals {} · Streak {}".format(
            self.shots, self.goals, self.streak))

    def _shot(self, gesture, n, x, y):
        if self.state != "ready":
            return
        self.target = (x, y)
        self.state = "flying"
        self.shots += 1
        self._score()

    def _aim(self, _ctl, x, y):
        self.aim = (x, y)

    def _aim_leave(self, _ctl):
        self.aim = None

    def _goalie_speed(self):
        # The goalie trains while you celebrate: harder to beat at higher scores.
        return 0.033 * (1.0 + 0.5 * self.goals)

    def _goalie_x_now(self):
        return W * 0.5 + 0.40 * W * math.sin(self.goalie_t * 1.8)

    def _tick(self):
        self.goalie_t += self._goalie_speed()
        self.goalie_x = self._goalie_x_now()
        if self.state == "flying" and self.target:
            px, py = self.puck
            tx, ty = self.target
            dx, dy = tx - px, ty - py
            dist = math.hypot(dx, dy)
            if dist < 14:
                self.puck = (tx, ty)
                self._resolve()
            else:
                # A real slapper: crosses the rink in well under a second.
                speed = 15.0 + 0.25 * (H - py)
                step = min(speed, dist)
                self.puck = (px + step * dx / dist, py + step * dy / dist)
        if self.flash and GLib.get_monotonic_time() > self.flash_until:
            self.flash = None
        self.area.queue_draw()
        return True

    def _resolve(self):
        tx, ty = self.target
        in_net = 60 < ty < 150 and 40 < tx < W - 40
        self.streak = self.streak + 1 if in_net and abs(tx - self.goalie_x) >= 45 else 0
        if not in_net:
            post = abs(tx - 40) < 18 or abs(tx - (W - 40)) < 18 or abs(ty - 150) < 18
            self.flash = ("PING — off the post!" if post else "MISS — wide of the net.",
                          "#e9b44c")
        elif abs(tx - self.goalie_x) < 45:
            self.flash = ("🧤 SAVED! The goalie kicks himself.", "#5db6d7")
        else:
            self.goals += 1
            self._score()
            self.flash = ("🚨 GOAL! Streak of {} in a row.".format(self.streak)
                          if self.streak > 1 else "🚨 GOAL!", "#7ec142")
            if self.goals >= 5:
                self.flash = ("🥇 FIVE goals — you're basically elite.", "#7ec142")
                self.streak = 0
                self.goals = 0
                self.shots = 0
                self._score()
        self.flash_until = GLib.get_monotonic_time() + 1_800_000
        self.state = "ready"
        self.puck = (W * 0.5, H - 60)
        self.target = None

    def _draw(self, area, cr, w, h, data=None):
        scale_x = w / W
        scale_y = h / H
        cr.save()
        cr.scale(scale_x, scale_y)

        # rink
        cr.set_source_rgb(0.93, 0.96, 1.0)
        cr.rectangle(20, 30, W - 40, H - 50)
        cr.fill()
        # boards
        cr.set_line_width(6)
        cr.set_source_rgb(0.2, 0.24, 0.28)
        cr.rectangle(20, 30, W - 40, H - 50)
        cr.stroke()

        # center red line
        cr.set_source_rgb(0.84, 0.17, 0.12)
        cr.set_line_width(2)
        cr.move_to(W / 2, 30)
        cr.line_to(W / 2, H - 20)
        cr.stroke()

        # faceoff circles
        for cx in (W * 0.28, W * 0.72):
            cr.set_source_rgb(0.2, 0.4, 0.8)
            cr.set_line_width(2)
            cr.arc(cx, H * 0.42, 48, 0, 6.28318)
            cr.stroke()

        # net
        cr.set_source_rgb(0.85, 0.85, 0.85)
        cr.rectangle(40, 50, W - 80, 100)
        cr.stroke()
        cr.set_source_rgb(0.75, 0.78, 0.82)
        cr.rectangle(40, 50, W - 80, 12)
        cr.fill_preserve()
        cr.stroke()

        # goalie block
        gx = self.goalie_x
        cr.set_source_rgb(0.14, 0.62, 0.86)
        cr.rectangle(gx - 45, 70, 90, 18)
        cr.fill()

        # puck
        px, py = self.puck
        cr.set_source_rgb(0.07, 0.07, 0.08)
        cr.arc(px, py, 7, 0, 6.28318)
        cr.fill()

        # aim reticle while waiting for a shot
        if self.state == "ready" and self.aim:
            ax, ay = self.aim
            cr.set_source_rgba(0.84, 0.17, 0.12, 0.9)
            cr.set_line_width(2)
            cr.set_dash([4, 4])
            cr.arc(ax, ay, 16, 0, 6.28318)
            cr.stroke()
            cr.set_dash([])
            cr.move_to(ax - 24, ay)
            cr.line_to(ax - 6, ay)
            cr.move_to(ax + 6, ay)
            cr.line_to(ax + 24, ay)
            cr.move_to(ax, ay - 24)
            cr.line_to(ax, ay - 6)
            cr.move_to(ax, ay + 6)
            cr.line_to(ax, ay + 24)
            cr.stroke()

        # flash message
        if self.flash:
            text, color = self.flash
            cr.set_source_rgb(*self._rgb(color))
            cr.select_font_face("Sans", 0, 1)
            cr.set_font_size(30)
            ext = cr.text_extents(text)
            cr.move_to(W / 2 - ext.width / 2, H * 0.62)
            cr.show_text(text)

        cr.restore()

    @staticmethod
    def _rgb(hexcolor):
        h = hexcolor.lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def fetch_scores(self):
        self.scores_label.set_text("Fetching tonight's scores…")

        def fetcher():
            import json as _json
            import urllib.request
            with urllib.request.urlopen("https://api-web.nhle.com/v1/score/now", timeout=8) as resp:
                raw = resp.read()
                return _json.loads(raw)

        def done(result):
            if isinstance(result, Exception) or not isinstance(result, dict):
                self.scores_label.set_text(
                    "📡 Offline, so here's simulated hockey:\n\n"
                    "CAN 4 - TOR 2   •   MTL 3 - WSH 1\n"
                    "EDM 2 - CGY 5   •   WPG 6 - VAN 0\n"
                    "(From the polite parallel universe.)")
                return
            try:
                lines = []
                for g in result.get("games", [])[:8]:
                    def pick(*keys, obj=None):
                        o = obj
                        for k in keys:
                            if o is None or not isinstance(o, dict):
                                return None
                            o = o.get(k)
                        return o
                    home = pick("homeTeam", obj=g) or pick("home", obj=g) or {}
                    away = pick("awayTeam", obj=g) or pick("away", obj=g) or {}
                    ab = (home.get("abbrev") or home.get("teamAbbrev") or
                          (home.get("team") or {}).get("abbrev") or "?")
                    ah = (away.get("abbrev") or away.get("teamAbbrev") or
                          (away.get("team") or {}).get("abbrev") or "?")
                    hs = home.get("score")
                    as_ = away.get("score")
                    lines.append("{} {} — {} {}".format(ab, as_ if as_ is not None else "-", ah,
                                                        hs if hs is not None else "-"))
                self.scores_label.set_text("\n".join(lines) or "No games right now, sorry.")
            except Exception:
                self.scores_label.set_text("The scoreboard service was unavailable. Try again.")

        run_async(fetcher, done)


def build(win, opts=None):
    return Arena(win)
