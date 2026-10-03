"""
Ad policy for Aquile Reader on Ubuntu (WP-15, FR-18 / FR-20).

Baseline position: the Linux build bundles no ad SDK and performs no ad
networking. "Ads" on this route are truthful first-party placeholders
(house/promo cards for e.g. the documented Linux upgrade path) rendered
fully offline. No tracking URLs are fetched, prefetched, or pinged —
placeholder actions are in-app route identifiers, never remote beacons.

This module imports nothing network-capable and exposes no function that
opens a socket. ``AdSlot.render()`` returns static local content.
"""

from typing import Dict, List, Mapping, Union

from .tiers import TIER_FREE, TierManager

#: Static house/promo inventory. ``action`` values are in-app route ids
#: (handled locally); they must never be remote tracking URLs.
HOUSE_PROMOS: List[Dict[str, str]] = [
    {
        "id": "house-upgrade",
        "title": "Aquile Reader Premium",
        "body": "Support development and unlock catalog sync when the "
                "approved Linux upgrade path is available.",
        "action": "open_upgrade_info",
    },
    {
        "id": "house-tips",
        "title": "Reading tip",
        "body": "Press F11 for a distraction-free full-screen reading view.",
        "action": "open_reader_tips",
    },
    {
        "id": "house-collections",
        "title": "Collections",
        "body": "All highlights and notes across every book, in one place.",
        "action": "open_collections",
    },
]


def should_show_ads(tier: Union[str, TierManager]) -> bool:
    """Return True only for the free tier.

    Accepts a tier name or a :class:`TierManager` (whose expired trials
    fold to free via ``effective_tier()``). Trial and premium never show
    ads. Unknown tier names return False rather than crashing the UI;
    unknown *features* still raise in :class:`TierManager`.
    """
    name = tier.effective_tier() if isinstance(tier, TierManager) else tier
    return name == TIER_FREE


def placeholder_promo(index: int = 0) -> Dict[str, str]:
    """Return a copy of one static house promo (offline-safe)."""
    if not HOUSE_PROMOS:
        raise ValueError("No house promos configured.")
    return dict(HOUSE_PROMOS[index % len(HOUSE_PROMOS)])


class AdPolicy:
    """Answers whether promotional placeholder content may be shown."""

    def __init__(self, tiers: TierManager) -> None:
        self._tiers = tiers

    def should_show_ads(self) -> bool:
        return should_show_ads(self._tiers)

    def promo_for_current_tier(self) -> Union[Dict[str, str], None]:
        """House promo when ads apply, else None (never a remote ad)."""
        if not self.should_show_ads():
            return None
        return placeholder_promo(0)


class AdSlot:
    """Offline placeholder slot.

    Renders bundled house/promo content only. It never fetches tracking
    URLs, performs network I/O, or loads remote resources: ``render()``
    returns a plain dict of local strings.
    """

    def __init__(self, slot_id: str = "library-footer", promo_index: int = 0) -> None:
        if not slot_id:
            raise ValueError("slot_id must be a non-empty string.")
        self.slot_id = slot_id
        self.promo_index = promo_index

    def render(self) -> Dict[str, str]:
        """Render the placeholder as local content (no network)."""
        promo = placeholder_promo(self.promo_index)
        return {
            "slot": self.slot_id,
            "kind": "house_placeholder",
            "title": promo["title"],
            "body": promo["body"],
            "action": promo["action"],
            "promo_id": promo["id"],
        }

    def render_text(self) -> str:
        content = self.render()
        return f"{content['title']}: {content['body']}"

    def available_offline(self) -> bool:
        """Placeholders are bundled, so they are always offline-available."""
        return True

    @staticmethod
    def tracking_urls_fetched() -> List[str]:
        """Audit hook: this implementation never fetches any URL."""
        return []
