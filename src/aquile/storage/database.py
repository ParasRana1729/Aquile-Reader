"""
SQLite Database Connection and Schema Management for Aquile Reader.
Enforces WAL mode, atomic transactions, and versioned schema migrations (NFR-01, NFR-02).
"""

import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Optional, Generator

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = 1

def get_default_db_path() -> str:
    xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    data_dir = os.path.join(xdg_data, "aquile-reader")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "aquile.db")

class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_default_db_path()
        self._init_database()

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # WAL mode provides concurrent read performance and durability
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA user_version;")
            version = cursor.fetchone()[0]

            if version == 0:
                self._migrate_to_v1(conn)
            elif version < CURRENT_SCHEMA_VERSION:
                logger.info("Migrating database from version %d to %d", version, CURRENT_SCHEMA_VERSION)
                # Future version migrations
            conn.commit()

    def _migrate_to_v1(self, conn: sqlite3.Connection):
        logger.info("Initializing schema version 1")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                file_format TEXT NOT NULL,
                cover_path TEXT,
                total_chapters INTEGER DEFAULT 1,
                file_size_bytes INTEGER DEFAULT 0,
                added_at REAL NOT NULL,
                last_read_at REAL
            );

            CREATE TABLE IF NOT EXISTS reading_progress (
                book_id TEXT PRIMARY KEY,
                chapter_index INTEGER NOT NULL DEFAULT 0,
                page_index INTEGER NOT NULL DEFAULT 0,
                cfi TEXT NOT NULL DEFAULT '',
                percentage REAL NOT NULL DEFAULT 0.0,
                updated_at REAL NOT NULL,
                FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS annotations (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                chapter_index INTEGER NOT NULL,
                cfi TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                text_content TEXT NOT NULL,
                note_text TEXT DEFAULT '',
                color TEXT NOT NULL DEFAULT '#FFEB3B',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            PRAGMA user_version = 1;
        """)
