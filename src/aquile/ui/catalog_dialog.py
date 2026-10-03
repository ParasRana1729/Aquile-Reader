"""
OPDS catalog browser dialog for Aquile Reader (FR-14, FR-20).

Offline-first: constructing this dialog performs no network I/O. All
network activity (feed discovery, downloads) is explicit and user-invoked
via buttons. Failures surface truthful status text and never touch the
local library.
"""

import os
import tempfile
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

try:
    from ..catalog.catalog_manager import CatalogManager
    from ..catalog.opds_client import (
        CancelledError,
        NetworkError,
        OpdsClient,
        UnsupportedContentError,
    )
except (ImportError, ValueError):
    try:
        from aquile.catalog.catalog_manager import CatalogManager
        from aquile.catalog.opds_client import (
            CancelledError,
            NetworkError,
            OpdsClient,
            UnsupportedContentError,
        )
    except ImportError:  # `src.` layout when running tests from repo root.
        from src.aquile.catalog.catalog_manager import CatalogManager
        from src.aquile.catalog.opds_client import (
            CancelledError,
            NetworkError,
            OpdsClient,
            UnsupportedContentError,
        )


def _default_download_dir() -> str:
    downloads = os.path.expanduser("~/Downloads")
    if os.path.isdir(downloads):
        return downloads
    return tempfile.gettempdir()


