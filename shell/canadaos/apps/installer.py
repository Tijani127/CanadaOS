"""Installer — sends CanadaOS from the ISO onto a real hard disk.

Choosing a disk and confirming is the dangerous part; the actual install
runs /usr/local/bin/canadaos-install (root). The log streams into this
window so the user can watch instead of staring, eh."""
import json
import os
import subprocess
import threading

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from .base import button, row_label, info_dialog, confirm_dialog

INSTALL_SCRIPT = "/usr/local/bin/canadaos-install"


def _sudo_available():
    """Passwordless sudo? (the live user's sudoers allows NOPASSWD)"""
    try:
        return subprocess.run(["sudo", "-n", "true"], timeout=10).returncode == 0
    except Exception:
        return False


def _disks():
    """Physical disks: [(path, bytes, model, removable)]"""
    try:
        out = subprocess.run(
            ["lsblk", "--json", "-b", "-d",
             "-o", "NAME,SIZE,TYPE,RM,MODEL"],
            capture_output=True, text=True, timeout=10).stdout
        data = json.loads(out)
    except Exception:
        return []
    disks = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        try:
            size = int(dev.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        model = (dev.get("model") or "").strip() or "disk"
        disks.append((
            "/dev/" + dev.get("name", ""),
            size,
            model,
            bool(dev.get("rm")),
        ))
    return disks


def _gib(n):
    return "{:.1f} GiB".format(n / (1024 ** 3))


class Installer(Gtk.Box):
    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(14)
        self.set_margin_end(14)
        self.add_css_class("app-root")
        self.win = win
        self._running = False
        self._disks = _disks()
        self._needs_password = not _sudo_available()

        intro = row_label(
            "Install CanadaOS onto a real hard drive instead of booting "
            "from the ISO every time. Everything on the chosen disk — "
            "every partition — is erased. Permanently.", "muted-label")
        intro.set_wrap(True)

        # Target disk
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.append(row_label("Target disk:", "muted-label"))
        self._dropdown = None
        try:
            names = ["{} — {} {}{}".format(
                    d[0], _gib(d[1]), d[2], " (removable)" if d[3] else "")
                for d in self._disks] or ["no physical disks found"]
            self._dropdown = Gtk.DropDown.new_from_strings(tuple(names))
            self._dropdown.set_hexpand(True)
            row.append(self._dropdown)
        except Exception:
            row.append(row_label("(disk chooser unavailable)", "muted-label"))
        row.append(button("Refresh", self._refresh, "app-tile"))

        pwrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if self._needs_password:
            pwrow.append(row_label("sudo password:", "muted-label"))
            self._password = Gtk.Entry()
            self._password.set_visibility(False)
            self._password.set_placeholder_text("(live user default: live)")
            self._password.set_hexpand(True)
            pwrow.append(self._password)

        warn = row_label(
            "⚠️ This cannot be undone. Double-check the disk name before "
            "continuing.", "muted-label")
        warn.set_wrap(True)
        warn.add_css_class("danger-label")

        self._agree = Gtk.CheckButton(
            label="I understand the selected disk will be completely erased")
        self._agree.connect("toggled", lambda *_: self._sync())

        self._go = button("Install to disk", self._ask, "app-tile")

        self._status = row_label("", "muted-label")
        self._status.set_wrap(True)

        self._log = Gtk.TextView()
        self._log.set_editable(False)
        self._log.set_cursor_visible(False)
        self._log.set_wrap_mode(Gtk.WrapMode.CHAR)
        self._log.add_css_class("mono")
        self._buf = self._log.get_buffer()
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(self._log)

        self.append(intro)
        self.append(row)
        if self._needs_password:
            self.append(pwrow)
        self.append(warn)
        self.append(self._agree)
        self.append(self._go)
        self.append(self._status)
        self.append(scroller)
        self._sync()

    # ---- helpers -----------------------------------------------------

    def _selected_disk(self):
        if not self._disks or self._dropdown is None:
            return None
        idx = self._dropdown.get_selected()
        if idx is None or idx >= len(self._disks):
            return None
        return self._disks[idx]

    def _sync(self, *_a):
        ok = (not self._running and bool(self._disks)
              and bool(self._agree.get_active()))
        self._go.set_sensitive(ok)

    def _refresh(self, *_a):
        if self._running:
            return
        self._disks = _disks()
        names = ["{} — {} {}{}".format(
                d[0], _gib(d[1]), d[2], " (removable)" if d[3] else "")
            for d in self._disks] or ["no physical disks found"]
        try:
            if self._dropdown is None:
                self._dropdown = Gtk.DropDown.new_from_strings(tuple(names))
            else:
                self._dropdown.set_model(Gtk.StringList.new(names))
        except Exception:
            pass
        self._sync()

    def _ask(self, *_a):
        if self._running:
            return
        disk = self._selected_disk()
        if disk is None:
            return
        confirm_dialog(
            self.win, "Erase {}?".format(disk[0]),
            "{} ({} — {}) will be formatted and CanadaOS installed. "
            "All data on it is gone forever. Proceed?".format(
                disk[0], _gib(disk[1]), disk[2]),
            lambda: self._begin(disk))

    # ---- the real work ------------------------------------------------

    def _begin(self, disk):
        self._running = True
        self._sync()
        try:
            self._dropdown.set_sensitive(False)
        except Exception:
            pass
        self._status.set_text("Installing to {} — this takes a few "
                              "minutes...".format(disk[0]))
        self._log_line("")
        self._log_line("=== canadaos-install {} ===".format(disk[0]))

        root = os.geteuid() == 0
        if root:
            cmd = [INSTALL_SCRIPT, disk[0]]
        else:
            cmd = ["sudo", "-S", "-p", "", INSTALL_SCRIPT, disk[0]]
        password = self._password.get_text() if self._needs_password else ""

        def work():
            rc = 1
            err = ""
            try:
                proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1)
                if not root:
                    try:
                        proc.stdin.write(password + "\n")
                        proc.stdin.flush()
                    except Exception as ex:
                        err = str(ex)
                with proc.stdout:
                    for line in iter(proc.stdout.readline, ""):
                        line = line.rstrip("\r\n")
                        if line:
                            GLib.idle_add(self._log_line, line)
                rc = proc.wait()
            except Exception as ex:  # noqa: BLE001
                err = str(ex) or err
            GLib.idle_add(self._finished, rc, err)

        threading.Thread(target=work, daemon=True).start()

    def _log_line(self, text):
        self._buf.insert(self._buf.get_end_iter(), text + "\n")
        try:
            scroll = self._log.get_parent()
            adj = scroll.get_vadjustment()
            adj.set_value(adj.get_upper())
        except Exception:
            pass
        return False

    def _finished(self, rc, err):
        self._running = False
        try:
            self._dropdown.set_sensitive(True)
        except Exception:
            pass
        self._sync()
        if rc == 0:
            self._status.set_text(
                "Installed! Shut down, remove the boot media, and boot "
                "from the disk.")
            confirm_dialog(
                self.win, "CanadaOS installed",
                "Installation finished. Reboot now and remove the boot "
                "media? (The live ISO session you are in is unaffected "
                "until reboot.)", self._reboot)
        else:
            self._status.set_text("Install failed ({}). See the log."
                                  .format(rc))
            info_dialog(
                self.win, "Install failed",
                "The installer could not finish. The log below has the "
                "exact error. {}".format(err))

    def _reboot(self, *_a):
        root = os.geteuid() == 0
        if root:
            subprocess.Popen(["systemctl", "reboot"])
            return
        password = self._password.get_text() if self._needs_password else ""

        def work():
            subprocess.Popen(
                ["sudo", "-S", "-p", "", "systemctl", "reboot"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).stdin.write(password + "\n")

        threading.Thread(target=work, daemon=True).start()


def build(win, opts=None):
    return Installer(win)
