"""
Read-aloud (TTS) playback bar for Aquile Reader.

Headless-safe Gtk control: constructs without touching audio hardware
(FR-12, FR-20). All audio work goes through the injected TtsEngine and
only happens in response to user actions, never in __init__.
"""

import logging

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

try:
    from ..reader.tts_engine import MIN_RATE, MAX_RATE, DEFAULT_RATE, MissingVoiceError
except (ImportError, ValueError):
    try:
        from aquile.reader.tts_engine import MIN_RATE, MAX_RATE, DEFAULT_RATE, MissingVoiceError
    except (ImportError, ValueError):  # pragma: no cover - import fallback
        MIN_RATE, MAX_RATE, DEFAULT_RATE = 0.5, 2.0, 1.0

        class MissingVoiceError(ValueError):
            """Fallback when the engine module is unavailable."""

try:
    from ..reader.tts_engine import TtsEngine  # noqa: F401  (typing only)
except (ImportError, ValueError):
    try:
        from aquile.reader.tts_engine import TtsEngine  # noqa: F401
    except (ImportError, ValueError):
        TtsEngine = object  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


def _clamp_rate(value: object) -> float:
    """Clamps a speech rate into the supported 0.5x-2.0x range."""
    try:
        rate = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(DEFAULT_RATE)
    if rate != rate:  # NaN guard
        return float(DEFAULT_RATE)
    return max(float(MIN_RATE), min(float(MAX_RATE), rate))


