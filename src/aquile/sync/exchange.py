"""
Authorized local exchange bundle for WP-14 (FR-17 / FR-19).

Clean-room boundary (docs/rights/G0_APPROVAL.md): proprietary sync DBs and
undocumented cloud APIs are out of bounds. This module implements only an
authorized local exchange: a zip bundle (JSON manifest + metadata, progress,
annotations, sessions) with stable IDs and SHA-256 checksums.

Conflict rule (per PRD FR-17): newer-wins by ``updated_at``. An incoming
record never silently overwrites a newer local record. Import reports what
was added / updated / skipped so callers can show truthful status.

Security (NFR-06): safe zip handling -- traversal block, unexpected entry
rejection is lenient but traversal is fatal, uncompressed size cap to bound
decompression abuse. No extraction to disk; entries are read in memory.

Upload truthfulness (FR-17): this module performs local file exchange only.
It never claims an unsent upload succeeded. See ``sync_state.SyncState``
for truthful status strings.

Only the Python standard library is used (zipfile / json / hashlib).
"""

import hashlib
import json
import os
import tempfile
import time
import zipfile


EXCHANGE_FORMAT = "aquile-exchange"
EXCHANGE_VERSION = 1

MANIFEST_NAME = "manifest.json"
BOOK_NAME = "book.json"
PROGRESS_NAME = "progress.json"
ANNOTATIONS_NAME = "annotations.json"
SESSIONS_NAME = "sessions.json"

KNOWN_FILES = (MANIFEST_NAME, BOOK_NAME, PROGRESS_NAME, ANNOTATIONS_NAME, SESSIONS_NAME)

# Bound total uncompressed payload to block decompression abuse (NFR-06).
# Annotations + progress + sessions for one book are kilobytes; 64 MiB is
# generous while still bounding memory use.
MAX_BUNDLE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_FILES_IN_BUNDLE = 16


class ExchangeError(Exception):
    """Base error for exchange bundle failures."""


class CorruptBundleError(ExchangeError):
    """Raised when a bundle is not a valid zip or fails validation."""


