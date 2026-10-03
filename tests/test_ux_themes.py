"""
WP-C theme-unification tests (UX_PLAN_V3.md sections 2-3, defect D3).

Pins the single shared theme vocabulary:
- page themes: white/silver/sepia/night/solarized/custom (models.PAGE_THEMES
  is the source of truth, re-exported identically by settings_dialog and
  reader_chrome);
- accent themes: turquoise/vineyard/darkside/clearsky/pulpyorange
  (models.ACCENT_THEMES name->hex map, single source of truth);
- AppSettings gains `accent` (default 'turquoise') + `transparency`
  (default 0);
- every page theme persists via SettingsRepository roundtrip and maps to a
  root CSS class in reader_view.ReaderView.PAGE_THEME_CLASSES;
- schema migration v3->v4 keeps existing settings rows.
"""

import os
import re
import sqlite3
import tempfile
import unittest

from src.aquile.domain import models
from src.aquile.domain.models import AppSettings
from src.aquile.storage.database import CURRENT_SCHEMA_VERSION, Database
from src.aquile.storage.repository import SettingsRepository

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

EXPECTED_PAGE_THEMES = ["white", "silver", "sepia", "night", "solarized", "custom"]
EXPECTED_ACCENTS = {"turquoise", "vineyard", "darkside", "clearsky", "pulpyorange"}


def _temp_settings_repo():
    tmp = tempfile.TemporaryDirectory()
    db = Database(os.path.join(tmp.name, "ux_themes.db"))
    return tmp, SettingsRepository(db)


class TestThemeVocabulary(unittest.TestCase):
    def test_models_has_accent_field_default_turquoise(self):
        s = AppSettings()
        self.assertEqual(s.accent, "turquoise")

    def test_models_has_transparency_field_default_zero(self):
        s = AppSettings()
        self.assertEqual(s.transparency, 0)

    def test_models_page_themes_vocabulary(self):
        self.assertEqual(list(models.PAGE_THEMES), EXPECTED_PAGE_THEMES)

    def test_accent_map_has_required_names_and_turquoise_hex(self):
        accent_map = getattr(models, "ACCENT_THEMES", None)
        self.assertIsNotNone(accent_map, "models.ACCENT_THEMES missing")
        self.assertTrue(EXPECTED_ACCENTS.issubset(set(accent_map.keys())))
        self.assertEqual(accent_map["turquoise"], "#009688")

    def test_each_accent_hex_is_valid_rrggbb(self):
        for name, hex_color in models.ACCENT_THEMES.items():
            with self.subTest(accent=name):
                self.assertRegex(hex_color, HEX_RE)
                self.assertEqual(models.validate_accent_hex(hex_color), hex_color)

    def test_page_vocabulary_identical_in_both_ui_modules(self):
        from src.aquile.ui import reader_chrome, settings_dialog
        for mod in (reader_chrome, settings_dialog):
            with self.subTest(module=mod.__name__):
                self.assertEqual(list(mod.PAGE_THEMES), EXPECTED_PAGE_THEMES)
                self.assertEqual(list(mod.PAGE_THEME_LABELS),
                                 list(models.PAGE_THEME_LABELS))

    def test_accent_vocabulary_single_sourced_in_both_ui_modules(self):
        from src.aquile.ui import reader_chrome, settings_dialog
        for mod in (reader_chrome, settings_dialog):
            with self.subTest(module=mod.__name__):
                self.assertIs(mod.ACCENT_THEMES, models.ACCENT_THEMES)


