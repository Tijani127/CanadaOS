#!/usr/bin/env bash
# CanadaOS ISO build — run on (or inside WSL) Debian/Ubuntu:
#   sudo apt install live-build debootstrap
#   ./scripts/build-iso.sh
# Output: build/canadaos-*.iso
set -euo pipefail
cd "$(dirname "$0")/.."

echo "🇨🇦  Copying the CanadaOS shell into the live chroot includes…"
INC=build/config/includes.chroot
install -d "$INC/usr/lib/canadaos"
rm -rf "$INC/usr/lib/canadaos/canadaos"
cp -r shell/canadaos "$INC/usr/lib/canadaos/canadaos"
find "$INC/usr/lib/canadaos" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

echo "🔧  Marking hook + include files executable…"
chmod +x build/config/hooks/live/*.chroot 2>/dev/null || true
chmod +x "$INC/usr/bin/canadaos-shell" "$INC/usr/bin/canadaos-session"
chmod +x "$INC/usr/local/bin/"* 2>/dev/null || true
chmod +x scripts/*.sh

echo "⚙️   lb config …"
cd build
lb config noauto \
  --distribution bookworm \
  --architectures amd64 \
  --binary-images iso-hybrid \
  --bootappend-live "boot=live components quiet splash" \
  --iso-volume "CanadaOS-1.0-amd64" \
  --iso-application "CanadaOS 1.0 'Double-Double'" \
  --iso-publisher "canadaos;ca" \
  --debian-installer none \
  "${@}"

echo "🏗️   lb build (this takes a while — have a double-double)…"
lb build noauto "${@}"

echo
echo "Done, eh. ISO at: build/live-image-amd64.iso"
echo "Test it:  qemu-system-x86_64 -m 4096 -cdrom build/live-image-amd64.iso -enable-kvm"
