"""
Grouped Collections view for Aquile Reader (B0 UI_RESEARCH section 6).

Clean-room re-implementation: filter dropdown (All / Notes / Highlights /
Bookmarks), "Show only favorites" check, per-book groups (cover, title,
author, dates, collapse chevron) and rows with a colored type dot,
``location » section`` + timestamp, right-aligned progress %, click-to-jump
via callback.

Annotation-type heuristic (the domain model carries no explicit type):
- note_text non-empty  -> "note" (Notes)
- empty text_content    -> "bookmark" (Bookmarks, location-only marker)
- otherwise             -> "highlight" (Highlights)

Favorites: the Book model carries no favorite flag yet, so the check reads
an optional ``is_favorite`` / ``favorite`` attribute (default False) and is
forward-compatible once the model gains one.
"""

from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple
import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

FILTER_OPTIONS = ("All", "Notes", "Highlights", "Bookmarks")

TYPE_NAMES = {
    "note": "Notes",
    "highlight": "Highlights",
    "bookmark": "Bookmarks",
}

TYPE_COLORS = {
    "note": "#2196F3",
    "highlight": "#FFC107",
    "bookmark": "#4CAF50",
}


def annotation_type(ann) -> str:
    """Classify an annotation as 'note', 'highlight', or 'bookmark'."""
    if getattr(ann, "note_text", ""):
        return "note"
    if not getattr(ann, "text_content", ""):
        return "bookmark"
    return "highlight"


def is_favorite(book) -> bool:
    """Best-effort favorite flag (Book has no favorite field yet)."""
    return bool(
        getattr(book, "is_favorite", getattr(book, "favorite", False))
    )


def format_timestamp(created_at: float) -> str:
    """Format an epoch timestamp for row display."""
    try:
        return datetime.fromtimestamp(float(created_at)).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OverflowError, OSError):
        return ""