class CatalogDialog(Adw.Window):
    """Modal OPDS catalog browser: manage feeds, search, download books."""

    def __init__(
        self,
        parent_window=None,
        catalog_manager=None,
        on_import_file_callback=None,
        download_dir=None,
        client=None,
    ):
        super().__init__()
        self.catalog_manager = catalog_manager or CatalogManager()
        self.on_import_file_callback = on_import_file_callback
        self.download_dir = download_dir or _default_download_dir()
        self.client = client or OpdsClient()

        # Local-only state; no network happens here.
        self._current_entries = []
        self._cancel_tokens = {}  # entry_id -> {"cancelled": bool}
        self._result_widgets = {}  # entry_id -> dict of row widgets
        self._feed_urls = []  # parallel to feed ListBox rows

        if parent_window is not None:
            try:
                self.set_transient_for(parent_window)
            except Exception:
                pass
        self.set_modal(True)
        self.set_title("Book Catalogs")
        self.set_default_size(560, 640)
        self.add_css_class("catalog-dialog")

        self._build_ui()
        self.refresh_feeds()  # local registry read only; no network.

    # -- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content)

        self.header = Adw.HeaderBar()
        content.append(self.header)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        content.append(page)

        # Feeds group: URL entry + add/remove feed list.
        feeds_group = Adw.PreferencesGroup(title="Catalog Feeds")
        page.add(feeds_group)

        url_row = Adw.ActionRow(title="Add OPDS feed")
        url_row.set_subtitle("Paste an http(s) OPDS catalog URL")
        self.feed_url_entry = Gtk.Entry()
        self.feed_url_entry.set_placeholder_text("https://example.org/opds")
        self.feed_url_entry.set_hexpand(True)
        self.feed_url_entry.connect("activate", self._on_add_feed)
        url_row.add_suffix(self.feed_url_entry)
        self.add_feed_button = Gtk.Button(label="Add")
        self.add_feed_button.connect("clicked", self._on_add_feed)
        url_row.add_suffix(self.add_feed_button)
        feeds_group.add(url_row)

        self.feed_listbox = Gtk.ListBox()
        self.feed_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.feed_listbox.add_css_class("boxed-list")
        feeds_group.add(self.feed_listbox)

        load_row = Adw.ActionRow(title="Selected feed")
        load_row.set_subtitle("Load entries for the selected catalog")
        self.load_feed_button = Gtk.Button(label="Load Catalog")
        self.load_feed_button.connect("clicked", self._on_load_feed)
        load_row.add_suffix(self.load_feed_button)
        feeds_group.add(load_row)

        # Browse group: local search over discovered entries.
        browse_group = Adw.PreferencesGroup(title="Browse Catalog")
        page.add(browse_group)

        search_row = Adw.ActionRow(title="Search")
        search_row.set_subtitle("Filters already-loaded entries; works offline")
        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search title or author…")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self._on_search)
        search_row.add_suffix(self.search_entry)
        self.search_button = Gtk.Button(label="Search")
        self.search_button.connect("clicked", self._on_search)
        search_row.add_suffix(self.search_button)
        browse_group.add(search_row)

        # Results group: ListBox with download button per row.
        results_group = Adw.PreferencesGroup(title="Results")
        page.add(results_group)
        self.results_listbox = Gtk.ListBox()
        self.results_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.results_listbox.add_css_class("boxed-list")
        results_group.add(self.results_listbox)

        # Status group: truthful local status / error text.
        status_group = Adw.PreferencesGroup(title="Status")
        page.add(status_group)
        status_row = Adw.ActionRow(title="Catalog status")
        self.status_label = Gtk.Label(label="No catalog loaded yet.")
        self.status_label.set_wrap(True)
        self.status_label.set_xalign(0.0)
        self.status_label.set_hexpand(True)
        status_row.add_suffix(self.status_label)
        status_group.add(status_row)

    # -- status ----------------------------------------------------------

    def set_status(self, text: str) -> None:
        self.status_label.set_text(text)

    def status_text(self) -> str:
        return self.status_label.get_text()

    # -- feeds (local-only, via CatalogManager) --------------------------

    def refresh_feeds(self) -> None:
        while True:
            row = self.feed_listbox.get_row_at_index(0)
            if row is None:
                break
            self.feed_listbox.remove(row)
        self._feed_urls = []
        try:
            feeds = self.catalog_manager.list_feeds()
        except Exception as exc:
            self.set_status(f"Cannot list catalogs: {exc}")
            return
        for feed in feeds:
            self._append_feed_row(feed)
        first = self.feed_listbox.get_row_at_index(0)
        if first is not None:
            self.feed_listbox.select_row(first)

    def _append_feed_row(self, feed: dict) -> None:
        name = str(feed.get("name", "") or feed.get("url", ""))
        url = str(feed.get("url", ""))
        feed_id = str(feed.get("id", "") or url)
        row = Gtk.ListBoxRow()
        row.feed_url = url
        row.feed_id = feed_id
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        title = Gtk.Label(label=name)
        title.set_xalign(0.0)
        url_label = Gtk.Label(label=url)
        url_label.set_xalign(0.0)
        url_label.add_css_class("dim-label")
        labels.append(title)
        labels.append(url_label)
        box.append(labels)
        remove_btn = Gtk.Button(label="Remove")
        remove_btn.set_tooltip_text(f"Remove {name}")
        remove_btn.connect("clicked", self._on_remove_feed, feed_id)
        box.append(remove_btn)
        row.set_child(box)
        self.feed_listbox.append(row)
        self._feed_urls.append(url)

    def get_feed_count(self) -> int:
        count = 0
        while self.feed_listbox.get_row_at_index(count) is not None:
            count += 1
        return count

    def _on_add_feed(self, _widget) -> None:
        url = self.feed_url_entry.get_text().strip()
        if not url:
            self.set_status("Enter a catalog URL first.")
            return
        try:
            record = self.catalog_manager.add_feed(url)
        except ValueError as exc:
            self.set_status(f"Cannot add catalog: {exc}")
            return
        except Exception as exc:
            self.set_status(f"Cannot add catalog: {exc}")
            return
        self.feed_url_entry.set_text("")
        self.refresh_feeds()
        self.set_status(f"Added catalog '{record.get('name', url)}'.")

    def _on_remove_feed(self, _button, feed_id: str) -> None:
        try:
            removed = self.catalog_manager.remove_feed(feed_id)
        except Exception as exc:
            self.set_status(f"Cannot remove catalog: {exc}")
            return
        if not removed:
            self.set_status("That catalog cannot be removed (built-in or unknown).")
            return
        self.refresh_feeds()
        self.set_status("Removed catalog.")

    # -- discovery / search (explicit user-invoked network) --------------

    def _selected_feed_url(self):
        row = self.feed_listbox.get_selected_row()
        if row is not None and getattr(row, "feed_url", ""):
            return row.feed_url
        if self._feed_urls:
            return self._feed_urls[0]
        return ""

    def _on_load_feed(self, _button) -> None:
        url = (self._selected_feed_url() or "").strip()
        if not url:
            self.set_status("No catalog selected.")
            return
        self.set_status(f"Loading catalog…")
        self.load_feed_button.set_sensitive(False)
        thread = threading.Thread(
            target=self._discover_worker, args=(url,), daemon=True
        )
        thread.start()

    def _discover_worker(self, url: str) -> None:
        try:
            entries = self.client.discover(url)
        except (NetworkError, UnsupportedContentError) as exc:
            GLib.idle_add(self._on_discover_failed, f"Catalog unavailable: {exc}")
            return
        except Exception as exc:
            GLib.idle_add(self._on_discover_failed, f"Catalog unavailable: {exc}")
            return
        GLib.idle_add(self._on_discover_done, entries)

    def _on_discover_failed(self, message: str) -> None:
        self.load_feed_button.set_sensitive(True)
        self.set_status(message)

    def _on_discover_done(self, entries) -> None:
        self.load_feed_button.set_sensitive(True)
        self._current_entries = list(entries or [])
        self.render_results(self._current_entries)
        if not self._current_entries:
            self.set_status("Catalog loaded: no downloadable books found.")
        else:
            self.set_status(
                f"Catalog loaded: {len(self._current_entries)} book(s) found."
            )

    def _on_search(self, _widget) -> None:
        query = self.search_entry.get_text()
        try:
            hits = self.client.search(query)
        except Exception as exc:
            self.set_status(f"Search failed: {exc}")
            return
        self._current_entries = list(hits)
        self.render_results(self._current_entries)
        if not self._current_entries:
            self.set_status("No matches in the loaded catalog.")
        else:
            self.set_status(f"{len(self._current_entries)} match(es).")

    # -- results + downloads ---------------------------------------------

    def get_result_count(self) -> int:
        count = 0
        while self.results_listbox.get_row_at_index(count) is not None:
            count += 1
        return count

    def render_results(self, entries) -> None:
        while True:
            row = self.results_listbox.get_row_at_index(0)
            if row is None:
                break
            self.results_listbox.remove(row)
        self._result_widgets.clear()
        for entry in entries or []:
            self._append_result_row(entry if isinstance(entry, dict) else {})

    def _append_result_row(self, entry: dict) -> None:
        entry_id = str(entry.get("id", "") or entry.get("title", ""))
        title = str(entry.get("title", "") or "Untitled")
        author = str(entry.get("author", "") or "Unknown author")
        fmt = str(entry.get("format", "") or "").upper()

        row = Gtk.ListBoxRow()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        title_label = Gtk.Label(label=title)
        title_label.set_xalign(0.0)
        title_label.set_wrap(True)
        subtitle = f"{author} · {fmt}" if fmt else author
        sub_label = Gtk.Label(label=subtitle)
        sub_label.set_xalign(0.0)
        sub_label.add_css_class("dim-label")
        labels.append(title_label)
        labels.append(sub_label)
        top.append(labels)

        has_file = bool(entry.get("acquisition_url") or entry.get("download_url")
                         or entry.get("url"))
        dl_btn = Gtk.Button(label="Download")
        dl_btn.set_sensitive(has_file)
        if not has_file:
            dl_btn.set_tooltip_text("No downloadable file for this entry")
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.set_visible(False)
        top.append(dl_btn)
        top.append(cancel_btn)
        outer.append(top)

        progress = Gtk.ProgressBar()
        progress.set_visible(False)
        progress.set_show_text(True)
        outer.append(progress)

        dl_btn.connect("clicked", self._on_download_clicked, dict(entry))
        cancel_btn.connect("clicked", self._on_cancel_clicked, entry_id)

        row.set_child(outer)
        self.results_listbox.append(row)
        self._result_widgets[entry_id] = {
            "download_button": dl_btn,
            "cancel_button": cancel_btn,
            "progress": progress,
        }

    def _on_download_clicked(self, button, entry: dict) -> None:
        entry_id = str(entry.get("id", "") or entry.get("title", ""))
        widgets = self._result_widgets.get(entry_id, {})
        token = {"cancelled": False}
        self._cancel_tokens[entry_id] = token
        button.set_sensitive(False)
        if widgets.get("cancel_button") is not None:
            widgets["cancel_button"].set_visible(True)
        if widgets.get("progress") is not None:
            widgets["progress"].set_visible(True)
            widgets["progress"].set_fraction(0.0)
            widgets["progress"].set_text("Starting…")
        self.set_status(f"Downloading '{entry.get('title', 'book')}'…")
        thread = threading.Thread(
            target=self._download_worker, args=(dict(entry), token), daemon=True
        )
        thread.start()

    def _on_cancel_clicked(self, _button, entry_id: str) -> None:
        token = self._cancel_tokens.get(entry_id)
        if token is not None:
            token["cancelled"] = True
        self.set_status("Cancelling download…")

    def _download_worker(self, entry: dict, token: dict) -> None:
        entry_id = str(entry.get("id", "") or entry.get("title", ""))

        def _progress(downloaded: int, total) -> None:
            GLib.idle_add(self._update_progress, entry_id, downloaded, total)

        try:
            path = self.client.download(
                entry, self.download_dir, progress_cb=_progress,
                cancel_token=token,
            )
        except CancelledError:
            GLib.idle_add(self._on_download_done, entry_id, "", "Download cancelled.")
            return
        except (NetworkError, UnsupportedContentError) as exc:
            GLib.idle_add(
                self._on_download_done, entry_id, "", f"Download failed: {exc}"
            )
            return
        except Exception as exc:
            GLib.idle_add(
                self._on_download_done, entry_id, "", f"Download failed: {exc}"
            )
            return
        GLib.idle_add(
            self._on_download_done, entry_id, path,
            f"Downloaded '{entry.get('title', 'book')}'.",
        )

    def _update_progress(self, entry_id: str, downloaded: int, total) -> None:
        widgets = self._result_widgets.get(entry_id, {})
        bar = widgets.get("progress")
        if bar is None:
            return
        try:
            total_num = int(total) if total else 0
        except (TypeError, ValueError):
            total_num = 0
        if total_num > 0:
            frac = max(0.0, min(1.0, downloaded / total_num))
            bar.set_fraction(frac)
            bar.set_text(f"{downloaded // 1024} / {total_num // 1024} KiB")
        else:
            bar.pulse()
            bar.set_text(f"{downloaded // 1024} KiB")

    def _on_download_done(self, entry_id: str, path: str, message: str) -> None:
        widgets = self._result_widgets.get(entry_id, {})
        if widgets.get("cancel_button") is not None:
            widgets["cancel_button"].set_visible(False)
        if widgets.get("download_button") is not None:
            widgets["download_button"].set_sensitive(True)
        self._cancel_tokens.pop(entry_id, None)
        self.set_status(message)
        if path and self.on_import_file_callback is not None:
            try:
                self.on_import_file_callback(path)
            except Exception as exc:
                self.set_status(f"{message} Import failed: {exc}")
