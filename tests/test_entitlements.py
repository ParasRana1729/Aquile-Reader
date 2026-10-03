"""
Entitlement tier and ad-placeholder tests (WP-15; FR-18 / FR-20).

Offline-only: no test performs network I/O. Trial expiry uses an
injectable fake clock, never wall time.
"""

import json
import unittest

from src.aquile.entitlements.tiers import (
    EntitlementError,
    TierManager,
    TIER_FREE,
    TIER_TRIAL,
    TIER_PREMIUM,
    LOCAL_FEATURES,
)
from src.aquile.entitlements.ads import (
    AdPolicy,
    AdSlot,
    HOUSE_PROMOS,
    should_show_ads,
)


class FakeClock:
    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


class TestTierGates(unittest.TestCase):
    def test_free_tier_enables_all_local_reading(self):
        tiers = TierManager(tier=TIER_FREE)
        for feature in LOCAL_FEATURES:
            self.assertTrue(
                tiers.is_enabled(feature),
                f"local feature {feature!r} must be free (FR-20)",
            )

    def test_free_tier_blocks_premium_gated_sync(self):
        tiers = TierManager(tier=TIER_FREE)
        self.assertFalse(tiers.is_enabled("catalog_sync"))
        self.assertFalse(tiers.can_use("cross_device_sync"))

    def test_active_trial_unlocks_premium_gates(self):
        clock = FakeClock()
        tiers = TierManager(
            tier=TIER_TRIAL, trial_started_at=clock.now, clock=clock
        )
        self.assertTrue(tiers.is_trial_active())
        self.assertFalse(tiers.is_trial_expired())
        self.assertTrue(tiers.is_enabled("catalog_sync"))
        self.assertTrue(tiers.has_access("cross_device_sync"))

    def test_premium_unlocks_premium_gates(self):
        tiers = TierManager(tier=TIER_PREMIUM)
        self.assertTrue(tiers.is_enabled("catalog_sync"))
        self.assertTrue(tiers.is_enabled("local_reading"))

    def test_trial_expiry_folds_to_free(self):
        clock = FakeClock(now=1_000_000.0)
        tiers = TierManager(
            tier=TIER_TRIAL,
            trial_started_at=clock.now,
            trial_days=14,
            clock=clock,
        )
        clock.now += 15 * 86400.0  # past the 14-day trial
        self.assertTrue(tiers.is_trial_expired())
        self.assertFalse(tiers.is_trial_active())
        self.assertEqual(tiers.effective_tier(), TIER_FREE)
        self.assertFalse(tiers.is_enabled("catalog_sync"))
        # Local books stay readable after expiry (FR-20).
        self.assertTrue(tiers.is_enabled("local_reading"))
        self.assertTrue(tiers.is_enabled("annotations"))

    def test_unknown_tier_and_feature_raise_explicit_errors(self):
        with self.assertRaises(EntitlementError):
            TierManager(tier="ultra")
        with self.assertRaises(EntitlementError):
            TierManager().set_tier("ultra")
        with self.assertRaises(EntitlementError):
            TierManager().is_enabled("not_a_feature")


class TestRestoreAndPersistence(unittest.TestCase):
    def test_restore_valid_local_record(self):
        payload = json.dumps(
            {
                "tier": "premium",
                "trial_started_at": None,
                "trial_days": 14,
                "issued_by": "local",
            }
        )
        tiers = TierManager.restore(payload)
        self.assertEqual(tiers.tier, TIER_PREMIUM)
        self.assertTrue(tiers.is_enabled("catalog_sync"))

    def test_restore_rejects_foreign_store_transfer(self):
        for issuer in ("microsoft_store", "google_play", "windows_store"):
            payload = json.dumps({"tier": "premium", "issued_by": issuer})
            with self.assertRaises(EntitlementError, msg=issuer):
                TierManager.restore(payload)

    def test_restore_rejects_malformed_payloads(self):
        with self.assertRaises(EntitlementError):
            TierManager.restore("{not json")
        with self.assertRaises(EntitlementError):
            TierManager.restore(json.dumps({"tier": "gold"}))
        with self.assertRaises(EntitlementError):
            TierManager.restore(json.dumps(["premium"]))
        with self.assertRaises(EntitlementError):
            TierManager.restore(42)

    def test_offline_persistence_roundtrip(self):
        clock = FakeClock()
        original = TierManager(
            tier=TIER_TRIAL,
            trial_started_at=clock.now,
            trial_days=7,
            clock=clock,
        )
        stored = original.to_settings_dict()
        # SettingsRepository-compatible: plain str keys and str values.
        self.assertTrue(all(isinstance(k, str) for k in stored))
        self.assertTrue(all(isinstance(v, str) for v in stored.values()))
        revived = TierManager.from_settings_dict(stored, clock=clock)
        self.assertEqual(revived, original)
        self.assertTrue(revived.is_trial_active())
        # JSON export/import round-trips offline too.
        exported = original.export_json()
        self.assertEqual(TierManager.restore(exported, clock=clock), original)

    def test_persistence_rejects_corrupt_records(self):
        with self.assertRaises(EntitlementError):
            TierManager.from_settings_dict({})
        with self.assertRaises(EntitlementError):
            TierManager.from_settings_dict({"entitlement.tier": "gold"})
        with self.assertRaises(EntitlementError):
            TierManager.from_settings_dict(
                {"entitlement.tier": "trial", "entitlement.trial_days": "abc"}
            )


