"""
Entitlement tiers for Aquile Reader on Ubuntu (WP-15, FR-18 / FR-20).

Clean-room Linux route: there is no Microsoft Store or Google Play billing
on Ubuntu, and Windows/Android purchases are NOT assumed to transfer.
Entitlement state lives in a local, offline-readable record (a plain
``dict[str, str]`` compatible with the ``settings`` key/value table used by
``SettingsRepository``). A future approved online purchase provider may issue
signed entitlement records; until such a route is approved, only locally
issued records are accepted by :meth:`TierManager.restore`.

Local-reading promise (FR-20): every local reading feature is enabled on
every tier. Nothing about local books, annotations, navigation, or saved
settings is paywalled. ``PREMIUM_FEATURES`` only gates future online
capabilities (e.g. catalog sync) that require an approved provider.

This module performs zero network I/O. All expiry evaluation uses an
injectable clock so tests never depend on wall time.
"""

import json
import time
from typing import Callable, Dict, Mapping, Optional, Union

TIER_FREE = "free"
TIER_TRIAL = "trial"
TIER_PREMIUM = "premium"

VALID_TIERS = frozenset({TIER_FREE, TIER_TRIAL, TIER_PREMIUM})

#: Trial length (days) used when a trial is started without an explicit span.
TRIAL_DEFAULT_DAYS = 14

#: Features that are always available offline on every tier (FR-20).
#: Local books must never be paywalled.
LOCAL_FEATURES = frozenset({
    "local_reading",
    "library",
    "epub",
    "pdf",
    "cbz",
    "cbr",
    "annotations",
    "bookmarks",
    "notes",
    "collections",
    "search",
    "statistics",
    "settings",
    "themes",
    "read_aloud",
    "dictionary_offline",
})

#: Future online capabilities gated behind trial/premium. These require an
#: approved provider when they arrive; today they simply evaluate against
#: the local tier record without any network access.
PREMIUM_FEATURES = frozenset({
    "catalog_sync",
    "cross_device_sync",
    "premium_catalog",
})

#: Issuers whose entitlement records this build accepts. Anything else
#: (e.g. a foreign store receipt) is rejected: no purchase-transfer
#: assumption across platforms.
LOCAL_ISSUERS = frozenset({"local", "linux", "test"})

_SETTINGS_PREFIX = "entitlement."


class EntitlementError(ValueError):
    """Raised for unknown tiers/features, malformed restore payloads, or
    entitlement records that claim rights this Linux route cannot verify
    (e.g. assumed cross-platform purchase transfer)."""


Clock = Callable[[], float]


def _now(clock: Optional[Clock]) -> float:
    return clock() if clock is not None else time.time()


