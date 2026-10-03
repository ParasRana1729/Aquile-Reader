"""
Settings and Customization Dialog for Aquile Reader.
Controls theme, columns, font family, font size, and line height (FR-09, FR-16).
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from ..domain.models import (
    ACCENT_LABELS,
    ACCENT_THEMES,
    PAGE_THEME_LABELS,
    PAGE_THEMES,
    AppSettings,
    validate_accent_name,
    validate_page_theme,
)
from ..storage.repository import SettingsRepository

# Re-exported single-source vocabulary (WP-C): identical objects to
# reader_chrome.PAGE_THEMES / ACCENT_THEMES so both UIs always agree.
__all__ = ["SettingsDialog", "PAGE_THEMES", "PAGE_THEME_LABELS", "ACCENT_THEMES"]

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

        # Theme Selector (shared WP-C vocabulary: white/silver/sepia/...).
        self.theme_row = Adw.ComboRow(title="Theme")
        theme_model = Gtk.StringList.new(PAGE_THEME_LABELS)
        self.theme_row.set_model(theme_model)
        try:
            theme_idx = list(PAGE_THEMES).index(self.settings.theme)
        except ValueError:
            theme_idx = 0
        self.theme_row.set_selected(theme_idx)
        self.theme_row.connect("notify::selected", self._on_theme_changed)
        appearance_group.add(self.theme_row)

        # Accent (color theme) selector (shared WP-C vocabulary).
        self.accent_row = Adw.ComboRow(title="Accent")
        accent_names = list(ACCENT_THEMES.keys())
        accent_labels = [ACCENT_LABELS[name] for name in accent_names]
        self.accent_row.set_model(Gtk.StringList.new(accent_labels))
        try:
            accent_idx = accent_names.index(getattr(self.settings, "accent", "turquoise"))
        except ValueError:
            accent_idx = 0
        self.accent_row.set_selected(accent_idx)
        self.accent_row.connect("notify::selected", self._on_accent_changed)
        appearance_group.add(self.accent_row)

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

        # Font Family (AppSettings.font_family was persisted but had no UI row)
        self.font_row = Adw.ComboRow(title="Font Family")
        font_model = Gtk.StringList.new(["Sans", "Serif", "Monospace", "Cantarell", "Noto Serif", "Liberation Serif"])
        self.font_row.set_model(font_model)
        try:
            font_idx = list(["Sans", "Serif", "Monospace", "Cantarell", "Noto Serif", "Liberation Serif"]).index(self.settings.font_family)
        except ValueError:
            font_idx = 0
        self.font_row.set_selected(font_idx)
        self.font_row.connect("notify::selected", self._on_font_changed)
        type_group.add(self.font_row)

        # Margins (AppSettings.margin_percent was persisted but had no UI row)
        margin_row = Adw.ActionRow(title="Margins (%)")
        self.margin_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 20, 1)
        self.margin_scale.set_value(self.settings.margin_percent)
        self.margin_scale.set_hexpand(True)
        self.margin_scale.set_draw_value(True)
        self.margin_scale.connect("value-changed", self._on_margin_changed)
        margin_row.add_suffix(self.margin_scale)
        type_group.add(margin_row)

        # Reset group
        reset_group = Adw.PreferencesGroup(title="Defaults")
        page.add(reset_group)
        reset_row = Adw.ActionRow(title="Reset to defaults")
        btn_reset = Gtk.Button(label="Reset")
        btn_reset.connect("clicked", self._on_reset_clicked)
        reset_row.add_suffix(btn_reset)
        reset_group.add(reset_row)

    def _on_theme_changed(self, combo, _):
        idx = combo.get_selected()
        if 0 <= idx < len(PAGE_THEMES):
            self.settings.theme = validate_page_theme(PAGE_THEMES[idx])
            self._notify_change()

    def _on_accent_changed(self, combo, _):
        idx = combo.get_selected()
        names = list(ACCENT_THEMES.keys())
        if 0 <= idx < len(names):
            self.settings.accent = validate_accent_name(names[idx])
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

    def _on_font_changed(self, combo, _):
        fonts = ["Sans", "Serif", "Monospace", "Cantarell", "Noto Serif", "Liberation Serif"]
        self.settings.font_family = fonts[combo.get_selected()]
        self._notify_change()

    def _on_margin_changed(self, scale):
        self.settings.margin_percent = int(scale.get_value())
        self._notify_change()

    def _on_reset_clicked(self, button):
        from ..domain.models import AppSettings
        self.settings = AppSettings()
        self.settings_repo.save(self.settings)
        try:
            self.theme_row.set_selected(list(PAGE_THEMES).index(self.settings.theme))
        except ValueError:
            self.theme_row.set_selected(0)
        self.column_row.set_selected(0)
        self.font_size_scale.set_value(self.settings.font_size)
        self.line_height_scale.set_value(self.settings.line_height)
        self.font_row.set_selected(0)
        self.margin_scale.set_value(self.settings.margin_percent)
        try:
            self.accent_row.set_selected(
                list(ACCENT_THEMES.keys()).index(self.settings.accent))
        except ValueError:
            self.accent_row.set_selected(0)
        if self.on_changed_callback:
            self.on_changed_callback(self.settings)

    def _notify_change(self):
        self.settings_repo.save(self.settings)
        if self.on_changed_callback:
            self.on_changed_callback(self.settings)
