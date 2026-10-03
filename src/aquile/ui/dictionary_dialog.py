"""
Offline-first dictionary dialog for Aquile Reader.

Adw.Window with a SearchEntry, a language combo (en/fr/es/de), a results
Gtk.ListBox, and a status label (FR-13, FR-20, NFR-04).

Privacy: the queried text is never written to logs; only word length,
language, and error types are recorded.
"""

import logging
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

try:
    from ..reader.dictionary import (
        DEFAULT_TIMEOUT,
        Definition,
        DictionaryService,
        LookupCancelledError,
        NoDefinitionError,
        ProviderUnavailableError,
    )
except (ImportError, ValueError):
    try:
        from aquile.reader.dictionary import (
            DEFAULT_TIMEOUT,
            Definition,
            DictionaryService,
            LookupCancelledError,
            NoDefinitionError,
            ProviderUnavailableError,
        )
    except (ImportError, ValueError):  # pragma: no cover - import fallback
        DEFAULT_TIMEOUT = 5.0
        Definition = object  # type: ignore[misc,assignment]
        DictionaryService = object  # type: ignore[misc,assignment]

        class NoDefinitionError(LookupError):
            """Fallback no-result error."""

        class ProviderUnavailableError(ConnectionError):
            """Fallback provider error."""

        class LookupCancelledError(Exception):
            """Fallback cancellation error."""

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("en", "fr", "es", "de")

STATUS_IDLE = "Type a word and press Enter."
STATUS_SEARCHING = "Looking up…"
STATUS_NO_DEFINITION = (
    "No definition found for this term. Try another word or language. "
    "Local reading is unaffected."
)
STATUS_PROVIDER_UNAVAILABLE = (
    "Dictionary provider unavailable — check your connection and retry. "
    "Local reading is unaffected."
)
STATUS_CANCELLED = "Lookup cancelled. Local reading is unaffected."
STATUS_INVALID = "Enter a word to look up."


