"""
Offline-first dictionary lookup for Aquile Reader.
Serves local stub definitions synchronously and consults the open
Wiktionary REST API only on explicit request, with timeout, cancellation,
and truthful offline/provider errors (FR-13, FR-20, NFR-04).
"""

import json
import logging
import re
import urllib.parse
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_LANG_CODE_RE = re.compile(r"^[a-z]{2,3}$")
_EDGE_PUNCT_RE = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)

DEFAULT_TIMEOUT = 5.0
MAX_QUERY_LENGTH = 100


class DictionaryError(Exception):
    """Base exception for dictionary lookup failures."""
    pass


class NoDefinitionError(DictionaryError, LookupError):
    """Raised when no definition is available for the requested term."""
    pass


class ProviderUnavailableError(DictionaryError, ConnectionError):
    """Raised when the optional online provider cannot be reached."""
    pass


class LookupCancelledError(DictionaryError):
    """Raised when a lookup is cancelled before or during the request."""
    pass


class InvalidQueryError(DictionaryError, ValueError):
    """Raised when the lookup word or language is malformed."""
    pass


@dataclass
class Definition:
    """A dictionary result for a single word and language."""
    word: str
    lang: str
    part_of_speech: str
    definitions: List[str]
    source: str = "local"

    def to_dict(self) -> Dict[str, object]:
        """Returns a JSON-serializable mapping of this definition."""
        return {
            "word": self.word,
            "lang": self.lang,
            "part_of_speech": self.part_of_speech,
            "definitions": list(self.definitions),
            "source": self.source,
        }


# Local stub dictionary: (word_lower, lang) -> (part_of_speech, [definitions]).
_LOCAL_STUB: Dict[Tuple[str, str], Tuple[str, List[str]]] = {
    ("book", "en"): (
        "noun",
        [
            "A written or printed work consisting of pages bound together.",
            "A bound set of pages for reading.",
        ],
    ),
    ("read", "en"): (
        "verb",
        [
            "To look at and comprehend the meaning of written matter.",
            "To interpret text aloud for a listener.",
        ],
    ),
    ("reader", "en"): (
        "noun",
        [
            "A person who reads.",
            "A device or application used for reading books.",
        ],
    ),
    ("library", "en"): (
        "noun",
        [
            "A collection of books held for reading or reference.",
            "A room or application view organizing a book collection.",
        ],
    ),
    ("page", "en"): (
        "noun",
        [
            "One side of a sheet of paper in a book.",
            "A single screen of content in a paginated reader.",
        ],
    ),
    ("dictionary", "en"): (
        "noun",
        [
            "A reference listing words with their meanings.",
        ],
    ),
    ("livre", "fr"): (
        "nom",
        [
            "Ouvrage ecrit reuni en pages reliees pour la lecture.",
            "Ancienne unite monetaire.",
        ],
    ),
    ("lire", "fr"): (
        "verbe",
        [
            "Interpreter un texte ecrit.",
        ],
    ),
    ("libro", "es"): (
        "sustantivo",
        [
            "Conjunto de paginas encuadernadas para la lectura.",
        ],
    ),
    ("buch", "de"): (
        "Substantiv",
        [
            "Gebundene Druckseiten zum Lesen.",
        ],
    ),
}


def _normalize_lang(lang: Optional[str]) -> str:
    """Normalizes a language tag (e.g. 'en-US' -> 'en'); defaults to 'en'."""
    if lang is None:
        return "en"
    text = str(lang).strip().lower().replace("_", "-")
    if not text:
        return "en"
    return text.split("-")[0]


def _clean_word(word: object) -> str:
    """Strips selection whitespace and surrounding punctuation from a query."""
    if not isinstance(word, str):
        raise InvalidQueryError("Lookup word must be a string")
    cleaned = word.strip()
    if not cleaned:
        raise InvalidQueryError("Lookup word must not be empty")
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise InvalidQueryError("Lookup word is too long")
    cleaned = _EDGE_PUNCT_RE.sub("", cleaned)
    if not cleaned:
        raise InvalidQueryError("Lookup word contains no readable text")
    return cleaned


