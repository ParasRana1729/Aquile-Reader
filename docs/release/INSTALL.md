# Aquile Reader 0.1.0-preview — Install Guide (Ubuntu)

All artifacts are built by scripts in `scripts/` into `dist/` (gitignored build
output — attach them to a GitHub Release, do not commit them).

| Artifact | File | Size | Use |
| --- | --- | --- | --- |
| .deb | `dist/aquile-reader_0.1.0-preview_amd64.deb` | ~70K | Ubuntu/Debian: `sudo dpkg -i` or double-click |
| .rpm | `dist/aquile-reader-0.1.0-1.preview.noarch.rpm` | ~84K | Fedora/RHEL: `sudo dnf install` |
| AppImage | `dist/AquileReader-0.1.0-preview-x86_64.AppImage` | ~1M | Any distro, no install: `chmod +x` + run |
| tarball | `dist/aquile-reader-0.1.0-preview.tar.gz` | ~85K | Portable: unpack + `./install.sh` to `~/.local` |

Rebuild everything: `bash scripts/build_deb.sh && bash scripts/build_rpm.sh && bash scripts/build_appimage.sh && bash scripts/build_tarball.sh`

## Prerequisites (all formats)

Host packages: `python3`, `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`,
`gir1.2-poppler-0.18`. On Ubuntu:

```sh
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-poppler-0.18
```

The AppImage uses host Python/GTK (fails with a clear message if missing);
it is not a fully bundled image. FUSE is needed to run AppImages directly;
without FUSE use `./AquileReader-*.AppImage --appimage-extract` and run
`squashfs-root/AppRun`.

## .deb (Ubuntu)

```sh
sudo dpkg -i dist/aquile-reader_0.1.0-preview_amd64.deb
sudo apt-get install -f   # only if dependency errors appear
aquile-reader [book.epub]
```

Unsigned preview — do not present as an auto-update source.

## .rpm (Fedora/RHEL family)

```sh
sudo dnf install dist/aquile-reader-0.1.0-1.preview.noarch.rpm
aquile-reader [book.epub]
```

Requires names target Fedora/RHEL (`gtk4`, `libadwaita`, `poppler-glib`);
other RPM distros may need mapping. Unsigned preview.

## AppImage

```sh
chmod +x dist/AquileReader-0.1.0-preview-x86_64.AppImage
./dist/AquileReader-0.1.0-preview-x86_64.AppImage [book.epub]
```

## Tarball (no root)

```sh
tar xzf dist/aquile-reader-0.1.0-preview.tar.gz
cd aquile-reader-0.1.0-preview && ./install.sh   # installs to ~/.local
aquile-reader                  # ensure ~/.local/bin is on PATH
# or run unpacked: ./bin/aquile-reader [book file]
```

## File associations

All formats register `application/epub+zip`, `application/pdf`, CBZ/CBR MIME
types without stealing defaults. Right-click a book → Open With → Aquile Reader,
or run `aquile-reader path/to/book.epub` directly.

## Data & privacy

Books, annotations, and settings stay in XDG user dirs (`~/.local/share`,
`~/.config`) on your machine. No account, no telemetry. Network is used only
when you explicitly open catalogs/dictionary/voices features.
