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
chmod +x "$INC/usr/bin/canadaos-shell" "$INC/usr/bin/canadaos-session" "$INC/usr/bin/canadaos-debug-session"
chmod +x "$INC/usr/local/bin/"* 2>/dev/null || true
chmod +x scripts/*.sh

echo "⚙️   lb config …"
cd build
lb config noauto \
  --distribution bookworm \
  --architectures amd64 \
  --binary-images iso-hybrid \
  --bootappend-live "boot=live components quiet splash console=ttyS0" \
  --iso-volume "CanadaOS-1.0-amd64" \
  --iso-application "CanadaOS 1.0 'Double-Double'" \
  --iso-publisher "canadaos;ca" \
  --debian-installer none \
  "${@}"

# The host (Ubuntu CI runner) would otherwise try to bootstrap bookworm from
# Ubuntu mirrors. Force the parent mirrors to Debian, always, eh.
cat >> config/common <<'EOF'
LB_PARENT_DISTRIBUTION="bookworm"
LB_PARENT_ARCHIVE_AREAS="main contrib non-free non-free-firmware"
LB_PARENT_MIRROR_BOOTSTRAP="http://deb.debian.org/debian"
LB_PARENT_MIRROR_CHROOT="http://deb.debian.org/debian"
LB_PARENT_MIRROR_CHROOT_SECURITY="http://security.debian.org/"
LB_PARENT_MIRROR_BINARY="http://deb.debian.org/debian"
LB_PARENT_MIRROR_BINARY_SECURITY="http://security.debian.org/"
LB_MIRROR_BOOTSTRAP="http://deb.debian.org/debian"
LB_MIRROR_CHROOT="http://deb.debian.org/debian"
LB_MIRROR_BINARY="http://deb.debian.org/debian"
EOF

echo "🏗️   lb build (this takes a while — have a double-double)…"

# Ubuntu runners ship /etc/live/build.conf pointing at archive.ubuntu.com,
# which cannot serve Debian suites (the exact failure: asking ubuntu for
# bookworm). Rewrite those mirrors to Debian — bullets over charm.
if [ -f /etc/live/build.conf ]; then
    echo "🔧  /etc/live/build.conf before patching:"
    cat /etc/live/build.conf || true
    sed -i 's|archive.ubuntu.com/ubuntu|deb.debian.org/debian|g' /etc/live/build.conf
    echo "🔧  /etc/live/build.conf after patching:"
    cat /etc/live/build.conf || true
fi
lb build noauto "${@}"

echo
echo "Done, eh. ISO at: build/live-image-amd64.iso"
echo "Test it:  qemu-system-x86_64 -m 4096 -cdrom build/live-image-amd64.iso -enable-kvm"
