"""
Opaque-box tests for WP-12 read-aloud (FR-12) and dictionary (FR-13).
Covers voice discovery, speed clamping, pause/resume, word-boundary
tracking, missing-voice errors, local hits, no-result handling, offline
truthfulness, language handling, log redaction, cancellation, cloud
consent, and state persistence. Headless-safe: stdlib only, no audio
hardware or network access required.
"""

import logging
import threading
import unittest
import urllib.error

from src.aquile.reader.tts_engine import (
    CloudVoiceConsentError,
    MissingVoiceError,
    TtsEngine,
    TtsError,
)
from src.aquile.reader.dictionary import (
    Definition,
    DictionaryService,
    LookupCancelledError,
    NoDefinitionError,
    ProviderUnavailableError,
)


class TestTtsEngine(unittest.TestCase):
    """Opaque-box tests for the read-aloud engine (FR-12, UB-08, FR-20)."""

    def test_voice_listing_returns_usable_voices_headless(self):
        """list_voices exposes at least one well-formed voice without audio hardware."""
        engine = TtsEngine()
        voices = engine.list_voices()
        self.assertGreaterEqual(len(voices), 1)
        for voice in voices:
            self.assertTrue(voice.id)
            self.assertTrue(voice.name)
            self.assertTrue(voice.lang)
            self.assertTrue(voice.engine)

    def test_speed_clamping_to_supported_range(self):
        """Rates clamp to 0.5x-2.0x on both the setter and the constructor."""
        engine = TtsEngine()
        self.assertEqual(engine.set_rate(10.0), 2.0)
        self.assertEqual(engine.get_rate(), 2.0)
        self.assertEqual(engine.set_rate(0.01), 0.5)
        self.assertEqual(engine.set_rate(-3.0), 0.5)
        self.assertEqual(engine.set_rate(1.25), 1.25)
        loud = TtsEngine(rate=99.0)
        self.assertEqual(loud.get_rate(), 2.0)
        quiet = TtsEngine(rate=0.0)
        self.assertEqual(quiet.get_rate(), 0.5)

    def test_pause_resume_state_transitions(self):
        """pause/resume move between speaking and paused; stop returns to idle."""
        engine = TtsEngine()
        try:
            engine.speak("hello brave world")
            self.assertEqual(engine.state, "speaking")
            self.assertTrue(engine.is_speaking)
            self.assertTrue(engine.pause())
            self.assertEqual(engine.state, "paused")
            self.assertTrue(engine.is_paused)
            self.assertTrue(engine.resume())
            self.assertEqual(engine.state, "speaking")
            self.assertFalse(engine.is_paused)
        finally:
            engine.stop()
        self.assertEqual(engine.state, "idle")
        self.assertFalse(engine.is_speaking)
        # Idempotent no-ops outside the active window must not raise.
        self.assertFalse(engine.pause())
        self.assertFalse(engine.resume())

    def test_text_tracking_word_boundary_indices(self):
        """Word-boundary callbacks report indices that slice the source text."""
        events = []
        engine = TtsEngine(on_word_boundary=lambda i, s, e: events.append((i, s, e)))
        text = "Hello brave world"
        try:
            spans = engine.speak(text)
        finally:
            engine.stop()
        self.assertEqual(len(spans), 3)
        self.assertEqual(events, spans)
        words = text.split()
        for index, start, end in spans:
            self.assertEqual(text[start:end], words[index])
            self.assertLess(start, end)
        self.assertEqual(engine.last_word_spans, spans)
        static = TtsEngine.get_word_boundaries("one  two")
        self.assertEqual(static, [(0, 0, 3), (1, 5, 8)])

    def test_missing_voice_error_with_recovery_path(self):
        """Unknown voices raise MissingVoiceError with a useful Ubuntu recovery path."""
        engine = TtsEngine()
        with self.assertRaises(MissingVoiceError) as ctx:
            engine.set_voice("no-such-voice-__wp12_test__")
        message = str(ctx.exception).lower()
        self.assertIn("not available", message)
        self.assertTrue(
            ("espeak" in message or "speech-dispatcher" in message or "available voices" in message),
            f"recovery path missing: {ctx.exception}",
        )
        with self.assertRaises(TtsError):
            engine.speak("hello", voice_id="no-such-voice-__wp12_test__")

    def test_cloud_voice_requires_explicit_consent(self):
        """Cloud synthesis stays disabled until explicit consent (UB-08)."""
        engine = TtsEngine()
        with self.assertRaises(CloudVoiceConsentError):
            engine.speak("hello cloud", use_cloud=True)
        engine.set_cloud_consent(True)
        try:
            spans = engine.speak("hello cloud", use_cloud=True)
        finally:
            engine.stop()
        self.assertEqual(len(spans), 2)

    def test_state_persistence_roundtrip(self):
        """get_state/restore_state preserve voice, rate, and position (UB-08)."""
        engine = TtsEngine()
        voice_id = engine.list_voices()[0].id
        engine.set_voice(voice_id)
        engine.set_rate(1.5)
        try:
            engine.speak("persist this position please")
            snapshot = engine.get_state()
        finally:
            engine.stop()
        self.assertEqual(snapshot["voice_id"], voice_id)
        self.assertEqual(snapshot["rate"], 1.5)
        restored = TtsEngine()
        restored.restore_state(snapshot)
        self.assertEqual(restored.get_rate(), 1.5)
        current = restored.get_voice()
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.id, voice_id)

    def test_tts_does_not_log_spoken_text(self):
        """Spoken book text never reaches logs (NFR-04)."""
        engine = TtsEngine()
        secret = "ZxqTtsSecretKq9"
        logger_name = "src.aquile.reader.tts_engine"
        with self.assertLogs(logger_name, level="DEBUG") as captured:
            try:
                engine.speak(f"{secret} spoken aloud here")
            finally:
                engine.stop()
        combined = "\n".join(captured.output)
        self.assertNotIn(secret, combined)


