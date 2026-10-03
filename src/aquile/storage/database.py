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

CURRENT_SCHEMA_VERSION = 4

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

            if version < 1:
                self._migrate_to_v1(conn)
            if version < 2:
                logger.info("Migrating database from version %d to %d", version, CURRENT_SCHEMA_VERSION)
                self._migrate_to_v2(conn)
            if version < 3:
                logger.info("Migrating database from version %d to %d", version, CURRENT_SCHEMA_VERSION)
                self._migrate_to_v3(conn)
            if version < 4:
                logger.info("Migrating database from version %d to %d", version, CURRENT_SCHEMA_VERSION)
                self._migrate_to_v4(conn)
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

    def _migrate_to_v2(self, conn: sqlite3.Connection):
        logger.info("Initializing schema version 2")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS reading_sessions (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_seconds REAL NOT NULL DEFAULT 0.0,
                active_seconds REAL NOT NULL DEFAULT 0.0,
                idle_seconds REAL NOT NULL DEFAULT 0.0,
                words_read INTEGER NOT NULL DEFAULT 0,
                wpm REAL NOT NULL DEFAULT 0.0,
                FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_reading_sessions_book_id ON reading_sessions (book_id);
            CREATE INDEX IF NOT EXISTS idx_reading_sessions_started_at ON reading_sessions (started_at);
            CREATE INDEX IF NOT EXISTS idx_reading_sessions_book_started ON reading_sessions (book_id, started_at DESC);

            CREATE TABLE IF NOT EXISTS reading_statistics (
                book_id TEXT PRIMARY KEY,
                total_reading_seconds REAL NOT NULL DEFAULT 0.0,
                active_reading_seconds REAL NOT NULL DEFAULT 0.0,
                total_sessions INTEGER NOT NULL DEFAULT 0,
                estimated_words_read INTEGER NOT NULL DEFAULT 0,
                average_wpm REAL NOT NULL DEFAULT 0.0,
                last_session_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_reading_statistics_book_id ON reading_statistics (book_id);

            PRAGMA user_version = 2;
        """)

    def _migrate_to_v3(self, conn: sqlite3.Connection):
        logger.info("Migrating database to schema version 3 (book favorites)")
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(books);")
        columns = {row[1] for row in cursor.fetchall()}
        if "is_favorite" not in columns:
            conn.execute("ALTER TABLE books ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0;")
        conn.execute("PRAGMA user_version = 3;")

    def _migrate_to_v4(self, conn: sqlite3.Connection):
        # WP-C theme unification: settings live in a schemaless key/value
        # table, so no ALTER TABLE is possible or needed. The migration is
        # additive and keeps all existing rows: it only ensures the new
        # accent key has its default ('turquoise') when absent, then bumps
        # the version. Unknown legacy values are left untouched; the
        # SettingsRepository falls back to defaults when reading them.
        logger.info("Migrating database to schema version 4 (theme accent default)")
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('accent', 'turquoise');"
        )
        conn.execute("PRAGMA user_version = 4;")

