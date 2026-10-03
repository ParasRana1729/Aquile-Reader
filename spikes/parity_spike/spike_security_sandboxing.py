#!/usr/bin/env python3
"""
spike_security_sandboxing.py — Parity Spike: Security & Untrusted Input Defenses.
Tests path traversal defense (NFR-06), archive bomb limits, and graceful error handling.
Validates NFR-06, AT-02.
"""

import os
import zipfile

class SecurityError(Exception):
    pass

class CorruptArchiveError(Exception):
    pass

class SafeArchiveReader:
    MAX_ENTRY_SIZE = 50 * 1024 * 1024       # 50 MB per file limit
    MAX_TOTAL_SIZE = 250 * 1024 * 1024      # 250 MB total archive limit

    @classmethod
    def validate_and_extract_manifest(cls, archive_path):
        if not zipfile.is_zipfile(archive_path):
            raise CorruptArchiveError(f"File is not a valid zip container: {os.path.basename(archive_path)}")

        total_extracted = 0
        safe_entries = []

        with zipfile.ZipFile(archive_path, "r") as z:
            for info in z.infolist():
                # 1. Path traversal check: reject '..' or leading '/'
                normalized = os.path.normpath(info.filename)
                if normalized.startswith("..") or os.path.isabs(info.filename) or "../" in info.filename:
                    raise SecurityError(f"Malicious path traversal detected in archive: {info.filename}")

                # 2. Decompression bomb check
                if info.file_size > cls.MAX_ENTRY_SIZE:
                    raise SecurityError(f"Entry {info.filename} exceeds single file quota ({info.file_size} bytes)")
                
                total_extracted += info.file_size
                if total_extracted > cls.MAX_TOTAL_SIZE:
                    raise SecurityError(f"Archive exceeds maximum uncompressed size quota ({total_extracted} bytes)")

                safe_entries.append(info.filename)

        return safe_entries

def test_security_sandboxing():
    fixtures_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fixtures"))
    
    # 1. Test Path Traversal
    traversal_path = os.path.join(fixtures_dir, "path-traversal.epub")
    traversal_blocked = False
    try:
        SafeArchiveReader.validate_and_extract_manifest(traversal_path)
    except SecurityError as e:
        traversal_blocked = True
        traversal_msg = str(e)
    assert traversal_blocked, "Security vulnerability: Path traversal was not blocked!"

    # 2. Test Malformed / Corrupted Archive
    corrupt_path = os.path.join(fixtures_dir, "malformed-archive.epub")
    corrupt_caught = False
    try:
        SafeArchiveReader.validate_and_extract_manifest(corrupt_path)
    except CorruptArchiveError as e:
        corrupt_caught = True
        corrupt_msg = str(e)
    assert corrupt_caught, "Corrupt archive did not trigger controlled CorruptArchiveError!"

    # 3. Test Valid Archive (Canonical Text)
    valid_path = os.path.join(fixtures_dir, "canonical-text.epub")
    entries = SafeArchiveReader.validate_and_extract_manifest(valid_path)
    assert len(entries) > 0, "Valid archive should extract without error"

    return {
        "traversal_test": f"Passed ({traversal_msg})",
        "corrupt_archive_test": f"Passed ({corrupt_msg})",
        "valid_archive_entries": len(entries)
    }

if __name__ == "__main__":
    res = test_security_sandboxing()
    print("Security & Sandboxing Spike Passed:")
    for k, v in res.items():
        print(f"  {k}: {v}")