class TestDictionaryService(unittest.TestCase):
    """Opaque-box tests for the dictionary service (FR-13, FR-20, NFR-04)."""

    def test_dictionary_local_hit(self):
        """A stubbed local entry returns definitions without network use."""
        service = DictionaryService()
        result = service.lookup("book", "en")
        self.assertIsInstance(result, Definition)
        self.assertEqual(result.lang, "en")
        self.assertEqual(result.source, "local")
        self.assertGreaterEqual(len(result.definitions), 1)
        self.assertTrue(all(isinstance(entry, str) and entry for entry in result.definitions))

    def test_dictionary_no_result(self):
        """Unknown terms raise NoDefinitionError without touching the network."""
        service = DictionaryService()
        with self.assertRaises(NoDefinitionError):
            service.lookup("zxqjqv_nonexistent_word", "en")

    def test_dictionary_offline_failure_truthfulness(self):
        """Provider outages surface truthfully and never fabricate results."""
        offline_only = DictionaryService()
        with self.assertRaises(NoDefinitionError):
            offline_only.lookup("zxqjqv_nonexistent_word", "en", allow_online=False)

        def _failing_fetcher(word, lang, timeout, cancel_event=None):
            raise urllib.error.URLError("simulated offline")

        service = DictionaryService(online_fetcher=_failing_fetcher)
        with self.assertRaises(ProviderUnavailableError) as ctx:
            service.lookup("zxqjqv_nonexistent_word", "en", allow_online=True, timeout=1.0)
        message = str(ctx.exception).lower()
        self.assertTrue(
            ("unavailable" in message or "offline" in message or "connection" in message),
            f"error must be truthful about provider state: {ctx.exception}",
        )

    def test_dictionary_language_handling(self):
        """Language codes select entries; tags normalize case-insensitively."""
        service = DictionaryService()
        french = service.lookup("livre", "fr")
        self.assertEqual(french.lang, "fr")
        self.assertGreaterEqual(len(french.definitions), 1)
        with self.assertRaises(NoDefinitionError):
            service.lookup("livre", "en")
        normalized = service.lookup("book", "en-US")
        self.assertEqual(normalized.lang, "en")
        upper = service.lookup("BOOK", "EN")
        self.assertGreaterEqual(len(upper.definitions), 1)
        self.assertIn("en", service.available_languages())
        self.assertIn("fr", service.available_languages())

    def test_dictionary_redaction_no_word_in_logs(self):
        """Queried text never appears in log output (NFR-04)."""
        service = DictionaryService()
        token = "ZxqRedactKq7Unique"
        logger_name = "src.aquile.reader.dictionary"
        with self.assertLogs(logger_name, level="DEBUG") as captured:
            try:
                service.lookup(token, "en")
            except NoDefinitionError:
                pass
        combined = "\n".join(captured.output)
        self.assertNotIn(token, combined)

    def test_dictionary_lookup_cancellation(self):
        """A set cancel event aborts the lookup before any provider work."""
        service = DictionaryService()
        event = threading.Event()
        event.set()
        with self.assertRaises(LookupCancelledError):
            service.lookup("book", "en", cancel_event=event)


if __name__ == "__main__":
    unittest.main()