class TierManager:
    """Owns the local entitlement tier and its feature gates.

    Args:
        tier: one of ``"free"``, ``"trial"``, ``"premium"``.
        trial_started_at: epoch seconds when the trial began (trial only).
        trial_days: trial length in days.
        clock: injectable time source returning epoch seconds.
    """

    def __init__(
        self,
        tier: str = TIER_FREE,
        trial_started_at: Optional[float] = None,
        trial_days: float = TRIAL_DEFAULT_DAYS,
        clock: Optional[Clock] = None,
    ) -> None:
        if tier not in VALID_TIERS:
            raise EntitlementError(
                f"Unknown tier {tier!r}; expected one of {sorted(VALID_TIERS)}."
            )
        if trial_days <= 0:
            raise EntitlementError(
                f"trial_days must be positive, got {trial_days!r}."
            )
        if trial_started_at is not None and trial_started_at < 0:
            raise EntitlementError(
                f"trial_started_at must be a non-negative epoch, "
                f"got {trial_started_at!r}."
            )
        self._tier = tier
        self._trial_started_at = (
            float(trial_started_at) if trial_started_at is not None else None
        )
        self._trial_days = float(trial_days)
        self._clock = clock

    # -- tier state ------------------------------------------------------
    @property
    def tier(self) -> str:
        """Configured tier (may be an expired ``"trial"``; see
        :meth:`effective_tier`)."""
        return self._tier

    @property
    def trial_started_at(self) -> Optional[float]:
        return self._trial_started_at

    @property
    def trial_days(self) -> float:
        return self._trial_days

    def set_tier(self, tier: str) -> None:
        if tier not in VALID_TIERS:
            raise EntitlementError(
                f"Unknown tier {tier!r}; expected one of {sorted(VALID_TIERS)}."
            )
        self._tier = tier

    def start_trial(
        self,
        started_at: Optional[float] = None,
        trial_days: Optional[float] = None,
    ) -> None:
        """Begin (or restart) a local trial."""
        days = self._trial_days if trial_days is None else float(trial_days)
        if days <= 0:
            raise EntitlementError(
                f"trial_days must be positive, got {trial_days!r}."
            )
        now = float(started_at) if started_at is not None else _now(self._clock)
        if now < 0:
            raise EntitlementError(
                f"started_at must be a non-negative epoch, got {started_at!r}."
            )
        self._tier = TIER_TRIAL
        self._trial_started_at = now
        self._trial_days = days

    def is_trial_expired(self) -> bool:
        """True when the trial tier no longer confers premium access.

        A trial without a recorded start cannot prove its validity, so it
        is treated as expired rather than granting access.
        """
        if self._tier != TIER_TRIAL:
            return False
        if self._trial_started_at is None:
            return True
        elapsed = _now(self._clock) - self._trial_started_at
        return elapsed >= self._trial_days * 86400.0

    def is_trial_active(self) -> bool:
        return self._tier == TIER_TRIAL and not self.is_trial_expired()

    def effective_tier(self) -> str:
        """Tier after trial-expiry folding: an expired trial behaves as
        ``"free"`` (ads return, premium gates close) while the stored
        record is preserved for inspection."""
        if self._tier == TIER_TRIAL and self.is_trial_expired():
            return TIER_FREE
        return self._tier

    # -- feature gates ---------------------------------------------------
    def is_enabled(self, feature: str) -> bool:
        """Return True when ``feature`` is available under this tier.

        All :data:`LOCAL_FEATURES` are enabled on every tier (FR-20);
        :data:`PREMIUM_FEATURES` require premium or an unexpired trial.
        Raises :class:`EntitlementError` for unknown features so callers
        cannot silently gate (or ungate) a misspelled name.
        """
        if feature in LOCAL_FEATURES:
            return True
        if feature in PREMIUM_FEATURES:
            return self.effective_tier() in (TIER_TRIAL, TIER_PREMIUM)
        raise EntitlementError(
            f"Unknown feature {feature!r}; expected one of "
            f"{sorted(LOCAL_FEATURES | PREMIUM_FEATURES)}."
        )

    # Aliases used across UI/integration call sites.
    can_use = is_enabled
    has_access = is_enabled

    # -- persistence (offline, SettingsRepository-compatible) ------------
    def to_persistence_dict(self) -> Dict[str, str]:
        """Flatten to a ``dict[str, str]`` storable in the ``settings``
        key/value table. String-only values keep it compatible with
        ``SettingsRepository``'s storage contract."""
        data: Dict[str, str] = {
            f"{_SETTINGS_PREFIX}tier": self._tier,
            f"{_SETTINGS_PREFIX}trial_days": repr(self._trial_days),
        }
        data[f"{_SETTINGS_PREFIX}trial_started_at"] = (
            "" if self._trial_started_at is None else repr(self._trial_started_at)
        )
        return data

    # Alias spelling for call sites that think in "settings" terms.
    to_settings_dict = to_persistence_dict
    to_dict = to_persistence_dict

    @classmethod
    def from_persistence_dict(
        cls,
        data: Mapping[str, str],
        clock: Optional[Clock] = None,
    ) -> "TierManager":
        """Rebuild from :meth:`to_persistence_dict` output."""
        try:
            tier = data[f"{_SETTINGS_PREFIX}tier"]
        except KeyError:
            raise EntitlementError(
                f"Entitlement record is missing {_SETTINGS_PREFIX!r}tier."
            )
        if tier not in VALID_TIERS:
            raise EntitlementError(
                f"Unknown tier {tier!r} in stored entitlement record."
            )
        raw_days = data.get(f"{_SETTINGS_PREFIX}trial_days", repr(TRIAL_DEFAULT_DAYS))
        try:
            trial_days = float(raw_days)
        except (TypeError, ValueError):
            raise EntitlementError(
                f"Corrupt trial_days {raw_days!r} in stored entitlement record."
            )
        if trial_days <= 0:
            raise EntitlementError(
                f"Corrupt trial_days {raw_days!r} in stored entitlement record."
            )
        raw_started = data.get(f"{_SETTINGS_PREFIX}trial_started_at", "")
        trial_started_at: Optional[float] = None
        if raw_started not in ("", None):
            try:
                trial_started_at = float(raw_started)
            except (TypeError, ValueError):
                raise EntitlementError(
                    f"Corrupt trial_started_at {raw_started!r} in stored "
                    "entitlement record."
                )
            if trial_started_at < 0:
                raise EntitlementError(
                    f"Corrupt trial_started_at {raw_started!r} in stored "
                    "entitlement record."
                )
        return cls(
            tier=tier,
            trial_started_at=trial_started_at,
            trial_days=trial_days,
            clock=clock,
        )

    from_settings_dict = from_persistence_dict
    from_dict = from_persistence_dict

    # -- restore ---------------------------------------------------------
    @classmethod
    def restore(
        cls,
        state: Union[str, bytes, Mapping[str, object]],
        clock: Optional[Clock] = None,
    ) -> "TierManager":
        """Restore entitlement state from an exported JSON payload or dict.

        Accepted shape::

            {"tier": "premium", "trial_started_at": ..., "trial_days": ...,
             "issued_by": "local"}

        ``issued_by``, when present, must name a locally trusted issuer
        (see :data:`LOCAL_ISSUERS`). Records issued by foreign stores
        (e.g. ``"microsoft_store"`` / ``"google_play"``) are rejected with
        :class:`EntitlementError`: purchases are never assumed to transfer
        to Ubuntu. The approved Linux upgrade path is a locally issued
        record, documented alongside the packaging groundwork.
        """
        if isinstance(state, bytes):
            try:
                state = state.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise EntitlementError(f"Restore payload is not UTF-8: {exc}")
        if isinstance(state, str):
            try:
                parsed = json.loads(state)
            except json.JSONDecodeError as exc:
                raise EntitlementError(f"Restore payload is not valid JSON: {exc}")
        elif isinstance(state, Mapping):
            parsed = dict(state)
        else:
            raise EntitlementError(
                "Restore payload must be a JSON string or mapping, "
                f"got {type(state).__name__}."
            )
        if not isinstance(parsed, dict):
            raise EntitlementError(
                "Restore payload must decode to a JSON object."
            )
        issuer = parsed.get("issued_by", "local")
        if issuer not in LOCAL_ISSUERS:
            raise EntitlementError(
                f"Entitlement issuer {issuer!r} is not valid for this Linux "
                "build; Microsoft Store / Google Play purchases do not "
                "transfer to Ubuntu. Obtain a locally issued entitlement "
                "through the documented Linux upgrade path."
            )
        tier = parsed.get("tier", TIER_FREE)
        if tier not in VALID_TIERS:
            raise EntitlementError(
                f"Unknown tier {tier!r} in restore payload."
            )
        trial_started_at = parsed.get("trial_started_at")
        if trial_started_at is not None:
            try:
                trial_started_at = float(trial_started_at)
            except (TypeError, ValueError):
                raise EntitlementError(
                    "Corrupt trial_started_at in restore payload."
                )
            if trial_started_at < 0:
                raise EntitlementError(
                    "Corrupt trial_started_at in restore payload."
                )
        trial_days = parsed.get("trial_days", TRIAL_DEFAULT_DAYS)
        try:
            trial_days = float(trial_days)
        except (TypeError, ValueError):
            raise EntitlementError("Corrupt trial_days in restore payload.")
        if trial_days <= 0:
            raise EntitlementError("Corrupt trial_days in restore payload.")
        return cls(
            tier=tier,
            trial_started_at=trial_started_at,
            trial_days=trial_days,
            clock=clock,
        )

    def export_json(self) -> str:
        """Export local state for backup/restore round-trips."""
        payload = {
            "tier": self._tier,
            "trial_started_at": self._trial_started_at,
            "trial_days": self._trial_days,
            "issued_by": "local",
        }
        return json.dumps(payload, sort_keys=True)

    # -- dunder ----------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TierManager):
            return NotImplemented
        return (
            self._tier == other._tier
            and self._trial_started_at == other._trial_started_at
            and self._trial_days == other._trial_days
        )

    def __repr__(self) -> str:
        return (
            f"TierManager(tier={self._tier!r}, "
            f"trial_started_at={self._trial_started_at!r}, "
            f"trial_days={self._trial_days!r})"
        )
