# CanadaOS 🍁

The politest operating system. A fully custom, bootable, graphical Linux distro
built around Canadian stereotypes — dark theme, maple accents, and it says sorry
more than any other OS on the market.

## What's inside

| App | What it is | Dev Mode |
|---|---|---|
| 🎨 Paint | Canvas painting with the Canadian palette (Maple Red, Beaver Brown, Snow, Rockies Blue, Prairie Gold…). Save as PNG. | no |
| 🗒️ Notepad | Plain text notes, wrap toggle, char/word count. Simple and humble, unlike that syrup editor. | no |
| 🌐 Browser | Real internet via WebKit, address bar, back/forward, Canada-flavoured start page (`canadaos://home`). | no |
| 🗃️ Files | Real filesystem explorer: browse, new folder/file, rename, delete; `.maple` files jump to the Syrup editor, text to Notepad. | no |
| 🏒 Hockey Arena | Playable puck-shootout mini-game (click to shoot against a moving goalie) + live NHL scoreboard fetch with offline fallback. | no |
| ⚙️ Settings | Wallpapers, About, and **Dev Mode unlock**. | no |
| 💻 Sorry Terminal | A *real* bash terminal (VTE) that greets you politely, with Canadian commands layered on top: `sorry`, `hockey`, `poursyrup`, `toque`, `timmy`, `beaver`, `beavertail`, `maple-lint`, `canadaos-version`, `canadaos-weather`. | **yes** |
| 🍁 Maple Syrup Editor | A dev-grade syntax-highlighting editor for a tiny `.maple` language: line numbers, smart indent, colour tags, "Pour" linter, help. | **yes** |

### Dev Mode

Open **Settings → Dev Mode** and enter the secret password.

*Hint from Settings itself:* it's what you order at Tim Hortons when you want
two creams and two sugars → **`double-double`**

Dev Mode unlocks the Sorry Terminal + Maple Syrup Editor, and lights up a red
`DEV 🍁 ON` badge in the top bar. The flag persists in
`~/.config/canadaos/config.json`.

### Architecture (this is a real distro)

```
CanadaOS/
├── build/                      # live-build config (Debian bookworm ISO)
│   ├── config/package-lists/   # apt package list
│   ├── config/hooks/           # optional runtime bindings (VTE, WebKit)
│   └── config/includes.chroot/ # files laid directly on the ISO filesystem
│       ├── etc/lightdm/...     # autologin straight into CanadaOS
│       ├── etc/canadaos/sorryrc
│       ├── usr/bin/linux-session+shell launchers
│       └── usr/local/bin/      # Canadian shell commands
├── shell/                      # the desktop itself (Python 3 + GTK 4)
│   ├── canadaos/desktop.py     # top bar, dock, internal window manager
│   ├── canadaos/main.py        # entry: python3 -m canadaos.main
│   ├── canadaos/config.py      # dev-mode flag, wallpaper, ~/.config json
│   ├── canadaos/apps/          # paint, notepad, browser, terminal, files,
│   │                           # settings, hockey, syrup
│   └── canadaos/data/canada.css  # the whole dark maple theme
└── scripts/build-iso.sh        # one command to build the ISO
```

- **Shell**: one fullscreen GTK4 window is the desktop. Its `desktop.py` draws
  the top bar, dock, windows (draggable / resizable / minimisable / closable)
  and the app windows themselves — so no window manager is needed. `{main}`:
  `python3 -m canadaos.main`.
- **Sorry Terminal** runs a real `bash -l` through `/usr/local/bin/sorry-shell`
  which sources `/etc/canadaos/sorryrc` (aliases, PS1) then execs bash.
  The Canadian commands are real executables in `/usr/local/bin`.
- **Graceful fallbacks**: if a gadget binding (VTE / WebKit gir) isn't
  installed, apps show a friendly "install gir1.2-…" screen instead of crashing.

## Build the ISO (boot it in a VM)

Needs a Linux environment. Easiest: WSL2 + Debian on Windows.

```sh
sudo apt update && sudo apt install -y live-build debootstrap qemu-system-x86
./scripts/build-iso.sh                       # from the repo root
# grind. ~30-60 min depending on network/mirrors.
qemu-system-x86_64 -m 4096 -cdrom build/live-image-amd64.iso -enable-kvm
```

Or open the ISO in VirtualBox / any PC USB. LightDM logs in as `user`
automatically (password `live` if the login screen ever asks) and boots
straight into the CanadaOS desktop.

### If the desktop session crashes and you're bounced back to a login screen

From the greeter choose the **CanadaOS (debug — openbox)** session (top right
corner), log in with `user` / `live` — a minimal window manager and terminal
open, where the shell can be launched by hand so any traceback is visible:

```sh
PYTHONPATH=/usr/lib/canadaos python3 -m canadaos.main
```

## Debug / develop the shell without an ISO

On any Linux machine (or WSL GUI) with GTK4 bindings:

```sh
cd shell && PYTHONPATH=. python3 -m canadaos.main
```

## Known quirks (documented, not apologised for twice)

- The first build of an ISO takes a while; live-build mirrors are chatty.
- Emoji tiles need `fonts-noto-color-emoji` (already in the package list).
- The HUD "browser" only offers real URLs after build; first boot shows
  `canadaos://home` start page with polite bookmarks.

Have fun, and remember: if anything goes wrong, just run `sorry`. Twice. Eh.
