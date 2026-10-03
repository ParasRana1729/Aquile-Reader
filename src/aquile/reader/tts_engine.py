"""
Read-aloud speech engine for Aquile Reader.
Provides offline-first TTS voice discovery (espeak-ng / speech-dispatcher),
playback controls, speed adjustment, word-boundary text tracking, and
state persistence hooks without requiring audio hardware (FR-12, UB-08, FR-20, NFR-04).
"""

import logging
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MIN_RATE = 0.5
MAX_RATE = 2.0
DEFAULT_RATE = 1.0

_WORD_RE = re.compile(r"\S+")
_LANG_TOKEN_RE = re.compile(r"\b[a-z]{2}(?:[-_][A-Za-z]{2})?\b")
_LOCALE_TOKEN_RE = re.compile(r"\b([a-z]{2})[-_][A-Za-z]{2,}\b")

# Upper bound on probed voices: speech-dispatcher can expose thousands of
# voice variants; only a bounded prefix is needed for selection lists.
MAX_PROBED_VOICES = 200
# Upper bound on voice ids echoed in MissingVoiceError messages.
MAX_VOICE_IDS_IN_ERROR = 10

# Process-wide cache so repeated discovery across engine instances stays cheap.
_VOICE_CACHE: Optional[List["Voice"]] = None
_VOICE_CACHE_LOCK = threading.Lock()

# Cloud voice is never used implicitly; explicit opt-in consent is required (UB-08).
CLOUD_CONSENT_MESSAGE = (
    "Cloud voice processing requires explicit disclosure and consent (UB-08). "
    "The requested utterance was not sent anywhere; enable cloud voice explicitly "
    "via set_cloud_consent(True) before retrying."
)


class TtsError(Exception):
    """Base exception for read-aloud speech processing."""
    pass


class MissingVoiceError(TtsError, ValueError):
    """Raised when a requested voice is not available on this system."""
    pass


class CloudVoiceConsentError(TtsError, PermissionError):
    """Raised when cloud voice processing is requested without explicit consent."""
    pass


@dataclass(frozen=True)
class Voice:
    """Describes a single available speech voice."""
    id: str
    name: str
    lang: str
    engine: str

    def to_dict(self) -> Dict[str, str]:
        """Returns a JSON-serializable mapping of this voice."""
        return {"id": self.id, "name": self.name, "lang": self.lang, "engine": self.engine}


_STUB_VOICES: Tuple[Voice, ...] = (
    Voice(id="stub-en", name="Stub English (offline)", lang="en", engine="stub"),
    Voice(id="stub-fr", name="Stub French (offline)", lang="fr", engine="stub"),
    Voice(id="stub-es", name="Stub Spanish (offline)", lang="es", engine="stub"),
)


def _parse_espeak_output(output: str) -> List[Voice]:
    """Parses `espeak-ng --voices` output into Voice entries."""
    voices: List[Voice] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith(("pty", "---")):
            continue
        parts = stripped.split()
        if len(parts) < 4:
            continue
        lang = parts[1].lower().replace("_", "-")
        base_lang = lang.split("-")[0]
        if not re.fullmatch(r"[a-z]{2}", base_lang):
            continue
        name = " ".join(parts[4:]) if len(parts) > 4 else " ".join(parts[2:4])
        voice_id = f"espeak-ng:{lang}:{parts[3]}" if len(parts) > 3 else f"espeak-ng:{lang}"
        voices.append(
            Voice(id=voice_id, name=name or f"espeak-ng {lang}", lang=base_lang, engine="espeak-ng")
        )
    return voices


def _parse_spd_output(output: str, limit: int = MAX_PROBED_VOICES) -> List[Voice]:
    """Parses speech-dispatcher voice listings into Voice entries (best effort)."""
    voices: List[Voice] = []
    for line in output.splitlines():
        if len(voices) >= limit:
            break
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        locale_match = _LOCALE_TOKEN_RE.search(lowered)
        if locale_match:
            lang = locale_match.group(1)
        else:
            token_match = _LANG_TOKEN_RE.search(lowered)
            if not token_match:
                continue
            lang = token_match.group(0).split("-")[0].split("_")[0]
        voice_id = f"speech-dispatcher:{stripped[:48]}"
        voices.append(Voice(id=voice_id, name=stripped[:80], lang=lang, engine="speech-dispatcher"))
    return voices