class TestThemePersistence(unittest.TestCase):
    def test_each_page_theme_persists_roundtrip(self):
        tmp, repo = _temp_settings_repo()
        try:
            for theme in EXPECTED_PAGE_THEMES:
                with self.subTest(theme=theme):
                    repo.save(AppSettings(theme=theme))
                    self.assertEqual(repo.load().theme, theme)
        finally:
            tmp.cleanup()

    def test_each_page_theme_maps_to_root_css_class(self):
        from src.aquile.ui.reader_view import ReaderView
        css_map = ReaderView.PAGE_THEME_CLASSES
        for theme in EXPECTED_PAGE_THEMES:
            with self.subTest(theme=theme):
                classes = css_map.get(theme)
                self.assertIsNotNone(classes, f"no CSS class for {theme!r}")
                self.assertTrue(len(classes) >= 1)
                for cls in classes:
                    self.assertTrue(isinstance(cls, str) and len(cls) > 0)

    def test_each_accent_persists_roundtrip(self):
        tmp, repo = _temp_settings_repo()
        try:
            for name in sorted(EXPECTED_ACCENTS):
                with self.subTest(accent=name):
                    repo.save(AppSettings(accent=name))
                    reloaded = repo.load()
                    self.assertEqual(reloaded.accent, name)
                    self.assertRegex(models.ACCENT_THEMES[reloaded.accent], HEX_RE)
        finally:
            tmp.cleanup()

    def test_invalid_page_theme_rejected(self):
        with self.assertRaises(ValueError):
            models.validate_page_theme("neon")
        from src.aquile.ui.reader_chrome import ReaderDisplayPopover
        tmp, repo = _temp_settings_repo()
        try:
            popover = ReaderDisplayPopover(AppSettings(), repo)
            with self.assertRaises(ValueError):
                popover.set_theme("neon")
        finally:
            tmp.cleanup()

    def test_invalid_accent_rejected(self):
        with self.assertRaises(ValueError):
            models.validate_accent_name("neon")
        with self.assertRaises(ValueError):
            models.validate_accent_hex("not-a-color")
        tmp, repo = _temp_settings_repo()
        try:
            with self.assertRaises(ValueError):
                repo.save(AppSettings(accent="neon"))
        finally:
            tmp.cleanup()

    def test_transparency_clamped_zero_to_100(self):
        self.assertEqual(models.clamp_transparency(150), 100)
        self.assertEqual(models.clamp_transparency(-20), 0)
        self.assertEqual(models.clamp_transparency(42), 42)
        tmp, repo = _temp_settings_repo()
        try:
            repo.save(AppSettings(transparency=150))
            self.assertEqual(repo.load().transparency, 100)
            repo.save(AppSettings(transparency=-5))
            self.assertEqual(repo.load().transparency, 0)
        finally:
            tmp.cleanup()

    def test_migration_v3_to_v4_keeps_existing_settings(self):
        self.assertEqual(CURRENT_SCHEMA_VERSION, 4)
        tmp = tempfile.TemporaryDirectory()
        try:
            legacy_path = os.path.join(tmp.name, "legacy_v3.db")
            conn = sqlite3.connect(legacy_path)
            conn.executescript("""
                CREATE TABLE books (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE, file_format TEXT NOT NULL,
                    cover_path TEXT, total_chapters INTEGER DEFAULT 1,
                    file_size_bytes INTEGER DEFAULT 0, added_at REAL NOT NULL,
                    last_read_at REAL, is_favorite INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE reading_progress (
                    book_id TEXT PRIMARY KEY, chapter_index INTEGER NOT NULL DEFAULT 0,
                    page_index INTEGER NOT NULL DEFAULT 0, cfi TEXT NOT NULL DEFAULT '',
                    percentage REAL NOT NULL DEFAULT 0.0, updated_at REAL NOT NULL
                );
                CREATE TABLE annotations (
                    id TEXT PRIMARY KEY, book_id TEXT NOT NULL, chapter_index INTEGER NOT NULL,
                    cfi TEXT NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
                    text_content TEXT NOT NULL, note_text TEXT DEFAULT '',
                    color TEXT NOT NULL DEFAULT '#FFEB3B', created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                PRAGMA user_version = 3;
            """)
            conn.execute("INSERT INTO settings VALUES (?, ?)", ("theme", "sepia"))
            conn.execute("INSERT INTO settings VALUES (?, ?)", ("font_size", "22"))
            conn.commit()
            conn.close()

            migrated = Database(legacy_path)
            with migrated.get_connection() as c:
                version = c.execute("PRAGMA user_version;").fetchone()[0]
            self.assertEqual(version, 4)
            reloaded = SettingsRepository(migrated).load()
            self.assertEqual(reloaded.theme, "sepia")
            self.assertEqual(reloaded.font_size, 22)
            self.assertEqual(reloaded.accent, "turquoise")
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
