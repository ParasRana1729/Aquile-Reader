"""Aquile-style Home view: Recent Reads + Favourite Books.

Clean-room re-implementation of the layout/behavior notes in
``docs/reference/B0/UI_RESEARCH.md`` §2 (Home):

- ``Recent Reads`` section: grid of large covers with rounded corners +
  soft shadows (``.cover-card``), first cover rendered large.
- ``Favourite Books`` section: books flagged
  ``getattr(book, 'is_favorite', False)``.
- Footer links ``Open Library ›`` / ``See more ›`` invoking callbacks.
- ``+`` button top-right (imports go through the library callback).

Covers show a ``Gtk.Picture`` when ``book.cover_path`` points at a real
file, otherwise a title tile. Clicking a card opens the book via
``on_open_book``. :meth:`refresh` repopulates both sections from the
repositories.
"""

import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .icon_loader import load as _load_icon, path_for as _icon_path_for

#: Standard card size; the first recent cover is rendered larger.
COVER_SIZE = (128, 180)
COVER_SIZE_LARGE = (184, 256)

#: Maximum number of cards shown in Recent Reads.
MAX_RECENTS = 12


def recent_sort_key(book) -> float:
    """Order key for Recent Reads: last-read, falling back to added-at."""
    stamp = getattr(book, "last_read_at", None) or getattr(book, "added_at", 0) or 0
    try:
        return float(stamp)
    except (TypeError, ValueError):
        return 0.0


def is_favorite(book) -> bool:
    """A book is a favourite only when flagged via ``is_favorite``."""
    return bool(getattr(book, "is_favorite", False))


class HomeView(Gtk.Box):
    """Home screen with Recent Reads + Favourite Books sections."""

    def __init__(self, book_repo, progress_repo, on_open_book=None,
                 on_open_library=None, on_see_more=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.book_repo = book_repo
        self.progress_repo = progress_repo
        self.on_open_book = on_open_book
        self.on_open_library = on_open_library
        self.on_see_more = on_see_more
        self.max_recents = MAX_RECENTS
        self._build_ui()
        self.refresh()

    # -- construction -------------------------------------------------
    def _build_ui(self):
        self.add_css_class("home-view")

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header.set_margin_start(16)
        header.set_margin_end(16)
        header.set_margin_top(12)
        header.set_margin_bottom(4)
        title = Gtk.Label(label="Home")
        title.add_css_class("home-h1")
        title.set_xalign(0.0)
        title.set_hexpand(True)
        header.append(title)
        self.add_button = Gtk.Button(icon_name="list-add-symbolic")
        self.add_button.set_tooltip_text("Add books (open library)")
        self.add_button.connect("clicked", self._on_open_library)
        header.append(self.add_button)
        self.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(8)
        content.set_margin_bottom(8)
        content.set_spacing(8)
        scrolled.set_child(content)
        self.append(scrolled)

        self.recent_title = self._section_label(content, "Recent Reads")
        self.recent_flow = Gtk.FlowBox()
        self.recent_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        content.append(self.recent_flow)
        self.recent_empty_label = Gtk.Label(
            label="No recent reads yet — open a book from your library.")
        self.recent_empty_label.add_css_class("home-empty")
        content.append(self.recent_empty_label)

        self.fav_title = self._section_label(content, "Favourite Books")
        self.fav_flow = Gtk.FlowBox()
        self.fav_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        content.append(self.fav_flow)
        self.fav_empty_label = Gtk.Label(label="No favourite books yet.")
        self.fav_empty_label.add_css_class("home-empty")
        content.append(self.fav_empty_label)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer.set_margin_start(16)
        footer.set_margin_end(16)
        footer.set_margin_top(4)
        footer.set_margin_bottom(12)
        self.open_library_button = Gtk.Button(label="Open Library ›")
        self.open_library_button.add_css_class("home-link")
        self.open_library_button.connect("clicked", self._on_open_library)
        footer.append(self.open_library_button)
        spacer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        spacer.set_hexpand(True)
        footer.append(spacer)
        self.see_more_button = Gtk.Button(label="See more ›")
        self.see_more_button.add_css_class("home-link")
        self.see_more_button.connect("clicked", self._on_see_more)
        footer.append(self.see_more_button)
        self.append(footer)

    @staticmethod
    def _section_label(parent, text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.add_css_class("home-h1")
        label.set_xalign(0.0)
        parent.append(label)
        return label

    # -- data ---------------------------------------------------------
    def refresh(self) -> None:
        """Repopulate both sections from the book repository."""
        try:
            books = list(self.book_repo.list_all() or [])
        except Exception:
            books = []
        recents = sorted(books, key=recent_sort_key, reverse=True)
        recents = recents[: self.max_recents]
        favorites = [b for b in books if is_favorite(b)]
        self._fill_flow(self.recent_flow, recents, large_first=True)
        self._fill_flow(self.fav_flow, favorites, large_first=False)
        self.recent_empty_label.set_visible(len(recents) == 0)
        self.fav_empty_label.set_visible(len(favorites) == 0)

    def _fill_flow(self, flow: Gtk.FlowBox, books, large_first: bool) -> None:
        child = flow.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            flow.remove(child)
            child = nxt
        for index, book in enumerate(books):
            flow.append(self._make_card(book, large=large_first and index == 0))

    def _make_card(self, book, large: bool = False) -> Gtk.Button:
        width, height = COVER_SIZE_LARGE if large else COVER_SIZE
        card = Gtk.Button()
        card.add_css_class("cover-card")
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.START)
        card.set_tooltip_text(getattr(book, "title", "Untitled"))
        # Late binding over the loop variable: capture this book now.
        card.connect("clicked", lambda _btn, b=book: self._on_card_clicked(b))
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame.set_spacing(4)
        cover_path = getattr(book, "cover_path", None)
        if cover_path and os.path.isfile(cover_path):
            try:
                picture = Gtk.Picture.new_for_filename(cover_path)
            except Exception:
                picture = None
            if picture is not None:
                picture.set_content_fit(Gtk.ContentFit.COVER)
                picture.set_size_request(width, height)
                picture.add_css_class("cover-image")
                frame.append(picture)
            else:
                frame.append(self._tile(getattr(book, "title", "?"), width, height))
        else:
            frame.append(self._tile(getattr(book, "title", "?"), width, height))
        title_label = Gtk.Label(label=getattr(book, "title", "Untitled"))
        title_label.add_css_class("book-title")
        title_label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        title_label.set_max_width_chars(18)
        frame.append(title_label)
        author_label = Gtk.Label(
            label="by " + str(getattr(book, "author", "Unknown Author")))
        author_label.add_css_class("book-author")
        author_label.set_ellipsize(3)
        author_label.set_max_width_chars(20)
        frame.append(author_label)
        card.set_child(frame)
        return card

    @staticmethod
    def _tile(text: str, width: int, height: int) -> Gtk.Label:
        tile = Gtk.Label(label=text or "?")
        tile.add_css_class("cover-tile")
        tile.set_size_request(width, height)
        tile.set_wrap(True)
        tile.set_max_width_chars(14)
        return tile

    # -- callbacks ----------------------------------------------------
    def _on_card_clicked(self, book) -> None:
        if self.on_open_book is not None:
            self.on_open_book(book)

    def _on_open_library(self, _button) -> None:
        if self.on_open_library is not None:
            self.on_open_library()

    def _on_see_more(self, _button) -> None:
        if self.on_see_more is not None:
            self.on_see_more()
