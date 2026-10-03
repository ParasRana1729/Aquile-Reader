"""
Settings and Customization Dialog for Aquile Reader.
Controls theme, columns, font family, font size, and line height (FR-09, FR-16).
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from ..domain.models import AppSettings
from ..storage.repository import SettingsRepository

class SettingsDialog(Adw.PreferencesWindow):
    def __init__(self, parent_window, settings: AppSettings, settings_repo: SettingsRepository, on_changed_callback=None):
        super().__init__()
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_title("Reader Settings")
        self.set_default_size(480, 500)

        self.settings = settings
        self.settings_repo = settings_repo
        self.on_changed_callback = on_changed_callback

        page = Adw.PreferencesPage()
        self.add(page)

        # 1. Appearance Group
        appearance_group = Adw.PreferencesGroup(title="Appearance & Theme")
        page.add(appearance_group)

        # Theme Selector
        self.theme_row = Adw.ComboRow(title="Theme")
        theme_model = Gtk.StringList.new(["Light", "Dark", "Sepia"])
        self.theme_row.set_model(theme_model)
        theme_idx = {"light": 0, "dark": 1, "sepia": 2}.get(self.settings.theme, 0)
        self.theme_row.set_selected(theme_idx)
        self.theme_row.connect("notify::selected", self._on_theme_changed)
        appearance_group.add(self.theme_row)

        # Column Layout (Signature Aquile Reader Two-Column Feature)
        self.column_row = Adw.ComboRow(title="Page Layout")
        col_model = Gtk.StringList.new(["Two Columns (Aquile Default)", "Single Column"])
        self.column_row.set_model(col_model)
        self.column_row.set_selected(0 if self.settings.columns == 2 else 1)
        self.column_row.connect("notify::selected", self._on_column_changed)
        appearance_group.add(self.column_row)

        # 2. Typography Group
        type_group = Adw.PreferencesGroup(title="Typography")
        page.add(type_group)

        # Font Size
        font_size_row = Adw.ActionRow(title="Font Size")
        self.font_size_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 12, 32, 1)
        self.font_size_scale.set_value(self.settings.font_size)
        self.font_size_scale.set_hexpand(True)
        self.font_size_scale.set_draw_value(True)
        self.font_size_scale.connect("value-changed", self._on_font_size_changed)
        font_size_row.add_suffix(self.font_size_scale)
        type_group.add(font_size_row)

        # Line Spacing
        line_height_row = Adw.ActionRow(title="Line Spacing")
        self.line_height_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1.2, 2.4, 0.1)
        self.line_height_scale.set_value(self.settings.line_height)
        self.line_height_scale.set_hexpand(True)
        self.line_height_scale.set_draw_value(True)
        self.line_height_scale.connect("value-changed", self._on_line_height_changed)
        line_height_row.add_suffix(self.line_height_scale)
        type_group.add(line_height_row)

    def _on_theme_changed(self, combo, _):
        idx = combo.get_selected()
        themes = ["light", "dark", "sepia"]
        self.settings.theme = themes[idx]
        self._notify_change()

    def _on_column_changed(self, combo, _):
        idx = combo.get_selected()
        self.settings.columns = 2 if idx == 0 else 1
        self._notify_change()

    def _on_font_size_changed(self, scale):
        self.settings.font_size = int(scale.get_value())
        self._notify_change()

    def _on_line_height_changed(self, scale):
        self.settings.line_height = round(scale.get_value(), 2)
        self._notify_change()

    def _notify_change(self):
        self.settings_repo.save(self.settings)
        if self.on_changed_callback:
            self.on_changed_callback(self.settings)
