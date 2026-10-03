"""
Local-only sync status model for WP-14 (FR-17 / FR-19).

Per PRD FR-17 / FR-20 and G0 clean-room bounds, there is no authorized
cloud sync endpoint in this build. SyncState therefore tracks only local
exchange truthfully:

- ``"local-only"``: never exported or imported.
- ``"exported"``: the most recent exchange was a local bundle export.
- ``"imported"``: the most recent exchange was a local bundle import.

Status strings never claim ``"synced"`` or ``"uploaded"``: a local export
writes a file the user carries themselves; no network upload occurs here.

Token handling: sign-out clears stored credentials via an explicit
TokenStore interface. The default in-memory store is used in tests; on
real desktops the SecretServiceTokenStore below attempts the freedesktop
Secret Service (``secretstorage``) when available and falls back to
memory, so no plaintext secret is written to app preferences (NFR-05).
"""

import abc
import time
from dataclasses import dataclass, field
from typing import Dict, Optional


STATUS_LOCAL_ONLY = "local-only"
STATUS_EXPORTED = "exported"
STATUS_IMPORTED = "imported"

_TRUTHFUL_STATUSES = (STATUS_LOCAL_ONLY, STATUS_EXPORTED, STATUS_IMPORTED)


class TokenStore(abc.ABC):
    """Explicit credential-store interface (NFR-05)."""

    @abc.abstractmethod
    def get_token(self, account_id: str) -> Optional[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def set_token(self, account_id: str, token: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def clear(self) -> None:
        """Remove all stored tokens (used by sign-out)."""
        raise NotImplementedError


class InMemoryTokenStore(TokenStore):
    """Process-memory token store. Used in tests and as a safe fallback."""

    def __init__(self):
        self._tokens: Dict[str, str] = {}

    def get_token(self, account_id: str) -> Optional[str]:
        return self._tokens.get(account_id)

    def set_token(self, account_id: str, token: str) -> None:
        self._tokens[account_id] = token

    def clear(self) -> None:
        self._tokens.clear()


class SecretServiceTokenStore(TokenStore):
    """Freedesktop Secret Service compatible store with memory fallback.

    Uses ``secretstorage`` only when installed; otherwise behaves like
    :class:`InMemoryTokenStore`. No secret is ever written to plaintext
    app preferences by this class.
    """

    COLLECTION_LABEL = "Aquile Reader"

    def __init__(self, fallback: Optional[TokenStore] = None):
        self._fallback: TokenStore = fallback or InMemoryTokenStore()

    def _secretstorage(self):
        try:
            import secretstorage  # type: ignore
            return secretstorage
        except Exception:
            return None

    def get_token(self, account_id: str) -> Optional[str]:
        module = self._secretstorage()
        if module is None:
            return self._fallback.get_token(account_id)
        try:
            bus = module.dbus_init()
            collection = module.get_default_collection(bus)
            if collection.is_locked():
                collection.unlock()
            for item in collection.get_all_items():
                if item.get_label() == f"aquile:{account_id}":
                    return item.get_secret().decode("utf-8")
            return self._fallback.get_token(account_id)
        except Exception:
            return self._fallback.get_token(account_id)

    def set_token(self, account_id: str, token: str) -> None:
        module = self._secretstorage()
        if module is None:
            self._fallback.set_token(account_id, token)
            return
        try:
            bus = module.dbus_init()
            collection = module.get_default_collection(bus)
            if collection.is_locked():
                collection.unlock()
            collection.create_item(
                f"aquile:{account_id}",
                {"application": "aquile-reader", "account": account_id},
                token.encode("utf-8"),
                replace=True,
            )
        except Exception:
            self._fallback.set_token(account_id, token)

    def clear(self) -> None:
        module = self._secretstorage()
        if module is not None:
            try:
                bus = module.dbus_init()
                collection = module.get_default_collection(bus)
                if collection.is_locked():
                    collection.unlock()
                for item in list(collection.get_all_items()):
                    attrs = item.get_attributes()
                    if attrs.get("application") == "aquile-reader":
                        item.delete()
            except Exception:
                pass
        self._fallback.clear()


@dataclass
class SyncState:
    """Local-only exchange status (FR-17 truthful status, FR-20 offline)."""

    last_export_at: Optional[float] = None
    last_import_at: Optional[float] = None
    pending_changes: int = 0
    account_id: Optional[str] = None
    signed_in: bool = False

    def mark_local_change(self, count: int = 1) -> None:
        self.pending_changes += max(0, int(count))

    def mark_exported(self, timestamp: Optional[float] = None) -> None:
        self.last_export_at = timestamp if timestamp is not None else time.time()
        self.pending_changes = 0

    def mark_imported(self, timestamp: Optional[float] = None) -> None:
        self.last_import_at = timestamp if timestamp is not None else time.time()

    def status(self) -> str:
        """One of ``local-only`` / ``exported`` / ``imported`` (never synced)."""
        if self.last_export_at is None and self.last_import_at is None:
            return STATUS_LOCAL_ONLY
        if self.last_import_at is not None and (
            self.last_export_at is None or self.last_import_at >= self.last_export_at
        ):
            return STATUS_IMPORTED
        return STATUS_EXPORTED

    def describe(self) -> str:
        """Human-readable truthful status; never claims upload/sync success."""
        base = self.status()
        if base == STATUS_LOCAL_ONLY:
            if self.pending_changes > 0:
                return f"local-only with {self.pending_changes} pending change(s)"
            return "local-only"
        if base == STATUS_EXPORTED:
            detail = f"exported at {self.last_export_at:.0f} to a local file (no cloud upload)"
            if self.pending_changes > 0:
                detail += f" with {self.pending_changes} pending change(s)"
            return detail
        detail = f"imported at {self.last_import_at:.0f} from a local file"
        if self.pending_changes > 0:
            detail += f" with {self.pending_changes} pending change(s)"
        return detail

    def sign_in_local(self, account_id: str, token_store: TokenStore, token: str) -> None:
        """Record a local placeholder sign-in without contacting any server."""
        token_store.set_token(account_id, token)
        self.account_id = account_id
        self.signed_in = True

    def sign_out(self, token_store: TokenStore) -> None:
        """Clear credentials; local books/annotations are retained (NFR-02)."""
        token_store.clear()
        self.account_id = None
        self.signed_in = False


__all__ = [
    "STATUS_LOCAL_ONLY",
    "STATUS_EXPORTED",
    "STATUS_IMPORTED",
    "TokenStore",
    "InMemoryTokenStore",
    "SecretServiceTokenStore",
    "SyncState",
]
