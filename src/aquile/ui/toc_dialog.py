"""
Table of Contents Dialog for Aquile Reader.
Displays chapter navigation list (FR-08).
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from typing import List, Dict, Callable

class TocDialog(Adw.Window):
    def __init__(self, parent_window, toc_items: List[Dict[str, str]], on_select_chapter: Callable[[int], None]):
        super().__init__()
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_title("Table of Contents")
        self.set_default_size(400, 500)

        self.on_select_chapter = on_select_chapter

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)

        header = Adw.HeaderBar()
        box.append(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        box.append(scrolled)

        list_box = Gtk.ListBox()
        list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        list_box.add_css_class("boxed-list")
        list_box.set_margin_start(16)
        list_box.set_margin_end(16)
        list_box.set_margin_top(16)
        list_box.set_margin_bottom(16)
        scrolled.set_child(list_box)

        for idx, item in enumerate(toc_items):
            row = Adw.ActionRow()
            row.set_title(item["title"])
            row.set_activatable(True)
            row.connect("activated", self._make_activator(idx))
            list_box.append(row)

    def _make_activator(self, chapter_idx: int):
        def _activate(row):
            self.on_select_chapter(chapter_idx)
            self.close()
        return _activate
