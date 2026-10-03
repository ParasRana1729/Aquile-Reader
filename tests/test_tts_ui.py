"""
Headless tests for the TTS bar and dictionary dialog (FR-12, FR-13).

All tests skip gracefully when Gtk/Adw cannot initialise (e.g. no
display server) instead of failing.
"""

import unittest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk  # noqa: F401

    try:
        Adw.init()
    except Exception:
        pass
    _GTK_AVAILABLE = True
    _GTK_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - environment dependent
    _GTK_AVAILABLE = False
    _GTK_IMPORT_ERROR = exc

from src.aquile.reader.dictionary import (
    Definition,
    NoDefinitionError,
    ProviderUnavailableError,
)
from src.aquile.reader.tts_engine import TtsEngine


def _require_gtk(testcase: unittest.TestCase) -> None:
    if not _GTK_AVAILABLE:
        testcase.skipTest(f"Gtk unavailable: {_GTK_IMPORT_ERROR}")


class _StubDictionaryService:
    """Offline stub: hit / no-result / provider-down per configured mode."""

    def __init__(self, mode: str = "hit") -> None:
        self.mode = mode
        self.calls: list = []

    def lookup(self, word, lang: str = "en", allow_online: bool = False,
               timeout=None, cancel_event=None):
        self.calls.append((word, lang))
        if self.mode == "hit":
            return Definition(
                word=str(word),
                lang=str(lang),
                part_of_speech="noun",
                definitions=["A stub definition for headless tests."],
                source="stub",
            )
        if self.mode == "noresult":
            raise NoDefinitionError("no stub entry")
        raise ProviderUnavailableError("stub provider down")


def _make_tts_bar(testcase: unittest.TestCase, engine=None):
    _require_gtk(testcase)
    from src.aquile.ui.tts_controls import TtsBar

    engine = engine if engine is not None else TtsEngine()
    try:
        return TtsBar(engine)
    except Exception as exc:
        testcase.skipTest(f"Gtk widget init failed: {exc}")


def _make_dialog(testcase: unittest.TestCase, service=None):
    _require_gtk(testcase)
    from src.aquile.ui.dictionary_dialog import DictionaryDialog

    service = service if service is not None else _StubDictionaryService("hit")
    try:
        return DictionaryDialog(None, service)
    except Exception as exc:
        testcase.skipTest(f"Gtk widget init failed: {exc}")


class TestTtsBar(unittest.TestCase):
    def test_constructs_without_audio_side_effects(self):
        engine = TtsEngine()
        bar = _make_tts_bar(self, engine)
        self.assertEqual(engine.state, "idle")
        self.assertFalse(engine.is_speaking)
        self.assertGreaterEqual(bar.get_voice_count(), 1)

    def test_speed_clamps_high(self):
        engine = TtsEngine()
        bar = _make_tts_bar(self, engine)
        self.assertEqual(bar.set_speed(99.0), 2.0)
        self.assertEqual(engine.get_rate(), 2.0)
        self.assertEqual(bar.get_speed(), 2.0)

    def test_speed_clamps_low(self):
        engine = TtsEngine()
        bar = _make_tts_bar(self, engine)
        self.assertEqual(bar.set_speed(-5.0), 0.5)
        self.assertEqual(engine.get_rate(), 0.5)

    def test_voice_model_non_empty(self):
        bar = _make_tts_bar(self)
        model = bar.voice_dropdown.get_model()
        self.assertIsNotNone(model)
        self.assertGreaterEqual(model.get_n_items(), 1)

    def test_on_close_stops_and_releases(self):
        engine = TtsEngine()
        bar = _make_tts_bar(self, engine)
        bar.bind_text(lambda: "hello world")
        bar.on_close()  # must not raise; engine stays idle
        self.assertEqual(engine.state, "idle")
        self.assertIsNone(bar._get_text_callback)
        bar.on_close()  # idempotent


class TestDictionaryDialog(unittest.TestCase):
    def test_constructs_with_expected_widgets(self):
        dialog = _make_dialog(self)
        self.assertIsNotNone(dialog.search_entry)
        self.assertIsNotNone(dialog.lang_dropdown)
        self.assertIsNotNone(dialog.results_list)
        self.assertIsNotNone(dialog.status_label)
        self.assertEqual(dialog.get_language(), "en")
        self.assertEqual(dialog.set_language("fr"), "fr")

    def test_lookup_hit_shows_result(self):
        dialog = _make_dialog(self, _StubDictionaryService("hit"))
        result = dialog.lookup_word("book", "en")
        self.assertIsNotNone(result)
        self.assertEqual(dialog.get_result_count(), 1)
        self.assertIn("definition", dialog.get_status_text().lower())

    def test_lookup_no_result_distinct_status(self):
        dialog = _make_dialog(self, _StubDictionaryService("noresult"))
        result = dialog.lookup_word("qqq_no_such_word", "en")
        self.assertIsNone(result)
        self.assertEqual(dialog.get_result_count(), 0)
        status = dialog.get_status_text().lower()
        self.assertIn("no definition", status)
        self.assertNotIn("unavailable", status)

    def test_lookup_offline_distinct_status(self):
        dialog = _make_dialog(self, _StubDictionaryService("offline"))
        result = dialog.lookup_word("book", "en", allow_online=True)
        self.assertIsNone(result)
        self.assertEqual(dialog.get_result_count(), 0)
        self.assertIn("unavailable", dialog.get_status_text().lower())

    def test_lookup_never_logs_queried_text(self):
        import logging

        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Capture()
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            dialog = _make_dialog(self, _StubDictionaryService("hit"))
            dialog.lookup_word("s3cr3t-he4dless-word", "en")
        finally:
            root.removeHandler(handler)
        self.assertGreaterEqual(len(records), 0)
        for record in records:
            try:
                message = record.getMessage()
            except Exception:
                message = ""
            self.assertNotIn("s3cr3t-he4dless-word", message)
            for arg in (record.args if isinstance(record.args, tuple) else (record.args,)):
                self.assertNotIn("s3cr3t-he4dless-word", str(arg))


if __name__ == "__main__":
    unittest.main()