class UnsafeBundleError(ExchangeError):
    """Raised when a bundle contains unsafe entry names."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _checksum_of(obj) -> str:
    return _sha256_bytes(_canonical_bytes(obj))


def _now() -> float:
    return time.time()


def _is_safe_name(name: str) -> bool:
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    if name.startswith("~"):
        return False
    # Windows drive letter, e.g. C:\... or C:/...
    if len(name) >= 2 and name[1] == ":":
        return False
    if ".." in name.split("/"):
        return False
    if ".." in name.split("\\"):
        return False
    normalized = os.path.normpath(name)
    if normalized.startswith("..") or os.path.isabs(normalized):
        return False
    if normalized != name:
        # Reject ./ prefixes, redundant separators, trailing slashes.
        return False
    return True


def _content_hash_of_file(path: str):
    """SHA-256 of a local book file, or None when unavailable."""
    try:
        if not path or not os.path.isfile(path):
            return None
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 64), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _book_to_dict(book) -> dict:
    return {
        "id": getattr(book, "id", ""),
        "title": getattr(book, "title", "Untitled"),
        "author": getattr(book, "author", "Unknown Author"),
        "file_path": getattr(book, "file_path", ""),
        "file_format": getattr(book, "file_format", "epub"),
        "cover_path": getattr(book, "cover_path", None),
        "total_chapters": getattr(book, "total_chapters", 1),
        "file_size_bytes": getattr(book, "file_size_bytes", 0),
        "added_at": getattr(book, "added_at", _now()),
        "last_read_at": getattr(book, "last_read_at", None),
        "content_sha256": _content_hash_of_file(getattr(book, "file_path", "")),
    }


def _progress_to_dict(progress) -> dict | None:
    if progress is None:
        return None
    return {
        "book_id": getattr(progress, "book_id", ""),
        "chapter_index": getattr(progress, "chapter_index", 0),
        "page_index": getattr(progress, "page_index", 0),
        "cfi": getattr(progress, "cfi", ""),
        "percentage": getattr(progress, "percentage", 0.0),
        "updated_at": getattr(progress, "updated_at", _now()),
    }


def _annotation_to_dict(ann) -> dict:
    return {
        "id": getattr(ann, "id", ""),
        "book_id": getattr(ann, "book_id", ""),
        "chapter_index": getattr(ann, "chapter_index", 0),
        "cfi": getattr(ann, "cfi", ""),
        "start_offset": getattr(ann, "start_offset", 0),
        "end_offset": getattr(ann, "end_offset", 0),
        "text_content": getattr(ann, "text_content", ""),
        "note_text": getattr(ann, "note_text", ""),
        "color": getattr(ann, "color", "#FFEB3B"),
        "created_at": getattr(ann, "created_at", _now()),
        "updated_at": getattr(ann, "updated_at", _now()),
    }


def _session_to_dict(session) -> dict:
    started = getattr(session, "started_at", None)
    ended = getattr(session, "ended_at", None)
    return {
        "id": getattr(session, "id", ""),
        "book_id": getattr(session, "book_id", ""),
        "started_at": started.isoformat() if hasattr(started, "isoformat") else str(started),
        "ended_at": (ended.isoformat() if hasattr(ended, "isoformat") else (str(ended) if ended is not None else None)),
        "duration_seconds": float(getattr(session, "duration_seconds", 0.0)),
        "active_seconds": float(getattr(session, "active_seconds", 0.0)),
        "idle_seconds": float(getattr(session, "idle_seconds", 0.0)),
        "words_read": int(getattr(session, "words_read", 0)),
        "wpm": float(getattr(session, "wpm", 0.0)),
    }


def _dict_to_book(data: dict):
    # Local import to keep module importable without storage deps.
    from ..domain.models import Book

    allowed = {"id", "title", "author", "file_path", "file_format",
               "cover_path", "total_chapters", "file_size_bytes",
               "added_at", "last_read_at"}
    filtered = {k: v for k, v in data.items() if k in allowed}
    return Book(**filtered)


def _dict_to_progress(data: dict):
    from ..domain.models import ReadingProgress

    return ReadingProgress(
        book_id=data.get("book_id", ""),
        chapter_index=int(data.get("chapter_index", 0)),
        page_index=int(data.get("page_index", 0)),
        cfi=data.get("cfi", ""),
        percentage=float(data.get("percentage", 0.0)),
        updated_at=float(data.get("updated_at", _now())),
    )


def _dict_to_annotation(data: dict):
    from ..domain.models import Annotation

    return Annotation(
        id=data.get("id", ""),
        book_id=data.get("book_id", ""),
        chapter_index=int(data.get("chapter_index", 0)),
        cfi=data.get("cfi", ""),
        start_offset=int(data.get("start_offset", 0)),
        end_offset=int(data.get("end_offset", 0)),
        text_content=data.get("text_content", ""),
        note_text=data.get("note_text", ""),
        color=data.get("color", "#FFEB3B"),
        created_at=float(data.get("created_at", _now())),
        updated_at=float(data.get("updated_at", _now())),
    )


def _dict_to_session(data: dict):
    from datetime import datetime, timezone

    from ..domain.models import ReadingSession

    def _parse(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = datetime.fromisoformat(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)

    started = _parse(data.get("started_at")) or datetime.now(timezone.utc)
    ended = _parse(data.get("ended_at")) if data.get("ended_at") is not None else None
    return ReadingSession(
        id=data.get("id", ""),
        book_id=data.get("book_id", ""),
        started_at=started,
        ended_at=ended,
        duration_seconds=float(data.get("duration_seconds", 0.0)),
        active_seconds=float(data.get("active_seconds", 0.0)),
        idle_seconds=float(data.get("idle_seconds", 0.0)),
        words_read=int(data.get("words_read", 0)),
        wpm=float(data.get("wpm", 0.0)),
    )


def _book_recency(book_dict: dict) -> float:
    """Newer-wins ordering key for book metadata (last_read_at, else added_at)."""
    last_read = book_dict.get("last_read_at")
    added = book_dict.get("added_at", 0.0)
    try:
        if last_read is not None:
            return float(last_read)
    except (TypeError, ValueError):
        pass
    try:
        return float(added or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _find_local_annotation(ann_repo, ann_id: str, book_id: str):
    """Locate a local annotation by stable id, or None."""
    candidates = []
    try:
        candidates = ann_repo.get_by_book(book_id) or []
    except Exception:
        candidates = []
    for ann in candidates:
        if getattr(ann, "id", None) == ann_id:
            return ann
    # Fall back to cross-book scan (handles remapped book ids).
    try:
        for ann in ann_repo.list_all() or []:
            if getattr(ann, "id", None) == ann_id:
                return ann
    except Exception:
        pass
    return None


def _collect_sessions(stats_repo, book_id: str) -> list:
    if stats_repo is None:
        return []
    getter = getattr(stats_repo, "get_sessions_for_book", None)
    if getter is None:
        return []
    try:
        sessions = getter(book_id, limit=10000) or []
    except TypeError:
        try:
            sessions = getter(book_id) or []
        except Exception:
            return []
    except Exception:
        return []
    return list(sessions)


def _unpack_repos(book_repo=None, progress_repo=None, ann_repo=None,
                  stats_repo=None, repos=None):
    """Accept either positional repos or a single dict of repos."""
    if isinstance(book_repo, dict) and progress_repo is None:
        repos = book_repo
        book_repo = progress_repo = ann_repo = stats_repo = None
    if repos is not None:
        book_repo = repos.get("book_repo", repos.get("book", book_repo))
        progress_repo = repos.get("progress_repo", repos.get("progress", progress_repo))
        ann_repo = repos.get("ann_repo", repos.get("annotations", ann_repo))
        stats_repo = repos.get("stats_repo", repos.get("stats", stats_repo))
    return book_repo, progress_repo, ann_repo, stats_repo


class ExchangeBundle:
    """Authorized local exchange bundle (FR-17 / FR-19)."""

    FORMAT = EXCHANGE_FORMAT
    VERSION = EXCHANGE_VERSION
    MAX_BYTES = MAX_BUNDLE_UNCOMPRESSED_BYTES

    @staticmethod
    def export_book(book_id, book_repo, progress_repo, ann_repo,
                     stats_repo=None, dest_path=None, dest_dir=None) -> str:
        """Export one book's state to a zip bundle; returns the zip path."""
        book = book_repo.get_by_id(book_id)
        if book is None:
            raise ExchangeError(f"unknown book id: {book_id!r}")

        try:
            progress = progress_repo.get(book_id) if progress_repo is not None else None
        except Exception:
            progress = None
        try:
            annotations = list(ann_repo.get_by_book(book_id)) if ann_repo is not None else []
        except Exception:
            annotations = []
        sessions = _collect_sessions(stats_repo, book_id)

        book_dict = _book_to_dict(book)
        progress_dict = _progress_to_dict(progress)
        annotation_dicts = [_annotation_to_dict(a) for a in annotations]
        annotation_dicts.sort(key=lambda d: (str(d.get("id", ""))))
        session_dicts = [_session_to_dict(s) for s in sessions]
        session_dicts.sort(key=lambda d: (str(d.get("started_at", "")), str(d.get("id", ""))))

        payload_book = _canonical_bytes(book_dict)
        payload_progress = _canonical_bytes(progress_dict)
        payload_annotations = _canonical_bytes(annotation_dicts)
        payload_sessions = _canonical_bytes(session_dicts)

        manifest = {
            "format": EXCHANGE_FORMAT,
            "version": EXCHANGE_VERSION,
            "exported_at": _now(),
            "book_id": book_dict.get("id", ""),
            "files": {
                BOOK_NAME: _sha256_bytes(payload_book),
                PROGRESS_NAME: _sha256_bytes(payload_progress),
                ANNOTATIONS_NAME: _sha256_bytes(payload_annotations),
                SESSIONS_NAME: _sha256_bytes(payload_sessions),
            },
        }
        payload_manifest = _canonical_bytes(manifest)

        if dest_path is None:
            target_dir = dest_dir or tempfile.gettempdir()
            os.makedirs(target_dir, exist_ok=True)
            safe_id = "".join(c if (c.isalnum() or c in ("-", "_")) else "_" for c in str(book_id)) or "book"
            dest_path = os.path.join(target_dir, f"aquile-exchange-{safe_id}.zip")
        else:
            parent = os.path.dirname(os.path.abspath(dest_path))
            if parent:
                os.makedirs(parent, exist_ok=True)

        with zipfile.ZipFile(dest_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_NAME, payload_manifest)
            archive.writestr(BOOK_NAME, payload_book)
            archive.writestr(PROGRESS_NAME, payload_progress)
            archive.writestr(ANNOTATIONS_NAME, payload_annotations)
            archive.writestr(SESSIONS_NAME, payload_sessions)
        return dest_path

    @staticmethod
    def import_bundle(zip_path, book_repo=None, progress_repo=None,
                       ann_repo=None, stats_repo=None, repos=None) -> dict:
        """Validate and merge a bundle into local repos (newer-wins).

        Returns a summary dict with added / updated / skipped counts.
        Raises CorruptBundleError on invalid content and UnsafeBundleError
        on traversal attempts.
        """
        book_repo, progress_repo, ann_repo, stats_repo = _unpack_repos(
            book_repo, progress_repo, ann_repo, stats_repo, repos)
        if book_repo is None or progress_repo is None or ann_repo is None:
            raise ExchangeError("import_bundle requires book_repo, progress_repo, ann_repo")

        if not zip_path or not os.path.isfile(zip_path):
            raise CorruptBundleError(f"bundle not found: {zip_path!r}")
        if not zipfile.is_zipfile(zip_path):
            raise CorruptBundleError("not a zip bundle")

        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                infos = archive.infolist()
                if len(infos) > MAX_FILES_IN_BUNDLE:
                    raise CorruptBundleError("too many files in bundle")
                total_uncompressed = sum(i.file_size for i in infos)
                if total_uncompressed > MAX_BUNDLE_UNCOMPRESSED_BYTES:
                    raise CorruptBundleError("bundle exceeds size cap")
                for info in infos:
                    if not _is_safe_name(info.filename):
                        raise UnsafeBundleError(f"unsafe entry: {info.filename!r}")
                    if info.file_size > MAX_BUNDLE_UNCOMPRESSED_BYTES:
                        raise CorruptBundleError("bundle entry exceeds size cap")
                if MANIFEST_NAME not in archive.namelist():
                    raise CorruptBundleError("missing manifest.json")
                raw = {}
                for info in infos:
                    raw[info.filename] = archive.read(info.filename)
        except (UnsafeBundleError, CorruptBundleError):
            raise
        except zipfile.BadZipFile as exc:
            raise CorruptBundleError(f"bad zip bundle: {exc}") from exc
        except ExchangeError:
            raise
        except Exception as exc:
            raise CorruptBundleError(f"cannot read bundle: {exc}") from exc

        try:
            manifest = json.loads(raw[MANIFEST_NAME].decode("utf-8"))
        except Exception as exc:
            raise CorruptBundleError(f"invalid manifest: {exc}") from exc
        if manifest.get("format") != EXCHANGE_FORMAT:
            raise CorruptBundleError("unknown bundle format")
        if manifest.get("version") != EXCHANGE_VERSION:
            raise CorruptBundleError("unsupported bundle version")
        filesums = manifest.get("files") or {}
        for name in (BOOK_NAME, PROGRESS_NAME, ANNOTATIONS_NAME, SESSIONS_NAME):
            if name not in raw:
                raise CorruptBundleError(f"missing {name}")
            expected = filesums.get(name)
            actual = _sha256_bytes(raw[name])
            if expected != actual:
                raise CorruptBundleError(f"checksum mismatch: {name}")

        try:
            book_dict = json.loads(raw[BOOK_NAME].decode("utf-8"))
            progress_dict = json.loads(raw[PROGRESS_NAME].decode("utf-8"))
            annotation_dicts = json.loads(raw[ANNOTATIONS_NAME].decode("utf-8"))
            session_dicts = json.loads(raw[SESSIONS_NAME].decode("utf-8"))
        except Exception as exc:
            raise CorruptBundleError(f"invalid bundle payload: {exc}") from exc
        if not isinstance(book_dict, dict) or not book_dict.get("id"):
            raise CorruptBundleError("invalid book metadata")
        if progress_dict is not None and not isinstance(progress_dict, dict):
            raise CorruptBundleError("invalid progress payload")
        if not isinstance(annotation_dicts, list):
            raise CorruptBundleError("invalid annotations payload")
        if not isinstance(session_dicts, list):
            raise CorruptBundleError("invalid sessions payload")

        incoming_id = str(book_dict.get("id", ""))
        incoming_path = str(book_dict.get("file_path", "") or "")
        incoming_hash = book_dict.get("content_sha256")

        # Duplicate detection by stable id, then by path, then by content hash.
        local_book = None
        book_created = False
        book_duplicate = False
        target_book_id = incoming_id
        try:
            local_book = book_repo.get_by_id(incoming_id)
        except Exception:
            local_book = None
        if local_book is None and incoming_path:
            try:
                by_path = book_repo.get_by_path(incoming_path)
            except Exception:
                by_path = None
            if by_path is not None:
                local_book = by_path
                book_duplicate = True
                target_book_id = getattr(by_path, "id", incoming_id)
        if local_book is None and incoming_hash:
            try:
                for candidate in book_repo.list_all() or []:
                    if getattr(candidate, "id", "") == incoming_id:
                        continue
                    local_hash = _content_hash_of_file(getattr(candidate, "file_path", ""))
                    if local_hash and local_hash == incoming_hash:
                        local_book = candidate
                        book_duplicate = True
                        target_book_id = getattr(candidate, "id", incoming_id)
                        break
            except Exception:
                pass

        if local_book is None:
            book_repo.add(_dict_to_book(book_dict))
            book_created = True
            target_book_id = incoming_id
        else:
            local_dict = _book_to_dict(local_book)
            if _book_recency(book_dict) > _book_recency(local_dict):
                merged = dict(local_dict)
                for key in ("title", "author", "file_format", "cover_path",
                            "total_chapters", "file_size_bytes", "added_at", "last_read_at"):
                    if key in book_dict:
                        merged[key] = book_dict[key]
                # Keep the local stable id and path; never repoint silently.
                merged["id"] = getattr(local_book, "id", incoming_id)
                merged.pop("content_sha256", None)
                book_repo.add(_dict_to_book(merged))
                target_book_id = getattr(local_book, "id", incoming_id)
            else:
                target_book_id = getattr(local_book, "id", incoming_id)

        # Progress: newer-wins by updated_at.
        progress_updated = False
        progress_skipped_older = False
        if progress_dict is not None:
            progress_dict = dict(progress_dict)
            progress_dict["book_id"] = target_book_id
            incoming_ts = float(progress_dict.get("updated_at", 0.0) or 0.0)
            try:
                local_progress = progress_repo.get(target_book_id)
            except Exception:
                local_progress = None
            if local_progress is None:
                # No local progress: import only when the payload is non-empty
                # or explicitly carries a timestamp (avoids resurrecting blanks).
                is_blank = (
                    int(progress_dict.get("chapter_index", 0)) == 0
                    and int(progress_dict.get("page_index", 0)) == 0
                    and not str(progress_dict.get("cfi", "") or "")
                    and float(progress_dict.get("percentage", 0.0) or 0.0) == 0.0
                )
                if not is_blank:
                    progress_repo.save(_dict_to_progress(progress_dict))
                    progress_updated = True
            else:
                try:
                    local_ts = float(getattr(local_progress, "updated_at", 0.0) or 0.0)
                except (TypeError, ValueError):
                    local_ts = 0.0
                if incoming_ts > local_ts:
                    progress_repo.save(_dict_to_progress(progress_dict))
                    progress_updated = True
                else:
                    progress_skipped_older = True

        # Annotations: newer-wins by updated_at, keyed by stable id.
        annotations_added = 0
        annotations_updated = 0
        annotations_skipped_older = 0
        for entry in annotation_dicts:
            if not isinstance(entry, dict) or not entry.get("id"):
                continue
            entry = dict(entry)
            entry["book_id"] = target_book_id
            try:
                incoming_ts = float(entry.get("updated_at", 0.0) or 0.0)
            except (TypeError, ValueError):
                incoming_ts = 0.0
            existing = _find_local_annotation(ann_repo, str(entry.get("id")), target_book_id)
            if existing is None:
                ann_repo.add(_dict_to_annotation(entry))
                annotations_added += 1
            else:
                try:
                    local_ts = float(getattr(existing, "updated_at", 0.0) or 0.0)
                except (TypeError, ValueError):
                    local_ts = 0.0
                if incoming_ts > local_ts:
                    ann_repo.add(_dict_to_annotation(entry))
                    annotations_updated += 1
                else:
                    annotations_skipped_older += 1

        # Sessions: append-only by stable id; never delete local sessions.
        sessions_imported = 0
        if stats_repo is not None and session_dicts:
            existing_ids = set()
            try:
                for sess in _collect_sessions(stats_repo, target_book_id):
                    existing_ids.add(getattr(sess, "id", ""))
            except Exception:
                existing_ids = set()
            recorder = getattr(stats_repo, "record_session", None)
            if recorder is not None:
                for entry in session_dicts:
                    if not isinstance(entry, dict) or not entry.get("id"):
                        continue
                    if str(entry.get("id")) in existing_ids:
                        continue
                    entry = dict(entry)
                    entry["book_id"] = target_book_id
                    try:
                        recorder(_dict_to_session(entry))
                        existing_ids.add(str(entry.get("id")))
                        sessions_imported += 1
                    except Exception:
                        continue

        return {
            "book_id": target_book_id,
            "incoming_book_id": incoming_id,
            "book_created": book_created,
            "book_duplicate": book_duplicate,
            "progress_updated": progress_updated,
            "progress_skipped_older": progress_skipped_older,
            "annotations_added": annotations_added,
            "annotations_updated": annotations_updated,
            "annotations_skipped_older": annotations_skipped_older,
            "sessions_imported": sessions_imported,
        }


def export_book(book_id, book_repo, progress_repo, ann_repo,
                stats_repo=None, dest_path=None, dest_dir=None) -> str:
    """Module-level wrapper for :meth:`ExchangeBundle.export_book`."""
    return ExchangeBundle.export_book(
        book_id, book_repo, progress_repo, ann_repo,
        stats_repo=stats_repo, dest_path=dest_path, dest_dir=dest_dir)


def import_bundle(zip_path, book_repo=None, progress_repo=None,
                   ann_repo=None, stats_repo=None, repos=None) -> dict:
    """Module-level wrapper for :meth:`ExchangeBundle.import_bundle`."""
    return ExchangeBundle.import_bundle(
        zip_path, book_repo, progress_repo, ann_repo,
        stats_repo=stats_repo, repos=repos)
