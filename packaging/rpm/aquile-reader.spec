Name:           aquile-reader
Version:        0.1.0
Release:        1.preview%{?dist}
Summary:        Modern, customizable eBook reader (Ubuntu port preview)
License:        MIT
# No URL: this clean-room Ubuntu port has no authorized public homepage yet.
# Do not point at the proprietary upstream site or store listings (see PRD S1-S5).
BuildArch:      noarch

# Fedora/RHEL-family capability names for the GTK4/Libadwaita runtime.
# On openSUSE the equivalents are typically python3-gobject, gtk4,
# libadwaita and poppler-glib in the matching repo naming.
Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       poppler-glib

Source0:        %{name}-%{version}.tar.gz

%description
Aquile Reader for Ubuntu (preview package).
Local DRM-free EPUB/PDF/CBZ/CBR reading with two-column layout,
annotations, and offline-first library storage. Unsigned preview build:
local books, annotations, and settings work fully offline with no sign-in.
Runtime writes only to XDG user directories; normal use never needs root.

%prep
%setup -q

%build
# Pure-Python payload, nothing to compile.

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/usr/bin \
         %{buildroot}/usr/share/aquile-reader \
         %{buildroot}/usr/share/applications \
         %{buildroot}/usr/share/mime/packages

# Payload: package-private copy of the sources plus the entry point.
# run_aquile.py puts its sibling src/ on sys.path, so no site-packages
# install is needed.
cp -r src %{buildroot}/usr/share/aquile-reader/src
cp run_aquile.py %{buildroot}/usr/share/aquile-reader/run_aquile.py
# Hygiene: never ship bytecode caches (keeps the package small and avoids
# stale .pyc shadowing source on target machines).
find %{buildroot}/usr/share/aquile-reader -type d -name '__pycache__' \
    -prune -exec rm -rf {} + 2>/dev/null || true
find %{buildroot}/usr/share/aquile-reader -type f -name '*.py[co]' \
    -delete 2>/dev/null || true

# Launcher (root-free at runtime; app data lives under XDG dirs).
cat > %{buildroot}/usr/bin/aquile-reader <<'EOF'
#!/bin/sh
exec python3 /usr/share/aquile-reader/run_aquile.py "$@"
EOF
chmod 0755 %{buildroot}/usr/bin/aquile-reader

# Desktop entry: rewrite absolute Exec to the installed launcher path.
sed 's|^Exec=.*|Exec=/usr/bin/aquile-reader %%F|' \
    data/org.antigravity.AquileReader.desktop \
    > %{buildroot}/usr/share/applications/org.antigravity.AquileReader.desktop
# Harden staged entry: launcher must be visible (NoDisplay=false) and must
# advertise every MIME type the package registers (EPUB, PDF, CBZ, CBR).
grep -q '^NoDisplay=' \
    %{buildroot}/usr/share/applications/org.antigravity.AquileReader.desktop \
    || printf 'NoDisplay=false\n' \
    >> %{buildroot}/usr/share/applications/org.antigravity.AquileReader.desktop
grep -q 'application/vnd.comicbook-rar' \
    %{buildroot}/usr/share/applications/org.antigravity.AquileReader.desktop \
    || sed -i 's|^MimeType=.*|MimeType=application/epub+zip;application/pdf;application/vnd.comicbook+zip;application/vnd.comicbook-rar;|' \
    %{buildroot}/usr/share/applications/org.antigravity.AquileReader.desktop

# MIME registration for supported formats (reader must not steal defaults:
# package only registers, it sets no default handler). Desktop and MIME
# database refreshes are handled by distro file triggers, so no scriptlets.
cat > %{buildroot}/usr/share/mime/packages/aquile-reader.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/epub+zip">
    <comment>EPUB eBook</comment>
    <glob pattern="*.epub"/>
  </mime-type>
  <mime-type type="application/pdf">
    <comment>PDF document</comment>
    <glob pattern="*.pdf"/>
  </mime-type>
  <mime-type type="application/vnd.comicbook+zip">
    <comment>Comic book archive</comment>
    <glob pattern="*.cbz"/>
  </mime-type>
  <mime-type type="application/vnd.comicbook-rar">
    <comment>Comic book archive</comment>
    <glob pattern="*.cbr"/>
  </mime-type>
</mime-info>
EOF

# License text for %license.
cp LICENSE %{buildroot}/usr/share/aquile-reader/LICENSE 2>/dev/null || true

%files
%license LICENSE
/usr/bin/aquile-reader
/usr/share/aquile-reader/
/usr/share/applications/org.antigravity.AquileReader.desktop
/usr/share/mime/packages/aquile-reader.xml

%changelog
* Sat Oct 03 2026 Aquile Reader Ubuntu Port Team - 0.1.0-1.preview
- Initial unsigned preview RPM: offline-first EPUB/PDF/CBZ/CBR reader,
  GTK4/Libadwaita runtime, XDG-respecting root-free operation.