class TtsBar(Gtk.Box):
    """
    Compact read-aloud control bar.

    Contains play/pause/stop buttons, a voice Gtk.DropDown populated from
    TtsEngine.list_voices(), a speed Gtk.Scale (0.5x-2.0x), and a
    text-tracking label updated on word boundaries.

    The constructor performs no audio I/O: it never calls speak/play/
    pause/stop on the engine, so it is safe to build headless.
    """

    def __init__(self, tts_engine) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.tts_engine = tts_engine
        self._get_text_callback = None
        self._syncing_speed = False
        self._syncing_voice = False
        self._voices: list = []
        self._voice_ids: list = []

        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        self.add_css_class("tts-bar")

        # Playback buttons.
        self.play_button = Gtk.Button.new_from_icon_name("media-playback-start-symbolic")
        self.play_button.set_tooltip_text("Read aloud")
        self.play_button.connect("clicked", self._on_play_clicked)
        self.append(self.play_button)

        self.pause_button = Gtk.Button.new_from_icon_name("media-playback-pause-symbolic")
        self.pause_button.set_tooltip_text("Pause / resume")
        self.pause_button.connect("clicked", self._on_pause_clicked)
        self.append(self.pause_button)

        self.stop_button = Gtk.Button.new_from_icon_name("media-playback-stop-symbolic")
        self.stop_button.set_tooltip_text("Stop reading aloud")
        self.stop_button.connect("clicked", self._on_stop_clicked)
        self.append(self.stop_button)

        # Voice selector (populated from the engine; never touches audio).
        self._voice_model = Gtk.StringList.new(["Default voice"])
        expression = Gtk.PropertyExpression.new(Gtk.StringObject, None, "string")
        self.voice_dropdown = Gtk.DropDown(model=self._voice_model, expression=expression)
        self.voice_dropdown.set_tooltip_text("Voice")
        self.voice_dropdown.connect("notify::selected", self._on_voice_changed)
        self.append(self.voice_dropdown)
        self._refresh_voices()

        # Speed scale 0.5x-2.0x.
        initial_rate = _clamp_rate(
            self._safe_engine_call("get_rate", float(DEFAULT_RATE))
        )
        self.speed_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, float(MIN_RATE), float(MAX_RATE), 0.1
        )
        self.speed_scale.set_value(initial_rate)
        self.speed_scale.set_digits(1)
        self.speed_scale.set_hexpand(True)
        self.speed_scale.set_tooltip_text("Speech speed (0.5x-2.0x)")
        self.speed_scale.connect("value-changed", self._on_speed_changed)
        self.append(self.speed_scale)

        self.speed_label = Gtk.Label(label=f"{initial_rate:.1f}x")
        self.append(self.speed_label)

        # Text-tracking readout.
        self.tracking_label = Gtk.Label(label="Ready")
        self.tracking_label.set_hexpand(True)
        self.tracking_label.set_halign(Gtk.Align.START)
        self.tracking_label.set_ellipsize(True)
        self.append(self.tracking_label)

    # -- setup helpers ----------------------------------------------------

    def _safe_engine_call(self, method_name: str, default):
        """Calls an engine getter defensively; never raises."""
        engine = self.tts_engine
        method = getattr(engine, method_name, None) if engine is not None else None
        if not callable(method):
            return default
        try:
            return method()
        except Exception:
            logger.debug("tts bar engine call failed: method=%s", method_name)
            return default

    def _refresh_voices(self) -> None:
        """(Re)populates the voice model from list_voices(). No audio I/O."""
        voices = []
        engine = self.tts_engine
        list_voices = getattr(engine, "list_voices", None) if engine is not None else None
        if callable(list_voices):
            try:
                voices = list(list_voices()) or []
            except Exception:
                logger.debug("tts bar voice listing failed")
                voices = []
        self._voices = list(voices)
        self._voice_ids = [getattr(v, "id", "") for v in self._voices]

        if self._voices:
            names = [
                str(getattr(v, "name", "") or getattr(v, "id", "") or "Voice")
                for v in self._voices
            ]
        else:
            names = ["Default voice"]
        self._syncing_voice = True
        try:
            self._voice_model = Gtk.StringList.new(names)
            self.voice_dropdown.set_model(self._voice_model)
            selected = 0
            current = self._safe_engine_call("get_voice", None)
            current_id = getattr(current, "id", None)
            if current_id in self._voice_ids:
                selected = self._voice_ids.index(current_id)
            self.voice_dropdown.set_selected(selected)
        finally:
            self._syncing_voice = False

    # -- public API --------------------------------------------------------

    def bind_text(self, get_text_callback) -> None:
        """Registers the callback returning the text to speak."""
        if get_text_callback is not None and not callable(get_text_callback):
            raise ValueError("get_text_callback must be callable or None")
        self._get_text_callback = get_text_callback

    def get_speed(self) -> float:
        """Returns the current speed scale value, clamped to 0.5x-2.0x."""
        try:
            return _clamp_rate(self.speed_scale.get_value())
        except Exception:
            return float(DEFAULT_RATE)

    def set_speed(self, rate: float) -> float:
        """Sets the speed (clamped), syncing the engine, scale, and label."""
        clamped = _clamp_rate(rate)
        engine = self.tts_engine
        setter = getattr(engine, "set_rate", None) if engine is not None else None
        if callable(setter):
            try:
                clamped = _clamp_rate(setter(clamped))
            except Exception:
                logger.debug("tts bar set_rate failed")
        self._syncing_speed = True
        try:
            self.speed_scale.set_value(clamped)
            self.speed_label.set_label(f"{clamped:.1f}x")
        finally:
            self._syncing_speed = False
        return clamped

    def get_voice_count(self) -> int:
        """Returns the number of voices in the dropdown model."""
        try:
            return int(self.voice_dropdown.get_model().get_n_items())
        except Exception:
            return 0

    def get_selected_voice_id(self):
        """Returns the selected voice id, or None when unavailable."""
        try:
            index = int(self.voice_dropdown.get_selected())
        except Exception:
            return None
        if 0 <= index < len(self._voice_ids):
            return self._voice_ids[index]
        return None

    def get_tracking_text(self) -> str:
        """Returns the current tracking label text (for tests)."""
        try:
            return str(self.tracking_label.get_label())
        except Exception:
            return ""

    def on_close(self) -> None:
        """Stops playback and releases the text callback. Idempotent."""
        self._get_text_callback = None
        engine = self.tts_engine
        stop = getattr(engine, "stop", None) if engine is not None else None
        if callable(stop):
            try:
                stop()
            except Exception:
                logger.debug("tts bar stop on close failed")

    # -- signal handlers ----------------------------------------------------

    def _on_voice_changed(self, dropdown: Gtk.DropDown, _pspec) -> None:
        if self._syncing_voice:
            return
        voice_id = self.get_selected_voice_id()
        if voice_id is None:
            return
        engine = self.tts_engine
        setter = getattr(engine, "set_voice", None) if engine is not None else None
        if not callable(setter):
            return
        try:
            setter(voice_id)
        except MissingVoiceError:
            logger.debug("tts bar voice unavailable")
            self.tracking_label.set_label("Selected voice is unavailable.")
        except Exception:
            logger.debug("tts bar set_voice failed")

    def _on_speed_changed(self, scale: Gtk.Scale) -> None:
        if self._syncing_speed:
            return
        try:
            value = float(scale.get_value())
        except Exception:
            return
        self.set_speed(value)

    def _on_play_clicked(self, _button: Gtk.Button) -> None:
        engine = self.tts_engine
        speak = getattr(engine, "speak", None) if engine is not None else None
        if not callable(speak):
            self.tracking_label.set_label("Read-aloud is unavailable.")
            return
        text = ""
        if callable(self._get_text_callback):
            try:
                text = str(self._get_text_callback() or "")
            except Exception:
                logger.debug("tts bar text callback failed")
                text = ""
        if not text.strip():
            self.tracking_label.set_label("No text to read.")
            return
        self.tracking_label.set_label("Reading…")
        try:
            speak(text, on_word_boundary=self._on_word_boundary)
        except Exception:
            logger.debug("tts bar speak failed")
            self.tracking_label.set_label("Could not start reading aloud.")

    def _on_pause_clicked(self, _button: Gtk.Button) -> None:
        engine = self.tts_engine
        if engine is None:
            return
        try:
            if bool(getattr(engine, "is_paused", False)):
                resume = getattr(engine, "resume", None)
                if callable(resume) and resume():
                    self.tracking_label.set_label("Reading…")
            else:
                pause = getattr(engine, "pause", None)
                if callable(pause) and pause():
                    self.tracking_label.set_label("Paused.")
        except Exception:
            logger.debug("tts bar pause toggle failed")

    def _on_stop_clicked(self, _button: Gtk.Button) -> None:
        engine = self.tts_engine
        stop = getattr(engine, "stop", None) if engine is not None else None
        if callable(stop):
            try:
                stop()
            except Exception:
                logger.debug("tts bar stop failed")
        self.tracking_label.set_label("Stopped.")

    def _on_word_boundary(self, index: int, _start: int, _end: int) -> None:
        """Word-tracking callback; marshals the label update to the main loop."""

        def _update() -> bool:
            try:
                self.tracking_label.set_label(f"Word {int(index) + 1}")
            except Exception:
                pass
            return False

        try:
            GLib.idle_add(_update)
        except Exception:
            pass