class CollectionsView(Gtk.Box):
    """Per-book grouped annotations browser with type filter + jump callback."""

    def __init__(
        self,
        book_repo=None,
        ann_repo=None,
        progress_repo=None,
        on_jump_to_book: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.book_repo = book_repo
        self.ann_repo = ann_repo
        self.progress_repo = progress_repo
        self.on_jump_to_book = on_jump_to_book

        # Test-visible state: book_id -> Gtk.Expander group, plus flat row list
        # of (book, annotation, Adw.ActionRow) tuples.
        self._groups: Dict[str, Gtk.Expander] = {}
        self._rows: List[Tuple] = []

        self.add_css_class("collections-view")
        self._build_ui()
        self.refresh()

    # -- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)

        self.filter_dropdown = Gtk.DropDown.new_from_strings(list(FILTER_OPTIONS))
        self.filter_dropdown.set_tooltip_text("Filter by annotation type")
        self.filter_dropdown.connect("notify::selected", lambda *_: self.refresh())
        toolbar.append(self.filter_dropdown)

        self.favorites_check = Gtk.CheckButton(label="Show only favorites")
        self.favorites_check.connect("toggled", lambda *_: self.refresh())
        toolbar.append(self.favorites_check)
        self.append(toolbar)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        self.append(scrolled)

        self.groups_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.groups_box.set_margin_start(12)
        self.groups_box.set_margin_end(12)
        self.groups_box.set_margin_bottom(12)
        scrolled.set_child(self.groups_box)

        self.empty_page = Adw.StatusPage()
        self.empty_page.set_title("No Annotations Yet")
        self.empty_page.set_description(
            "Highlights, notes, and bookmarks created while reading "
            "will appear here grouped by book."
        )
        self.empty_page.set_icon_name("emblem-favorite-symbolic")

    # -- Filtering helpers ------------------------------------------------
    def get_filter(self) -> str:
        """Return the active filter name (one of FILTER_OPTIONS)."""
        selected = self.filter_dropdown.get_selected()
        if 0 <= selected < len(FILTER_OPTIONS):
            return FILTER_OPTIONS[selected]
        return "All"

    def set_filter(self, name: str) -> None:
        """Select a filter by name (test helper; triggers refresh)."""
        if name in FILTER_OPTIONS:
            self.filter_dropdown.set_selected(FILTER_OPTIONS.index(name))

    def set_show_favorites(self, show: bool) -> None:
        """Set the favorites-only check (test helper; triggers refresh)."""
        self.favorites_check.set_active(show)

    def get_groups(self) -> Dict[str, Gtk.Expander]:
        """Return the currently visible per-book groups keyed by book id."""
        return dict(self._groups)

    def get_visible_rows(self) -> List[Tuple]:
        """Return visible (book, annotation, row) tuples."""
        return list(self._rows)

    # -- Data --------------------------------------------------------------
    def _iter_books(self):
        if self.book_repo is not None:
            try:
                return list(self.book_repo.list_all())
            except Exception:
                return []
        return []

    def _annotations_for(self, book_id: str):
        if self.ann_repo is None:
            return []
        try:
            if hasattr(self.ann_repo, "get_by_book"):
                return list(self.ann_repo.get_by_book(book_id))
            return [a for a in self.ann_repo.list_all() if a.book_id == book_id]
        except Exception:
            return []

    def _progress_percent(self, book_id: str) -> Optional[float]:
        if self.progress_repo is None:
            return None
        try:
            prog = self.progress_repo.get(book_id)
            if prog is not None:
                return float(prog.percentage)
        except Exception:
            pass
        return None

    # -- Refresh ------------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild per-book groups from repositories under active filters."""
        while child := self.groups_box.get_first_child():
            self.groups_box.remove(child)
        self._groups.clear()
        self._rows.clear()

        active_filter = self.get_filter()
        only_favorites = self.favorites_check.get_active()

        shown = 0
        for book in self._iter_books():
            if only_favorites and not is_favorite(book):
                continue
            annotations = self._annotations_for(book.id)
            visible = [
                a for a in annotations
                if active_filter == "All"
                or TYPE_NAMES[annotation_type(a)] == active_filter
            ]
            if not visible:
                continue
            group = self._build_group(book, visible)
            self.groups_box.append(group)
            self._groups[book.id] = group
            shown += len(visible)

        if shown == 0:
            self.groups_box.append(self.empty_page)

    def _build_group(self, book, annotations) -> Gtk.Expander:
        group = Gtk.Expander(expanded=True)
        group.add_css_class("collections-group")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_margin_start(4)
        header.set_margin_end(4)
        header.set_margin_top(4)
        header.set_margin_bottom(4)

        cover = self._build_cover(book)
        header.append(cover)

        meta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        meta.set_hexpand(True)
        title = Gtk.Label(label=book.title)
        title.add_css_class("group-title")
        title.set_halign(Gtk.Align.START)
        title.set_wrap(True)
        meta.append(title)
        author = Gtk.Label(label=f"by {getattr(book, 'author', 'Unknown Author')}")
        author.add_css_class("group-subtitle")
        author.set_halign(Gtk.Align.START)
        meta.append(author)
        dates = Gtk.Label(label=self._dates_line(book))
        dates.add_css_class("group-subtitle")
        dates.set_halign(Gtk.Align.START)
        meta.append(dates)
        header.append(meta)

        # Collapse chevron (Expander toggles on header click; arrow mirrors state)
        chevron = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        chevron.set_valign(Gtk.Align.CENTER)
        header.append(chevron)
        group.connect(
            "notify::expanded",
            lambda exp, _ps: chevron.set_from_icon_name(
                "pan-down-symbolic" if exp.get_expanded() else "pan-end-symbolic"
            ),
        )

        group.set_label_widget(header)

        rows = Gtk.ListBox()
        rows.add_css_class("boxed-list")
        rows.set_selection_mode(Gtk.SelectionMode.NONE)
        for ann in annotations:
            row = self._build_row(book, ann)
            rows.append(row)
            self._rows.append((book, ann, row))
        group.set_child(rows)
        return group

    def _build_cover(self, book) -> Gtk.Widget:
        cover_path = getattr(book, "cover_path", None)
        if cover_path and os.path.exists(cover_path):
            try:
                picture = Gtk.Picture.new_for_filename(cover_path)
                picture.set_size_request(48, 64)
                picture.set_can_shrink(True)
                return picture
            except Exception:
                pass
        icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
        icon.set_pixel_size(48)
        return icon

    @staticmethod
    def _dates_line(book) -> str:
        added = format_timestamp(getattr(book, "added_at", 0.0) or 0.0)
        last_read = getattr(book, "last_read_at", None)
        last = format_timestamp(last_read) if last_read else "never"
        return f"Date added: {added} • Last read: {last}"

    def _build_row(self, book, ann) -> Adw.ActionRow:
        ann_type = annotation_type(ann)
        color = getattr(ann, "color", None) or TYPE_COLORS[ann_type]
        if ann_type != "highlight":
            color = TYPE_COLORS[ann_type]

        location = f"Chapter {int(getattr(ann, 'chapter_index', 0)) + 1}"
        cfi = getattr(ann, "cfi", "")
        if cfi:
            location += f" » {cfi}"
        stamp = format_timestamp(getattr(ann, "created_at", 0.0) or 0.0)
        subtitle = f"{location} • {stamp}" if stamp else location
        if getattr(ann, "note_text", ""):
            subtitle += f"\nNote: {ann.note_text}"

        text = (getattr(ann, "text_content", "") or "").strip()
        row = Adw.ActionRow(activatable=True)
        row.set_title(f'"{text[:160]}"' if text else f"({TYPE_NAMES[ann_type][:-1]})")
        row.set_subtitle(subtitle)

        dot = Gtk.Label()
        dot.set_markup(f'<span foreground="{color}">●</span>')
        dot.set_tooltip_text(TYPE_NAMES[ann_type])
        row.add_prefix(dot)

        pct = self._progress_percent(book.id)
        if pct is not None:
            pct_label = Gtk.Label(label=f"{pct:.1f}%")
            pct_label.set_halign(Gtk.Align.END)
            row.add_suffix(pct_label)
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))

        row.connect("activated", lambda _r, b=book, a=ann: self._emit_jump(b, a))
        return row

    def _emit_jump(self, book, annotation) -> None:
        if self.on_jump_to_book is None:
            return
        # Callback receives (book, annotation); tolerate single-arg callbacks.
        try:
            self.on_jump_to_book(book, annotation)
        except TypeError:
            self.on_jump_to_book(book)
