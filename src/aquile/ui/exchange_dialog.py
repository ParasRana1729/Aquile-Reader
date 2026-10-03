"""
Local exchange dialog for Aquile Reader (FR-17 / FR-19, NFR-02).

Authorized local-only exchange: export a book's state to a user-carried
``.aquile.zip`` bundle (via ExchangeBundle) or import such a bundle back.
No cloud sync, no upload claims: status strings come from SyncState and
are exactly ``local-only`` / ``exported`` / ``imported``.
"""

import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

try:
    from ..sync.exchange import ExchangeBundle
    from ..sync.sync_state import InMemoryTokenStore, SyncState
except (ImportError, ValueError):
    try:
        from aquile.sync.exchange import ExchangeBundle
        from aquile.sync.sync_state import InMemoryTokenStore, SyncState
    except ImportError:  # `src.` layout when running tests from repo root.
        from src.aquile.sync.exchange import ExchangeBundle
        from src.aquile.sync.sync_state import InMemoryTokenStore, SyncState


class ExchangeDialog(Adw.Window):
    """Export/import local exchange bundles with truthful status."""

    def __init__(
        self,
        parent_window=None,
        book_repo=None,
        progress_repo=None,
        ann_repo=None,
        stats_repo=None,
        sync_state=None,
        token_store=None,
    ):
        super().__init__()
        self.book_repo = book_repo
        self.progress_repo = progress_repo
        self.ann_repo = ann_repo
        self.stats_repo = stats_repo
        self.sync_state = sync_state or SyncState()
        self.token_store = token_store or InMemoryTokenStore()

        self._book_ids = []

        if parent_window is not None:
            try:
                self.set_transient_for(parent_window)
            except Exception:
                pass
        self.set_modal(True)
        self.set_title("Sync & Exchange")
        self.set_default_size(480, 560)
        self.add_css_class("exchange-dialog")

        self._build_ui()
        self.refresh_books()
        self.update_status_label()

    # -- UI construction -------------------------------------------------

    def _build_ui(self) -> None:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content)

        self.header = Adw.HeaderBar()
        content.append(self.header)

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        content.append(page)

        # Book picker group.
        book_group = Adw.PreferencesGroup(title="Book to Export")
        page.add(book_group)
        self.book_combo_row = Adw.ComboRow(title="Book")
        self.book_combo_row.set_subtitle("Local books only; nothing is uploaded")
        book_group.add(self.book_combo_row)

        # Local exchange group.
        exchange_group = Adw.PreferencesGroup(title="Local Exchange")
        page.add(exchange_group)

        export_row = Adw.ActionRow(title="Export bundle")
        export_row.set_subtitle("Save a .aquile.zip file you carry yourself")
        self.export_button = Gtk.Button(label="Export…")
        self.export_button.connect("clicked", self._on_export_clicked)
        export_row.add_suffix(self.export_button)
        exchange_group.add(export_row)

        import_row = Adw.ActionRow(title="Import bundle")
        import_row.set_subtitle("Merge a .aquile.zip file (newer-wins)")
        self.import_button = Gtk.Button(label="Import…")
        self.import_button.connect("clicked", self._on_import_clicked)
        import_row.add_suffix(self.import_button)
        exchange_group.add(import_row)

        # Status group.
        status_group = Adw.PreferencesGroup(title="Status")
        page.add(status_group)
        status_row = Adw.ActionRow(title="Sync status")
        self.status_label = Gtk.Label(label="local-only")
        self.status_label.set_wrap(True)
        self.status_label.set_xalign(0.0)
        self.status_label.set_hexpand(True)
        status_row.add_suffix(self.status_label)
        status_group.add(status_row)

        signout_row = Adw.ActionRow(title="Credentials")
        signout_row.set_subtitle("Clears stored tokens; books are kept")
        self.signout_button = Gtk.Button(label="Sign Out")
        self.signout_button.connect("clicked", self._on_signout_clicked)
        signout_row.add_suffix(self.signout_button)
        status_group.add(signout_row)

    # -- book list -------------------------------------------------------

    def refresh_books(self) -> None:
        books = []
        if self.book_repo is not None:
            try:
                books = list(self.book_repo.list_all() or [])
            except Exception:
                books = []
        self._book_ids = [getattr(b, "id", "") for b in books]
        if self._book_ids:
            titles = [
                f"{getattr(b, 'title', 'Untitled')}" for b in books
            ]
            self.book_combo_row.set_model(Gtk.StringList.new(titles))
            self.book_combo_row.set_selected(0)
            self.book_combo_row.set_sensitive(True)
        else:
            self.book_combo_row.set_model(Gtk.StringList.new(["No books available"]))
            self.book_combo_row.set_selected(0)
            self.book_combo_row.set_sensitive(False)

    def selected_book_id(self):
        idx = self.book_combo_row.get_selected()
        if 0 <= idx < len(self._book_ids):
            return self._book_ids[idx]
        return None

    # -- status (truthful local-only strings) ----------------------------

    def update_status_label(self) -> str:
        text = self.sync_state.describe()
        try:
            self.status_label.set_text(text)
        except Exception:
            pass
        return text

    def get_status_text(self) -> str:
        try:
            return self.status_label.get_text()
        except Exception:
            return self.sync_state.describe()

    # -- headless-testable core (no file chooser) ------------------------

    def export_to_path(self, book_id: str, dest_path: str) -> str:
        """Export one book to dest_path; returns the bundle path."""
        if not book_id:
            raise ValueError("No book selected for export")
        if self.book_repo is None or self.progress_repo is None \
                or self.ann_repo is None:
            raise ValueError("Exchange repositories are not configured")
        path = ExchangeBundle.export_book(
            book_id, self.book_repo, self.progress_repo, self.ann_repo,
            stats_repo=self.stats_repo, dest_path=dest_path,
        )
        self.sync_state.mark_exported()
        self.update_status_label()
        return path

    def import_from_path(self, zip_path: str) -> dict:
        """Import a bundle; returns the merge summary dict."""
        if not zip_path or not os.path.isfile(zip_path):
            raise ValueError(f"Bundle not found: {zip_path!r}")
        if self.book_repo is None or self.progress_repo is None \
                or self.ann_repo is None:
            raise ValueError("Exchange repositories are not configured")
        summary = ExchangeBundle.import_bundle(
            zip_path, self.book_repo, self.progress_repo, self.ann_repo,
            self.stats_repo,
        )
        self.sync_state.mark_imported()
        self.update_status_label()
        try:
            self.refresh_books()
        except Exception:
            pass
        return summary

    def do_sign_out(self) -> str:
        """Clear credentials; local books/annotations are retained."""
        self.sync_state.sign_out(self.token_store)
        return self.update_status_label()

    # -- file choosers (user-invoked only) -------------------------------

    def _on_export_clicked(self, _button) -> None:
        book_id = self.selected_book_id()
        if not book_id:
            self.status_label.set_text("local-only: no book selected for export")
            return
        dialog = Gtk.FileDialog()
        dialog.set_title("Save Exchange Bundle")
        dialog.set_initial_name(f"aquile-exchange-{book_id}.zip")
        try:
            dialog.save(self.get_root(), None, self._on_export_chosen, book_id)
        except Exception as exc:
            self.status_label.set_text(f"Cannot open save dialog: {exc}")

    def _on_export_chosen(self, dialog, result, book_id: str) -> None:
        try:
            gfile = dialog.save_finish(result)
        except Exception:
            return  # user cancelled
        if gfile is None:
            return
        try:
            self.export_to_path(book_id, gfile.get_path())
        except Exception as exc:
            self.status_label.set_text(f"Export failed: {exc}")

    def _on_import_clicked(self, _button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Open Exchange Bundle")
        bundle_filter = Gtk.FileFilter()
        bundle_filter.set_name("Aquile exchange (*.zip)")
        bundle_filter.add_pattern("*.zip")
        filters = dialog.get_filters()
        if filters is not None:
            filters.append(bundle_filter)
        else:
            from gi.repository import Gio
            store = Gio.ListStore.new(Gtk.FileFilter)
            store.append(bundle_filter)
            dialog.set_filters(store)
        try:
            dialog.open(self.get_root(), None, self._on_import_chosen)
        except Exception as exc:
            self.status_label.set_text(f"Cannot open file dialog: {exc}")

    def _on_import_chosen(self, dialog, result) -> None:
        try:
            gfile = dialog.open_finish(result)
        except Exception:
            return  # user cancelled
        if gfile is None:
            return
        try:
            summary = self.import_from_path(gfile.get_path())
        except Exception as exc:
            self.status_label.set_text(f"Import failed: {exc}")
            return
        added = summary.get("annotations_added", 0)
        updated = summary.get("annotations_updated", 0)
        base = self.get_status_text()
        self.status_label.set_text(
            f"{base} (+{added} note(s), ~{updated} updated)"
        )

    def _on_signout_clicked(self, _button) -> None:
        self.do_sign_out()