class DictionaryDialog(Adw.Window):
    """Modal dictionary lookup window with offline-first behavior."""

    def __init__(self, parent_window=None, dictionary_service=None) -> None:
        super().__init__()
        self.dictionary_service = (
            dictionary_service if dictionary_service is not None else self._default_service()
        )
        self.lookup_timeout: float = float(DEFAULT_TIMEOUT)
        self._last_results: list = []
        self._lookup_seq: int = 0

        if parent_window is not None:
            try:
                self.set_transient_for(parent_window)
            except Exception:
                pass
        self.set_modal(True)
        self.set_title("Dictionary")
        self.set_default_size(480, 560)
        self.add_css_class("dictionary-dialog")

        self._build_ui()
        self._set_status(STATUS_IDLE)

    @staticmethod
    def _default_service():
        """Builds a default offline DictionaryService when available."""
        try:
            factory = DictionaryService
            if isinstance(factory, type):
                return factory()
        except Exception:
            logger.debug("dictionary dialog default service unavailable")
        return None

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(content)

        self.header = Adw.HeaderBar()
        content.append(self.header)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        body.set_margin_start(12)
        body.set_margin_end(12)
        body.set_margin_top(12)
        body.set_margin_bottom(12)
        body.set_vexpand(True)
        content.append(body)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        body.append(search_row)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Look up a word…")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self._on_search_activated)
        search_row.append(self.search_entry)

        self.lang_dropdown = Gtk.DropDown.new_from_strings(list(SUPPORTED_LANGUAGES))
        self.lang_dropdown.set_tooltip_text("Language")
        self.lang_dropdown.set_selected(0)
        search_row.append(self.lang_dropdown)

        self.lookup_button = Gtk.Button(label="Look up")
        self.lookup_button.connect("clicked", self._on_lookup_clicked)
        search_row.append(self.lookup_button)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        body.append(scrolled)

        self.results_list = Gtk.ListBox()
        self.results_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.results_list)

        self.status_label = Gtk.Label(label=STATUS_IDLE)
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_wrap(True)
        self.status_label.set_xalign(0.0)
        body.append(self.status_label)

    # -- public API ----------------------------------------------------------

    def get_language(self) -> str:
        """Returns the currently selected language code."""
        try:
            index = int(self.lang_dropdown.get_selected())
        except Exception:
            return "en"
        if 0 <= index < len(SUPPORTED_LANGUAGES):
            return SUPPORTED_LANGUAGES[index]
        return "en"

    def set_language(self, lang: str) -> str:
        """Selects a supported language code; unknown codes fall back to 'en'."""
        normalized = str(lang or "en").strip().lower().replace("_", "-").split("-")[0]
        if normalized not in SUPPORTED_LANGUAGES:
            normalized = "en"
        self.lang_dropdown.set_selected(SUPPORTED_LANGUAGES.index(normalized))
        return normalized

    def get_status_text(self) -> str:
        """Returns the current status label text (for tests)."""
        try:
            return str(self.status_label.get_label())
        except Exception:
            return ""

    def get_result_count(self) -> int:
        """Returns the number of definition rows currently shown."""
        return len(self._last_results)

    def get_results(self) -> list:
        """Returns the definitions from the most recent successful lookup."""
        return list(self._last_results)

    def lookup_word(self, word, lang=None, allow_online: bool = False, timeout=None):
        """
        Synchronous lookup with a timeout; updates results and status.

        Returns the Definition on success, else None. Distinguishes the
        no-definition case from provider failures in the status label.
        Never logs the queried text itself.
        """
        active_lang = lang if lang is not None else self.get_language()
        lang_norm = (
            str(active_lang or "en").strip().lower().replace("_", "-").split("-")[0] or "en"
        )
        try:
            query_len = len(str(word or "").strip())
        except Exception:
            query_len = 0
        effective_timeout = self.lookup_timeout if timeout is None else timeout
        try:
            effective_timeout = float(effective_timeout)
        except (TypeError, ValueError):
            effective_timeout = float(DEFAULT_TIMEOUT)

        service = self.dictionary_service
        lookup = getattr(service, "lookup", None) if service is not None else None
        if not callable(lookup):
            logger.debug("dictionary lookup unavailable: lang=%s", lang_norm)
            self._show_error(STATUS_PROVIDER_UNAVAILABLE)
            return None

        logger.debug(
            "dictionary dialog lookup: word_len=%d lang=%s", query_len, lang_norm
        )
        try:
            result = lookup(word, lang_norm, allow_online, effective_timeout)
        except NoDefinitionError:
            logger.debug("dictionary dialog no result: lang=%s", lang_norm)
            self._show_error(STATUS_NO_DEFINITION)
            return None
        except ProviderUnavailableError:
            logger.debug("dictionary dialog provider unavailable: lang=%s", lang_norm)
            self._show_error(STATUS_PROVIDER_UNAVAILABLE)
            return None
        except LookupCancelledError:
            logger.debug("dictionary dialog lookup cancelled: lang=%s", lang_norm)
            self._show_error(STATUS_CANCELLED)
            return None
        except (ValueError, LookupError):
            # InvalidQueryError subclasses ValueError; other lookup errors
            # mean no usable result without implying a provider outage.
            logger.debug("dictionary dialog invalid query: lang=%s", lang_norm)
            self._show_error(STATUS_INVALID)
            return None
        except Exception:
            logger.debug("dictionary dialog lookup failed: lang=%s", lang_norm)
            self._show_error(STATUS_PROVIDER_UNAVAILABLE)
            return None

        definitions = list(getattr(result, "definitions", None) or [])
        if not definitions:
            self._show_error(STATUS_NO_DEFINITION)
            return None
        self._show_result(result)
        return result

    # -- async path (GLib thread) --------------------------------------------

    def _on_lookup_clicked(self, _button: Gtk.Button) -> None:
        self._submit_current_query()

    def _on_search_activated(self, entry: Gtk.SearchEntry) -> None:
        self._submit_current_query()

    def _submit_current_query(self) -> None:
        try:
            word = str(self.search_entry.get_text() or "")
        except Exception:
            word = ""
        if not word.strip():
            self._set_status(STATUS_INVALID)
            return
        lang = self.get_language()
        self._set_status(STATUS_SEARCHING)
        self._lookup_seq += 1
        seq = self._lookup_seq
        thread = threading.Thread(
            target=self._lookup_in_thread,
            args=(word, lang, seq),
            daemon=True,
        )
        thread.start()

    def _lookup_in_thread(self, word: str, lang: str, seq: int) -> None:
        service = self.dictionary_service
        lookup = getattr(service, "lookup", None) if service is not None else None
        if not callable(lookup):
            GLib.idle_add(self._apply_async_error, seq, STATUS_PROVIDER_UNAVAILABLE)
            return
        try:
            result = lookup(word, lang, False, self.lookup_timeout)
        except NoDefinitionError:
            GLib.idle_add(self._apply_async_error, seq, STATUS_NO_DEFINITION)
            return
        except ProviderUnavailableError:
            GLib.idle_add(self._apply_async_error, seq, STATUS_PROVIDER_UNAVAILABLE)
            return
        except LookupCancelledError:
            GLib.idle_add(self._apply_async_error, seq, STATUS_CANCELLED)
            return
        except (ValueError, LookupError):
            GLib.idle_add(self._apply_async_error, seq, STATUS_INVALID)
            return
        except Exception:
            GLib.idle_add(self._apply_async_error, seq, STATUS_PROVIDER_UNAVAILABLE)
            return
        if not list(getattr(result, "definitions", None) or []):
            GLib.idle_add(self._apply_async_error, seq, STATUS_NO_DEFINITION)
            return
        GLib.idle_add(self._apply_async_result, seq, result)

    def _apply_async_error(self, seq: int, message: str) -> bool:
        if seq == self._lookup_seq:
            self._show_error(message)
        return False

    def _apply_async_result(self, seq: int, result) -> bool:
        if seq == self._lookup_seq:
            self._show_result(result)
        return False

    # -- rendering -------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        try:
            self.status_label.set_label(message)
        except Exception:
            pass

    def _clear_results(self) -> None:
        self._last_results = []
        try:
            while True:
                row = self.results_list.get_row_at_index(0)
                if row is None:
                    break
                self.results_list.remove(row)
        except Exception:
            pass

    def _show_result(self, result) -> None:
        self._clear_results()
        try:
            word = str(getattr(result, "word", "") or "")
            pos = str(getattr(result, "part_of_speech", "") or "")
            source = str(getattr(result, "source", "") or "")
            header_text = word
            if pos:
                header_text += f" — {pos}"
            if source:
                header_text += f" ({source})"
            header = Gtk.Label(label=header_text or "Definition")
            header.set_halign(Gtk.Align.START)
            header.set_xalign(0.0)
            header_row = Gtk.ListBoxRow(child=header)
            header_row.set_selectable(False)
            self.results_list.append(header_row)

            for text in list(getattr(result, "definitions", None) or []):
                body = Gtk.Label(label=str(text))
                body.set_wrap(True)
                body.set_halign(Gtk.Align.START)
                body.set_xalign(0.0)
                row = Gtk.ListBoxRow(child=body)
                row.set_selectable(False)
                self.results_list.append(row)
            self._last_results = [result]
        except Exception:
            self._show_error(STATUS_PROVIDER_UNAVAILABLE)
            return
        self._set_status(f"Found {len(list(getattr(result, 'definitions', None) or []))} definition(s).")

    def _show_error(self, message: str) -> None:
        self._clear_results()
        self._set_status(message)