class TestAds(unittest.TestCase):
    def test_ads_only_on_free_tier(self):
        self.assertTrue(should_show_ads(TIER_FREE))
        self.assertFalse(should_show_ads(TIER_TRIAL))
        self.assertFalse(should_show_ads(TIER_PREMIUM))
        self.assertTrue(should_show_ads(TierManager(tier=TIER_FREE)))
        self.assertFalse(should_show_ads(TierManager(tier=TIER_PREMIUM)))
        # Expired trial folds to free: ads return, no crash.
        clock = FakeClock(now=5_000_000.0)
        expired = TierManager(
            tier=TIER_TRIAL,
            trial_started_at=1_000_000.0,
            trial_days=14,
            clock=clock,
        )
        self.assertTrue(expired.is_trial_expired())
        self.assertTrue(should_show_ads(expired))

    def test_ad_policy_hides_promos_for_paying_tiers(self):
        self.assertIsNotNone(AdPolicy(TierManager(tier=TIER_FREE)).promo_for_current_tier())
        self.assertIsNone(AdPolicy(TierManager(tier=TIER_PREMIUM)).promo_for_current_tier())
        clock = FakeClock()
        trial = TierManager(
            tier=TIER_TRIAL, trial_started_at=clock.now, clock=clock
        )
        self.assertIsNone(AdPolicy(trial).promo_for_current_tier())

    def test_ad_slot_renders_offline_house_content_without_tracking(self):
        slot = AdSlot(slot_id="library-footer")
        content = slot.render()
        self.assertEqual(content["kind"], "house_placeholder")
        self.assertTrue(content["title"])
        self.assertTrue(content["body"])
        self.assertTrue(slot.available_offline())
        self.assertEqual(AdSlot.tracking_urls_fetched(), [])
        # No remote/tracking URLs anywhere in rendered content or inventory.
        blob = json.dumps(content) + json.dumps(HOUSE_PROMOS)
        self.assertNotIn("http://", blob)
        self.assertNotIn("https://", blob)
        self.assertEqual(content["slot"], "library-footer")
        self.assertIn(content["title"], slot.render_text())

    def test_ad_module_imports_no_network_capable_libraries(self):
        import pathlib
        import re

        source = pathlib.Path(__file__).resolve().parent.parent / "src" / "aquile" / "entitlements" / "ads.py"
        text = source.read_text(encoding="utf-8")
        imported = " ".join(
            line for line in text.splitlines()
            if re.match(r"\s*(import|from)\s+", line)
        )
        for forbidden in ("urllib", "requests", "httpx", "socket", "http"):
            self.assertNotIn(forbidden, imported)

    def test_full_offline_cycle_does_not_crash(self):
        clock = FakeClock()
        tiers = TierManager(tier=TIER_FREE, clock=clock)
        tiers.start_trial()
        self.assertTrue(tiers.is_trial_active())
        self.assertFalse(should_show_ads(tiers))
        revived = TierManager.from_settings_dict(tiers.to_settings_dict(), clock=clock)
        self.assertEqual(revived, tiers)
        slot = AdSlot()
        self.assertTrue(slot.render_text())
        clock.now += 30 * 86400.0
        self.assertTrue(revived.is_trial_expired())
        self.assertTrue(should_show_ads(revived))
        self.assertTrue(revived.is_enabled("epub"))


if __name__ == "__main__":
    unittest.main()