def _is_cancelled(cancel_event: object) -> bool:
    """Checks threading.Event-like, callable, or cancelled() style cancel signals."""
    if cancel_event is None:
        return False
    try:
        is_set = getattr(cancel_event, "is_set", None)
        if callable(is_set):
            return bool(is_set())
        cancelled = getattr(cancel_event, "cancelled", None)
        if callable(cancelled):
            return bool(cancelled())
        if callable(cancel_event):
            return bool(cancel_event())  # type: ignore[operator]
    except Exception:
        return False
    return False


def _strip_html(text: str) -> str:
    """Removes HTML tags from provider definitions and collapses whitespace."""
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", text or "")).strip()


class DictionaryService:
    """
    Offline-first dictionary with an optional open online provider.

    Local stub entries answer immediately without network access (FR-20).
    The Wiktionary REST API is contacted only when allow_online=True, with
    a timeout and cooperative cancellation. Queried text is never written
    to logs (NFR-04); only lengths and language codes are recorded.
    """

    def __init__(
        self,
        local_entries: Optional[Dict[Tuple[str, str], Tuple[str, List[str]]]] = None,
        online_fetcher: Optional[Callable[..., Definition]] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._local: Dict[Tuple[str, str], Tuple[str, List[str]]] = (
            dict(local_entries) if local_entries is not None else dict(_LOCAL_STUB)
        )
        self._online_fetcher = online_fetcher
        try:
            self._timeout = float(timeout)
        except (TypeError, ValueError):
            self._timeout = DEFAULT_TIMEOUT

    def available_languages(self) -> List[str]:
        """Returns sorted language codes present in the local dictionary."""
        return sorted({lang for (_, lang) in self._local.keys()})

    def lookup(
        self,
        word: str,
        lang: str = "en",
        allow_online: bool = False,
        timeout: Optional[float] = None,
        cancel_event: object = None,
    ) -> Definition:
        """
        Looks up a word in the given language.
        Checks the local dictionary first; contacts the optional online
        provider only when allow_online=True. Raises NoDefinitionError when
        no entry exists, ProviderUnavailableError when the online provider
        cannot be reached, and LookupCancelledError when cancelled.
        """
        lang_norm = _normalize_lang(lang)
        cleaned = _clean_word(word)
        effective_timeout = self._timeout if timeout is None else float(timeout)
        logger.debug(
            "dictionary lookup requested: word_len=%d lang=%s online=%s",
            len(cleaned),
            lang_norm,
            bool(allow_online),
        )
        if _is_cancelled(cancel_event):
            logger.debug("dictionary lookup cancelled before start: lang=%s", lang_norm)
            raise LookupCancelledError("Dictionary lookup was cancelled")

        key = (cleaned.lower(), lang_norm)
        if key in self._local:
            pos, definitions = self._local[key]
            logger.debug(
                "dictionary local hit: lang=%s defs=%d source=local", lang_norm, len(definitions)
            )
            return Definition(
                word=cleaned,
                lang=lang_norm,
                part_of_speech=pos,
                definitions=list(definitions),
                source="local",
            )

        if not allow_online:
            logger.debug("dictionary no local entry: lang=%s", lang_norm)
            raise NoDefinitionError(
                "No local definition is available for the requested term "
                f"(lang={lang_norm}); online lookup was not requested so no "
                "network access was attempted."
            )

        if _is_cancelled(cancel_event):
            logger.debug("dictionary lookup cancelled before online: lang=%s", lang_norm)
            raise LookupCancelledError("Dictionary lookup was cancelled")

        if self._online_fetcher is not None:
            try:
                result = self._online_fetcher(cleaned, lang_norm, effective_timeout, cancel_event)
            except LookupCancelledError:
                raise
            except ProviderUnavailableError:
                raise
            except NoDefinitionError:
                raise
            except DictionaryError:
                raise
            except Exception as exc:
                logger.debug(
                    "dictionary online fetcher failed: lang=%s error=%s",
                    lang_norm,
                    type(exc).__name__,
                )
                raise ProviderUnavailableError(
                    "The online dictionary provider is unavailable; check your "
                    "connection and retry. Local reading is unaffected."
                ) from exc
            if not isinstance(result, Definition) or not result.definitions:
                raise NoDefinitionError(
                    "The online provider returned no definition for the requested term."
                )
            logger.debug("dictionary online hit: lang=%s source=%s", lang_norm, result.source)
            return result
        return self._fetch_online(cleaned, lang_norm, effective_timeout, cancel_event)

    def _fetch_online(
        self, word: str, lang: str, timeout: float, cancel_event: object = None
    ) -> Definition:
        """
        Queries the Wiktionary REST API for a definition.
        Raises NoDefinitionError for 404/empty results and
        ProviderUnavailableError for transport failures.
        """
        if not _LANG_CODE_RE.match(lang):
            raise InvalidQueryError(f"Unsupported language for online lookup (lang={lang})")
        url = (
            f"https://{lang}.wiktionary.org/api/rest_v1/page/definition/"
            f"{urllib.parse.quote(word)}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Aquile-Reader/1.0 (Ubuntu; offline-first dictionary)",
                "Accept": "application/json",
            },
        )
        logger.debug("dictionary online request started: lang=%s", lang)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if _is_cancelled(cancel_event):
                    raise LookupCancelledError("Dictionary lookup was cancelled")
                status = getattr(response, "status", 200)
                if status == 404:
                    raise NoDefinitionError(
                        "The online provider has no definition for the requested term."
                    )
                payload = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                logger.debug("dictionary online no result: lang=%s", lang)
                raise NoDefinitionError(
                    "The online provider has no definition for the requested term."
                ) from exc
            logger.debug(
                "dictionary online unavailable: lang=%s error=%s", lang, type(exc).__name__
            )
            raise ProviderUnavailableError(
                "The online dictionary provider is unavailable "
                f"(HTTP {exc.code}); check your connection and retry. "
                "Local reading is unaffected."
            ) from exc
        except LookupCancelledError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.debug(
                "dictionary online unavailable: lang=%s error=%s", lang, type(exc).__name__
            )
            raise ProviderUnavailableError(
                "The online dictionary provider is unavailable; check your "
                "connection and retry. Local reading is unaffected."
            ) from exc

        if _is_cancelled(cancel_event):
            raise LookupCancelledError("Dictionary lookup was cancelled")
        try:
            data = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            logger.debug("dictionary online bad payload: lang=%s", lang)
            raise ProviderUnavailableError(
                "The online dictionary provider returned an unreadable response; "
                "local reading is unaffected."
            ) from exc

        definitions: List[str] = []
        part_of_speech = ""
        try:
            entries = data if isinstance(data, list) else data.get(lang, data.get("en", []))
            if isinstance(entries, dict):
                entries = [entries]
            for entry in entries or []:
                pos = str(entry.get("partOfSpeech", "") or "")
                if pos and not part_of_speech:
                    part_of_speech = pos
                for item in entry.get("definitions", []) or []:
                    text = item.get("definition", "") if isinstance(item, dict) else str(item)
                    clean = _strip_html(str(text))
                    if clean:
                        definitions.append(clean)
                    if len(definitions) >= 5:
                        break
                if len(definitions) >= 5:
                    break
        except (AttributeError, TypeError) as exc:
            raise ProviderUnavailableError(
                "The online dictionary provider returned an unreadable response; "
                "local reading is unaffected."
            ) from exc

        if not definitions:
            logger.debug("dictionary online no result: lang=%s", lang)
            raise NoDefinitionError(
                "The online provider has no definition for the requested term."
            )
        logger.debug("dictionary online hit: lang=%s defs=%d", lang, len(definitions))
        return Definition(
            word=word,
            lang=lang,
            part_of_speech=part_of_speech or "unknown",
            definitions=definitions,
            source="wiktionary",
        )
