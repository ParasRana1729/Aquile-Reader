"""
Annotation and Bookmark Dialog for Aquile Reader.
Allows adding notes and highlights to the reading location (FR-10).
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
from typing import Callable, Optional
from ..domain.models import Annotation

class AnnotationDialog(Adw.Window):
    def __init__(self, parent_window, selected_text: str, on_save_callback: Callable[[str, str], None]):
        super().__init__()
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_title("Add Note or Bookmark")
        self.set_default_size(440, 360)

        self.selected_text = selected_text
        self.on_save_callback = on_save_callback
        self.selected_color = "#FFEB3B"

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        self.set_content(box)

        # HeaderBar with Save & Cancel
        header = Adw.HeaderBar()
        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.connect("clicked", lambda b: self.close())
        header.pack_start(btn_cancel)

        btn_save = Gtk.Button(label="Save")
        btn_save.add_css_class("suggested-action")
        btn_save.connect("clicked", self._on_save_clicked)
        header.pack_end(btn_save)
        box.append(header)

        # Text preview
        preview_label = Gtk.Label()
        preview_label.set_wrap(True)
        preview_label.set_xalign(0)
        snippet = (selected_text[:120] + "...") if len(selected_text) > 120 else selected_text
        preview_label.set_text(f'"{snippet}"')
        preview_label.add_css_class("italic")
        box.append(preview_label)

        # Note entry
        lbl_note = Gtk.Label(label="Personal Note:")
        lbl_note.set_xalign(0)
        box.append(lbl_note)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        scrolled.set_child(self.text_view)
        box.append(scrolled)

    def _on_save_clicked(self, button):
        buffer = self.text_view.get_buffer()
        start, end = buffer.get_bounds()
        note_text = buffer.get_text(start, end, True).strip()
        self.on_save_callback(note_text, self.selected_color)
        self.close()