def _probe_command(binary: str, args: List[str], timeout: float = 2.0) -> Optional[str]:
    """Runs a probe command and returns stdout, or None when unavailable."""
    path = shutil.which(binary)
    if not path:
        return None
    try:
        completed = subprocess.run(
            [path] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout or ""


class NullAudioBackend:
    """Headless-safe audio backend that performs no audio I/O."""

    def play(self, text: str, voice: Optional[Voice], rate: float) -> None:
        """Accepts an utterance without touching audio hardware."""
        return None

    def stop(self) -> None:
        """Stops playback (no-op)."""
        return None

    def pause(self) -> None:
        """Pauses playback (no-op)."""
        return None

    def resume(self) -> None:
        """Resumes playback (no-op)."""
        return None


class TtsEngine:
    """
    Offline-first read-aloud engine decoupled from the audio backend.

    Speech synthesis uses local mechanisms (espeak-ng / speech-dispatcher)
    when present and falls back to a deterministic stub voice list so that
    headless environments and tests operate without audio hardware.
    Network/cloud voices are never contacted unless the caller explicitly
    opts in with consent (UB-08, FR-20).
    """

    MIN_RATE = MIN_RATE
    MAX_RATE = MAX_RATE
    DEFAULT_RATE = DEFAULT_RATE

    def __init__(
        self,
        voice_id: Optional[str] = None,
        rate: float = DEFAULT_RATE,
        on_word_boundary: Optional[Callable[[int, int, int], None]] = None,
        audio_backend: Optional[object] = None,
        allow_cloud_voice: bool = False,
    ):
        self._lock = threading.Lock()
        self._voices_cache: Optional[List[Voice]] = None
        self._voice_id: Optional[str] = None
        self._rate: float = self._clamp_rate(rate)
        self._on_word_boundary = on_word_boundary
        self._audio_backend = audio_backend if audio_backend is not None else NullAudioBackend()
        self._allow_cloud_voice = bool(allow_cloud_voice)
        self._state: str = "idle"
        self._current_text: str = ""
        self._current_spans: List[Tuple[int, int, int]] = []
        self._word_index: int = -1

        if voice_id is not None:
            self.set_voice(voice_id)

    @staticmethod
    def _clamp_rate(rate: float) -> float:
        """Clamps a speech rate into the supported 0.5x-2.0x range."""
        try:
            value = float(rate)
        except (TypeError, ValueError):
            return DEFAULT_RATE
        if value != value:  # NaN guard
            return DEFAULT_RATE
        return max(MIN_RATE, min(MAX_RATE, value))

    @staticmethod
    def get_word_boundaries(text: str) -> List[Tuple[int, int, int]]:
        """
        Computes word-boundary spans for text.
        Returns a list of (word_index, char_start, char_end) tuples.
        """
        spans: List[Tuple[int, int, int]] = []
        for index, match in enumerate(_WORD_RE.finditer(text or "")):
            spans.append((index, match.start(), match.end()))
        return spans

    def list_voices(self, refresh: bool = False) -> List[Voice]:
        """
        Probes espeak-ng and speech-dispatcher for voices.
        Falls back to a stub voice list when no backend is available,
        so this method never raises for missing system packages.
        Results are cached process-wide; pass refresh=True to re-probe.
        """
        global _VOICE_CACHE
        with self._lock:
            if self._voices_cache is not None and not refresh:
                return list(self._voices_cache)
        if not refresh:
            with _VOICE_CACHE_LOCK:
                if _VOICE_CACHE is not None:
                    with self._lock:
                        self._voices_cache = list(_VOICE_CACHE)
                    return list(_VOICE_CACHE)
        probed: List[Voice] = []
        seen: set = set()

        def _extend(candidates: List[Voice]) -> None:
            for voice in candidates:
                if len(probed) >= MAX_PROBED_VOICES:
                    break
                if voice.id not in seen:
                    seen.add(voice.id)
                    probed.append(voice)

        for binary in ("espeak-ng", "espeak"):
            output = _probe_command(binary, ["--voices"])
            if output:
                try:
                    _extend(_parse_espeak_output(output))
                except Exception:
                    logger.debug("espeak voice parsing failed: backend=%s", binary)
                if probed:
                    break
        if not probed:
            for args in (["--list-synthesis-voices"], ["-L"]):
                output = _probe_command("spd-say", args)
                if output:
                    try:
                        _extend(_parse_spd_output(output))
                    except Exception:
                        logger.debug("speech-dispatcher voice parsing failed")
                    if probed:
                        break

        if not probed:
            probed = list(_STUB_VOICES)

        with _VOICE_CACHE_LOCK:
            _VOICE_CACHE = list(probed)
        with self._lock:
            self._voices_cache = list(probed)
        logger.debug("tts voices listed: count=%d", len(probed))
        return list(probed)

    def _find_voice(self, voice_id: str) -> Optional[Voice]:
        """Returns the Voice matching voice_id, or None."""
        for voice in self.list_voices():
            if voice.id == voice_id:
                return voice
        return None

    def _available_voice_ids(self) -> List[str]:
        """Returns available voice ids for error messages."""
        return [voice.id for voice in self.list_voices()]

    def set_voice(self, voice_id: str) -> Voice:
        """
        Selects the active voice.
        Raises MissingVoiceError with an Ubuntu recovery path when unknown.
        """
        voice = self._find_voice(voice_id)
        if voice is None:
            available = self._available_voice_ids()
            shown = available[:MAX_VOICE_IDS_IN_ERROR]
            remainder = len(available) - len(shown)
            listing = ", ".join(shown) if shown else "none"
            if remainder > 0:
                listing += f" (and {remainder} more)"
            raise MissingVoiceError(
                f"Voice '{voice_id}' is not available. "
                f"Available voices ({len(available)}): {listing}. "
                "On Ubuntu, install additional voices with "
                "'sudo apt install espeak-ng speech-dispatcher' and check "
                "Settings > Reader > Voice. Your reading position has been preserved."
            )
        with self._lock:
            self._voice_id = voice.id
        logger.debug("tts voice selected: lang=%s engine=%s", voice.lang, voice.engine)
        return voice

    def get_voice(self) -> Optional[Voice]:
        """Returns the currently selected Voice, or None when unset."""
        if self._voice_id is None:
            return None
        return self._find_voice(self._voice_id)

    def set_rate(self, rate: float) -> float:
        """
        Sets the speech rate, clamped to 0.5x-2.0x.
        Returns the effective clamped rate.
        """
        clamped = self._clamp_rate(rate)
        with self._lock:
            self._rate = clamped
        logger.debug("tts rate set: rate=%.2f", clamped)
        return clamped

    def get_rate(self) -> float:
        """Returns the current speech rate."""
        with self._lock:
            return self._rate

    def set_on_word_boundary(self, callback: Optional[Callable[[int, int, int], None]]) -> None:
        """Registers the word-boundary tracking callback (index, start, end)."""
        with self._lock:
            self._on_word_boundary = callback

    def set_cloud_consent(self, allowed: bool) -> None:
        """
        Records explicit user consent for cloud voice processing (UB-08).
        Cloud synthesis stays disabled until this is set to True.
        """
        with self._lock:
            self._allow_cloud_voice = bool(allowed)
        logger.debug("tts cloud consent updated: allowed=%s", bool(allowed))

    def set_audio_backend(self, backend: object) -> None:
        """Replaces the audio backend without affecting reading state."""
        with self._lock:
            self._audio_backend = backend

    @property
    def state(self) -> str:
        """Returns the playback state: idle, speaking, paused."""
        with self._lock:
            return self._state

    @property
    def is_speaking(self) -> bool:
        """Returns True while an utterance is active (speaking or paused)."""
        with self._lock:
            return self._state in ("speaking", "paused")

    @property
    def is_paused(self) -> bool:
        """Returns True while playback is paused."""
        with self._lock:
            return self._state == "paused"

    @property
    def last_word_spans(self) -> List[Tuple[int, int, int]]:
        """Returns word-boundary spans of the most recent utterance."""
        with self._lock:
            return list(self._current_spans)

    @property
    def word_index(self) -> int:
        """Returns the index of the last tracked word (-1 when idle)."""
        with self._lock:
            return self._word_index

    def speak(
        self,
        text: str,
        voice_id: Optional[str] = None,
        rate: Optional[float] = None,
        on_word_boundary: Optional[Callable[[int, int, int], None]] = None,
        use_cloud: bool = False,
    ) -> List[Tuple[int, int, int]]:
        """
        Starts speaking text with word-boundary tracking.
        Operates fully offline unless use_cloud=True, which requires
        explicit consent via set_cloud_consent(True) (UB-08, FR-20).
        Never logs the spoken text itself (NFR-04); only its length.
        """
        if use_cloud and not self._allow_cloud_voice:
            raise CloudVoiceConsentError(CLOUD_CONSENT_MESSAGE)
        if text is None or not str(text).strip():
            raise ValueError("Cannot speak empty text")
        if voice_id is not None:
            self.set_voice(voice_id)
        if rate is not None:
            self.set_rate(rate)
        callback = on_word_boundary if on_word_boundary is not None else self._on_word_boundary

        content = str(text)
        spans = self.get_word_boundaries(content)
        with self._lock:
            active_voice_id = self._voice_id
        voice = self._find_voice(active_voice_id) if active_voice_id else None
        with self._lock:
            self._current_text = content
            self._current_spans = list(spans)
            self._word_index = -1
            self._state = "speaking"
            backend = self._audio_backend
            current_rate = self._rate
        logger.debug(
            "tts speak started: chars=%d words=%d rate=%.2f cloud=%s",
            len(content),
            len(spans),
            current_rate,
            bool(use_cloud),
        )
        try:
            play = getattr(backend, "play", None)
            if callable(play):
                play(content, voice, current_rate)
        except Exception:
            logger.debug("tts audio backend play failed; tracking continues")

        for index, start, end in spans:
            with self._lock:
                if self._state not in ("speaking", "paused"):
                    break
                self._word_index = index
            if callback is not None:
                try:
                    callback(index, start, end)
                except Exception:
                    logger.debug("tts word-boundary callback failed: index=%d", index)
        return list(spans)

    def stop(self) -> None:
        """Stops playback and returns to idle, preserving voice/rate settings."""
        with self._lock:
            backend = self._audio_backend
            self._state = "idle"
            self._word_index = -1
        try:
            stop = getattr(backend, "stop", None)
            if callable(stop):
                stop()
        except Exception:
            logger.debug("tts audio backend stop failed")
        logger.debug("tts stopped")

    def pause(self) -> bool:
        """
        Pauses playback, preserving the word position for resume (UB-08).
        Returns True when the state changed to paused.
        """
        with self._lock:
            if self._state != "speaking":
                return False
            self._state = "paused"
            backend = self._audio_backend
        try:
            pause = getattr(backend, "pause", None)
            if callable(pause):
                pause()
        except Exception:
            logger.debug("tts audio backend pause failed")
        logger.debug("tts paused")
        return True

    def resume(self) -> bool:
        """
        Resumes paused playback without losing the word position.
        Returns True when the state changed back to speaking.
        """
        with self._lock:
            if self._state != "paused":
                return False
            self._state = "speaking"
            backend = self._audio_backend
        try:
            resume = getattr(backend, "resume", None)
            if callable(resume):
                resume()
        except Exception:
            logger.debug("tts audio backend resume failed")
        logger.debug("tts resumed")
        return True

    def get_state(self) -> Dict[str, object]:
        """
        Returns a JSON-serializable snapshot for persistence
        (voice, rate, playback state, word position).
        """
        with self._lock:
            return {
                "voice_id": self._voice_id,
                "rate": self._rate,
                "state": self._state,
                "word_index": self._word_index,
                "text_length": len(self._current_text),
            }

    def restore_state(self, state: Dict[str, object]) -> None:
        """
        Restores a snapshot from get_state() without losing reading state.
        Raises MissingVoiceError when the saved voice is no longer available.
        """
        if not isinstance(state, dict):
            raise ValueError("Invalid TTS state snapshot")
        voice_id = state.get("voice_id")
        if voice_id is not None:
            self.set_voice(str(voice_id))
        if "rate" in state:
            try:
                self.set_rate(float(state["rate"]))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                pass
        saved_word = state.get("word_index", -1)
        try:
            word_index = int(saved_word)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            word_index = -1
        saved_playback = str(state.get("state", "idle"))
        with self._lock:
            if saved_playback == "paused" and self._state == "idle" and self._current_spans:
                self._state = "paused"
            self._word_index = max(-1, word_index)
        logger.debug("tts state restored")

    save_state = get_state
