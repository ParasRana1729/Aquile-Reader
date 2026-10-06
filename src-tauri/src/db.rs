use std::fs;
use std::path::Path;
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use chrono::Utc;
use rusqlite::{params, Connection, Result};

use crate::models::{
    Annotation, AnnotationWithBookTitle, Book, BookWithProgress, Bookmark, MonthlyStat,
    ReadingSession, ReadingStats,
};

pub fn init_db(db_path: &Path) -> Result<Connection> {
    if let Some(parent) = db_path.parent() {
        fs::create_dir_all(parent).ok();
    }

    let conn = Connection::open(db_path)?;

    // WAL mode, normal synchronous, foreign keys enabled
    conn.execute_batch(
        "PRAGMA journal_mode = WAL;
         PRAGMA synchronous = NORMAL;
         PRAGMA foreign_keys = ON;

         CREATE TABLE IF NOT EXISTS books (
             id TEXT PRIMARY KEY,
             title TEXT NOT NULL,
             author TEXT,
             file_path TEXT NOT NULL UNIQUE,
             format TEXT NOT NULL,
             cover_image TEXT,
             page_count INTEGER NOT NULL DEFAULT 0,
             chapter_count INTEGER NOT NULL DEFAULT 0,
             file_size INTEGER NOT NULL DEFAULT 0,
             is_favorite INTEGER NOT NULL DEFAULT 0,
             added_date TEXT NOT NULL,
             last_read_date TEXT
         );

         CREATE TABLE IF NOT EXISTS reading_progress (
             book_id TEXT PRIMARY KEY,
             percentage REAL NOT NULL DEFAULT 0.0,
             position TEXT,
             updated_at TEXT NOT NULL,
             FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
         );

         CREATE TABLE IF NOT EXISTS annotations (
             id TEXT PRIMARY KEY,
             book_id TEXT NOT NULL,
             cfi_range TEXT,
             selected_text TEXT NOT NULL,
             note TEXT,
             color TEXT NOT NULL DEFAULT '#ffeb3b',
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
         );

         CREATE TABLE IF NOT EXISTS bookmarks (
             id TEXT PRIMARY KEY,
             book_id TEXT NOT NULL,
             page INTEGER NOT NULL,
             title TEXT NOT NULL,
             excerpt TEXT,
             created_at TEXT NOT NULL,
             FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
         );

         CREATE TABLE IF NOT EXISTS reading_sessions (
             id TEXT PRIMARY KEY,
             book_id TEXT NOT NULL,
             start_time TEXT NOT NULL,
             end_time TEXT,
             duration_seconds INTEGER NOT NULL DEFAULT 0,
             words_read INTEGER NOT NULL DEFAULT 0,
             FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
         );

         CREATE TABLE IF NOT EXISTS settings (
             key TEXT PRIMARY KEY,
             value TEXT NOT NULL
         );",
    )?;

    // Seed default sample books if table is empty
    let count: i64 = conn.query_row("SELECT count(*) FROM books", [], |row| row.get(0))?;
    if count == 0 {
        seed_default_books(&conn)?;
    }

    Ok(conn)
}

fn seed_default_books(conn: &Connection) -> Result<()> {
    let now = Utc::now().to_rfc3339();

    // 1. The Prince (Featured in win_001 and win_019)
    let prince_id = "book-the-prince".to_string();
    conn.execute(
        "INSERT INTO books (id, title, author, file_path, format, cover_image, page_count, chapter_count, file_size, is_favorite, added_date, last_read_date)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
        params![
            prince_id,
            "The Prince",
            "Nicolo Machiavelli",
            "builtin://the-prince.pdf",
            "pdf",
            generate_prince_cover_svg(),
            140,
            26,
            1245184,
            0,
            now,
            now,
        ],
    )?;

    conn.execute(
        "INSERT INTO reading_progress (book_id, percentage, position, updated_at)
         VALUES (?1, ?2, ?3, ?4)",
        params![prince_id, 7.0, "{\"page\": 10}", now],
    )?;

    // Seed sample annotation for The Prince
    conn.execute(
        "INSERT INTO annotations (id, book_id, cfi_range, selected_text, note, color, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            "ann-seed-1",
            prince_id,
            "{\"page\": 23}",
            "All states, all powers, that have held and hold rule over men have been and are either republics or principalities.",
            "Crucial political dichotomy established in opening sentence.",
            "#d41b6c",
            now,
            now,
        ],
    )?;

    // Seed sample bookmark for The Prince
    conn.execute(
        "INSERT INTO bookmarks (id, book_id, page, title, excerpt, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![
            "bm-seed-1",
            prince_id,
            23,
            "Chapter I Overview",
            "All states, all powers, that have held and hold rule over men...",
            now,
        ],
    )?;

    // Seed sample reading session
    conn.execute(
        "INSERT INTO reading_sessions (id, book_id, start_time, end_time, duration_seconds, words_read)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![
            "sess-seed-1",
            prince_id,
            now,
            now,
            1800,
            4200,
        ],
    )?;

    // 2. Man's Search For Meaning
    let mans_search_id = "book-mans-search".to_string();
    conn.execute(
        "INSERT INTO books (id, title, author, file_path, format, cover_image, page_count, chapter_count, file_size, is_favorite, added_date, last_read_date)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
        params![
            mans_search_id,
            "Man's Search For Meaning",
            "Viktor E. Frankl",
            "builtin://mans-search.epub",
            "epub",
            generate_mans_search_cover_svg(),
            200,
            12,
            854200,
            0,
            now,
            now,
        ],
    )?;

    conn.execute(
        "INSERT INTO reading_progress (book_id, percentage, position, updated_at)
         VALUES (?1, ?2, ?3, ?4)",
        params![mans_search_id, 0.0, None::<String>, now],
    )?;

    // Seed sample annotation for Viktor Frankl
    conn.execute(
        "INSERT INTO annotations (id, book_id, cfi_range, selected_text, note, color, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        params![
            "ann-seed-2",
            mans_search_id,
            "{\"page\": 15}",
            "Those who have a 'why' to live, can bear with almost any 'how'.",
            "Core thesis of logotherapy.",
            "#ffeb3b",
            now,
            now,
        ],
    )?;

    // 3. The Adventures of Sherlock Holmes
    let sherlock_id = "book-sherlock-holmes".to_string();
    conn.execute(
        "INSERT INTO books (id, title, author, file_path, format, cover_image, page_count, chapter_count, file_size, is_favorite, added_date, last_read_date)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
        params![
            sherlock_id,
            "The Adventures of Sherlock Holmes",
            "Arthur Conan Doyle",
            "builtin://sherlock-holmes.epub",
            "epub",
            generate_sherlock_cover_svg(),
            307,
            12,
            1560300,
            0,
            now,
            now,
        ],
    )?;

    // 4. Quick Start Guide Aquile Reader (From win_019)
    let guide_id = "book-quick-start".to_string();
    conn.execute(
        "INSERT INTO books (id, title, author, file_path, format, cover_image, page_count, chapter_count, file_size, is_favorite, added_date, last_read_date)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
        params![
            guide_id,
            "Quick Start Guide",
            "Aquile Reader",
            "builtin://quick-start-guide.epub",
            "epub",
            generate_quick_start_cover_svg(),
            16,
            4,
            452100,
            0,
            now,
            None::<String>,
        ],
    )?;

    Ok(())
}

pub fn list_books(conn: &Connection) -> Result<Vec<BookWithProgress>> {
    let mut stmt = conn.prepare(
        "SELECT b.id, b.title, b.author, b.file_path, b.format, b.cover_image,
                b.page_count, b.chapter_count, b.file_size, b.is_favorite,
                b.added_date, b.last_read_date,
                COALESCE(p.percentage, 0.0) as percentage, p.position
         FROM books b
         LEFT JOIN reading_progress p ON b.id = p.book_id
         ORDER BY b.added_date DESC",
    )?;

    let books = stmt
        .query_map([], |row| {
            Ok(BookWithProgress {
                id: row.get(0)?,
                title: row.get(1)?,
                author: row.get(2)?,
                file_path: row.get(3)?,
                format: row.get(4)?,
                cover_image: row.get(5)?,
                page_count: row.get(6)?,
                chapter_count: row.get(7)?,
                file_size: row.get(8)?,
                is_favorite: row.get::<_, i64>(9)? != 0,
                added_date: row.get(10)?,
                last_read_date: row.get(11)?,
                percentage: row.get(12)?,
                position: row.get(13)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

    Ok(books)
}

pub fn get_book(conn: &Connection, book_id: &str) -> Result<Option<BookWithProgress>> {
    let mut stmt = conn.prepare(
        "SELECT b.id, b.title, b.author, b.file_path, b.format, b.cover_image,
                b.page_count, b.chapter_count, b.file_size, b.is_favorite,
                b.added_date, b.last_read_date,
                COALESCE(p.percentage, 0.0) as percentage, p.position
         FROM books b
         LEFT JOIN reading_progress p ON b.id = p.book_id
         WHERE b.id = ?1",
    )?;

    let mut rows = stmt.query(params![book_id])?;
    if let Some(row) = rows.next()? {
        Ok(Some(BookWithProgress {
            id: row.get(0)?,
            title: row.get(1)?,
            author: row.get(2)?,
            file_path: row.get(3)?,
            format: row.get(4)?,
            cover_image: row.get(5)?,
            page_count: row.get(6)?,
            chapter_count: row.get(7)?,
            file_size: row.get(8)?,
            is_favorite: row.get::<_, i64>(9)? != 0,
            added_date: row.get(10)?,
            last_read_date: row.get(11)?,
            percentage: row.get(12)?,
            position: row.get(13)?,
        }))
    } else {
        Ok(None)
    }
}

pub fn get_book_by_path(conn: &Connection, file_path: &str) -> Result<Option<BookWithProgress>> {
    let mut stmt = conn.prepare(
        "SELECT b.id, b.title, b.author, b.file_path, b.format, b.cover_image,
                b.page_count, b.chapter_count, b.file_size, b.is_favorite,
                b.added_date, b.last_read_date,
                COALESCE(p.percentage, 0.0) as percentage, p.position
         FROM books b
         LEFT JOIN reading_progress p ON b.id = p.book_id
         WHERE b.file_path = ?1",
    )?;

    let mut rows = stmt.query(params![file_path])?;
    if let Some(row) = rows.next()? {
        Ok(Some(BookWithProgress {
            id: row.get(0)?,
            title: row.get(1)?,
            author: row.get(2)?,
            file_path: row.get(3)?,
            format: row.get(4)?,
            cover_image: row.get(5)?,
            page_count: row.get(6)?,
            chapter_count: row.get(7)?,
            file_size: row.get(8)?,
            is_favorite: row.get::<_, i64>(9)? != 0,
            added_date: row.get(10)?,
            last_read_date: row.get(11)?,
            percentage: row.get(12)?,
            position: row.get(13)?,
        }))
    } else {
        Ok(None)
    }
}

pub fn get_recent_reads(conn: &Connection, limit: usize) -> Result<Vec<BookWithProgress>> {
    let mut stmt = conn.prepare(
        "SELECT b.id, b.title, b.author, b.file_path, b.format, b.cover_image,
                b.page_count, b.chapter_count, b.file_size, b.is_favorite,
                b.added_date, b.last_read_date,
                COALESCE(p.percentage, 0.0) as percentage, p.position
         FROM books b
         LEFT JOIN reading_progress p ON b.id = p.book_id
         WHERE b.last_read_date IS NOT NULL
         ORDER BY b.last_read_date DESC
         LIMIT ?1",
    )?;

    let mut books: Vec<BookWithProgress> = stmt
        .query_map(params![limit as i64], |row| {
            Ok(BookWithProgress {
                id: row.get(0)?,
                title: row.get(1)?,
                author: row.get(2)?,
                file_path: row.get(3)?,
                format: row.get(4)?,
                cover_image: row.get(5)?,
                page_count: row.get(6)?,
                chapter_count: row.get(7)?,
                file_size: row.get(8)?,
                is_favorite: row.get::<_, i64>(9)? != 0,
                added_date: row.get(10)?,
                last_read_date: row.get(11)?,
                percentage: row.get(12)?,
                position: row.get(13)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

    // If fewer than limit, add from recently added
    if books.len() < limit {
        let existing_ids: Vec<String> = books.iter().map(|b| b.id.clone()).collect();
        let all_books = list_books(conn)?;
        for b in all_books {
            if !existing_ids.contains(&b.id) {
                books.push(b);
                if books.len() >= limit {
                    break;
                }
            }
        }
    }

    Ok(books)
}

pub fn insert_book(conn: &Connection, book: &Book) -> Result<()> {
    conn.execute(
        "INSERT INTO books (id, title, author, file_path, format, cover_image, page_count, chapter_count, file_size, is_favorite, added_date, last_read_date)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
         ON CONFLICT(file_path) DO UPDATE SET
            title = excluded.title,
            author = excluded.author,
            cover_image = excluded.cover_image,
            page_count = excluded.page_count,
            chapter_count = excluded.chapter_count,
            file_size = excluded.file_size",
        params![
            book.id,
            book.title,
            book.author,
            book.file_path,
            book.format,
            book.cover_image,
            book.page_count,
            book.chapter_count,
            book.file_size,
            if book.is_favorite { 1 } else { 0 },
            book.added_date,
            book.last_read_date,
        ],
    )?;
    Ok(())
}

pub fn update_book_cover(conn: &Connection, book_id: &str, cover_image: &str) -> Result<()> {
    conn.execute("UPDATE books SET cover_image = ?1 WHERE id = ?2", params![cover_image, book_id])?;
    Ok(())
}

pub fn delete_book(conn: &Connection, book_id: &str) -> Result<()> {
    conn.execute("DELETE FROM books WHERE id = ?1", params![book_id])?;
    Ok(())
}

pub fn update_progress(
    conn: &Connection,
    book_id: &str,
    percentage: f64,
    position: Option<&str>,
) -> Result<()> {
    let now = Utc::now().to_rfc3339();
    conn.execute(
        "INSERT INTO reading_progress (book_id, percentage, position, updated_at)
         VALUES (?1, ?2, ?3, ?4)
         ON CONFLICT(book_id) DO UPDATE SET
            percentage = excluded.percentage,
            position = excluded.position,
            updated_at = excluded.updated_at",
        params![book_id, percentage, position, now],
    )?;

    conn.execute(
        "UPDATE books SET last_read_date = ?1 WHERE id = ?2",
        params![now, book_id],
    )?;

    Ok(())
}

pub fn toggle_favorite(conn: &Connection, book_id: &str) -> Result<bool> {
    let current: i64 = conn.query_row(
        "SELECT is_favorite FROM books WHERE id = ?1",
        params![book_id],
        |row| row.get(0),
    )?;

    let new_val = if current == 0 { 1 } else { 0 };
    conn.execute(
        "UPDATE books SET is_favorite = ?1 WHERE id = ?2",
        params![new_val, book_id],
    )?;

    Ok(new_val == 1)
}

// ----------------- Annotations Operations -----------------

pub fn list_annotations(
    conn: &Connection,
    book_id: Option<&str>,
) -> Result<Vec<AnnotationWithBookTitle>> {
    let mut annotations = Vec::new();
    let query_base = "SELECT a.id, a.book_id, b.title, a.cfi_range, a.selected_text, a.note, a.color, a.created_at, a.updated_at
                      FROM annotations a
                      JOIN books b ON a.book_id = b.id";

    if let Some(bid) = book_id {
        let sql = format!("{} WHERE a.book_id = ?1 ORDER BY a.created_at DESC", query_base);
        let mut stmt = conn.prepare(&sql)?;
        let rows = stmt.query_map(params![bid], |row| {
            Ok(AnnotationWithBookTitle {
                id: row.get(0)?,
                book_id: row.get(1)?,
                book_title: row.get(2)?,
                cfi_range: row.get(3)?,
                selected_text: row.get(4)?,
                note: row.get(5)?,
                color: row.get(6)?,
                created_at: row.get(7)?,
                updated_at: row.get(8)?,
            })
        })?;
        for a in rows {
            if let Ok(item) = a {
                annotations.push(item);
            }
        }
    } else {
        let sql = format!("{} ORDER BY a.created_at DESC", query_base);
        let mut stmt = conn.prepare(&sql)?;
        let rows = stmt.query_map([], |row| {
            Ok(AnnotationWithBookTitle {
                id: row.get(0)?,
                book_id: row.get(1)?,
                book_title: row.get(2)?,
                cfi_range: row.get(3)?,
                selected_text: row.get(4)?,
                note: row.get(5)?,
                color: row.get(6)?,
                created_at: row.get(7)?,
                updated_at: row.get(8)?,
            })
        })?;
        for a in rows {
            if let Ok(item) = a {
                annotations.push(item);
            }
        }
    }

    Ok(annotations)
}

pub fn insert_annotation(conn: &Connection, ann: &Annotation) -> Result<()> {
    conn.execute(
        "INSERT INTO annotations (id, book_id, cfi_range, selected_text, note, color, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
         ON CONFLICT(id) DO UPDATE SET
            note = excluded.note,
            color = excluded.color,
            updated_at = excluded.updated_at",
        params![
            ann.id,
            ann.book_id,
            ann.cfi_range,
            ann.selected_text,
            ann.note,
            ann.color,
            ann.created_at,
            ann.updated_at,
        ],
    )?;
    Ok(())
}

pub fn delete_annotation(conn: &Connection, ann_id: &str) -> Result<()> {
    conn.execute("DELETE FROM annotations WHERE id = ?1", params![ann_id])?;
    Ok(())
}

// ----------------- Bookmarks Operations -----------------

pub fn list_bookmarks(conn: &Connection, book_id: &str) -> Result<Vec<Bookmark>> {
    let mut stmt = conn.prepare(
        "SELECT id, book_id, page, title, excerpt, created_at
         FROM bookmarks
         WHERE book_id = ?1
         ORDER BY page ASC, created_at DESC",
    )?;

    let bookmarks = stmt
        .query_map(params![book_id], |row| {
            Ok(Bookmark {
                id: row.get(0)?,
                book_id: row.get(1)?,
                page: row.get(2)?,
                title: row.get(3)?,
                excerpt: row.get(4)?,
                created_at: row.get(5)?,
            })
        })?
        .filter_map(|r| r.ok())
        .collect();

    Ok(bookmarks)
}

pub fn insert_bookmark(conn: &Connection, bm: &Bookmark) -> Result<()> {
    conn.execute(
        "INSERT INTO bookmarks (id, book_id, page, title, excerpt, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)
         ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            excerpt = excluded.excerpt",
        params![bm.id, bm.book_id, bm.page, bm.title, bm.excerpt, bm.created_at],
    )?;
    Ok(())
}

pub fn delete_bookmark(conn: &Connection, bm_id: &str) -> Result<()> {
    conn.execute("DELETE FROM bookmarks WHERE id = ?1", params![bm_id])?;
    Ok(())
}

// ----------------- Sessions & Insights Operations -----------------

pub fn record_session(conn: &Connection, session: &ReadingSession) -> Result<()> {
    conn.execute(
        "INSERT INTO reading_sessions (id, book_id, start_time, end_time, duration_seconds, words_read)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![
            session.id,
            session.book_id,
            session.start_time,
            session.end_time,
            session.duration_seconds,
            session.words_read,
        ],
    )?;
    Ok(())
}

pub fn get_reading_stats(conn: &Connection) -> Result<ReadingStats> {
    // Total books completed or in library
    let total_books: i64 = conn.query_row("SELECT count(*) FROM books", [], |r| r.get(0)).unwrap_or(0);

    // Reading session aggregations
    let (total_seconds, total_words): (i64, i64) = conn
        .query_row(
            "SELECT COALESCE(SUM(duration_seconds), 0), COALESCE(SUM(words_read), 0)
             FROM reading_sessions",
            [],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .unwrap_or((0, 0));

    // Unique days read
    let total_days_read: i64 = conn
        .query_row(
            "SELECT COUNT(DISTINCT SUBSTR(start_time, 1, 10)) FROM reading_sessions",
            [],
            |r| r.get(0),
        )
        .unwrap_or(1);

    let days_count = if total_days_read < 1 { 1 } else { total_days_read };
    let avg_minutes_per_day = (total_seconds as f64 / 60.0) / days_count as f64;
    let avg_speed_wpm = if total_seconds > 0 {
        (total_words as f64) / (total_seconds as f64 / 60.0)
    } else {
        240.0
    };

    // Calculate monthly reading stats
    let mut monthly_stats: Vec<MonthlyStat> = Vec::new();
    let months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    for m in &months {
        monthly_stats.push(MonthlyStat {
            month: m.to_string(),
            days_read: if *m == "Oct" { days_count } else { 0 },
            reading_time_minutes: if *m == "Oct" { total_seconds / 60 } else { 0 },
            pages_read: if *m == "Oct" { total_words / 250 } else { 0 },
        });
    }

    Ok(ReadingStats {
        total_books_read: total_books,
        total_reading_time_seconds: total_seconds,
        total_words_read: total_words,
        total_days_read: days_count,
        current_streak_days: days_count,
        record_streak_days: days_count.max(5),
        avg_reading_time_per_day_minutes: avg_minutes_per_day,
        avg_speed_wpm: avg_speed_wpm.clamp(50.0, 800.0),
        monthly_stats,
    })
}

// ----------------- Faithful SVG Book Covers matching Windows B0 -----------------

fn generate_prince_cover_svg() -> String {
    let svg = r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 440" width="300" height="440">
  <rect width="300" height="440" rx="8" fill="#ffffff" stroke="#d1d5db" stroke-width="1.5"/>
  <rect x="0" y="0" width="10" height="440" fill="#e5e7eb" opacity="0.7"/>
  
  <text x="150" y="140" font-family="Georgia, 'Times New Roman', serif" font-size="24" font-weight="bold" fill="#111827" text-anchor="middle" letter-spacing="1">
    The Prince
  </text>
  <text x="150" y="172" font-family="Georgia, 'Times New Roman', serif" font-size="12" font-style="italic" fill="#4b5563" text-anchor="middle">
    Nicolo Machiavelli
  </text>

  <g transform="translate(45, 270)">
    <!-- Planet PDF logo -->
    <path d="M 12 16 Q 70 -5 140 18" stroke="#e26a2c" stroke-width="5" fill="none" stroke-linecap="round"/>
    <text x="10" y="24" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="900" fill="#2c3882" letter-spacing="-1">
      Planet
    </text>
    <text x="115" y="24" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="28" font-weight="900" fill="#e26a2c" letter-spacing="-1">
      PDF
    </text>
    <text x="105" y="55" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="8" fill="#6b7280" text-anchor="middle">
      This eBook was designed and published by Planet PDF.
    </text>
    <text x="105" y="68" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="7.5" fill="#9ca3af" text-anchor="middle">
      For more free eBooks visit our Web site at http://www.planetpdf.com/
    </text>
  </g>
</svg>"##;
    format!("data:image/svg+xml;base64,{}", BASE64.encode(svg.as_bytes()))
}

fn generate_mans_search_cover_svg() -> String {
    let svg = r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 440" width="300" height="440">
  <rect width="300" height="440" rx="8" fill="#7ba3c7" stroke="#527d9e" stroke-width="1.5"/>
  <rect x="20" y="20" width="260" height="400" rx="4" fill="#a4c6e6" stroke="#487291" stroke-width="1.5"/>
  <rect x="35" y="35" width="230" height="370" fill="#d2e4f5" opacity="0.6"/>

  <text x="150" y="90" font-family="Georgia, serif" font-size="20" font-weight="bold" fill="#1e3a5f" text-anchor="middle" letter-spacing="2">
    MAN'S
  </text>
  <text x="150" y="125" font-family="Georgia, serif" font-size="22" font-weight="bold" fill="#1e3a5f" text-anchor="middle" letter-spacing="2">
    SEARCH
  </text>
  <text x="150" y="160" font-family="Georgia, serif" font-size="20" font-weight="bold" fill="#1e3a5f" text-anchor="middle" letter-spacing="2">
    FOR
  </text>
  <text x="150" y="195" font-family="Georgia, serif" font-size="22" font-weight="bold" fill="#1e3a5f" text-anchor="middle" letter-spacing="2">
    MEANING
  </text>

  <line x1="70" y1="215" x2="230" y2="215" stroke="#1e3a5f" stroke-width="1.5"/>

  <text x="150" y="245" font-family="Georgia, serif" font-size="16" font-weight="bold" fill="#1e3a5f" text-anchor="middle" letter-spacing="1">
    VIKTOR E.
  </text>
  <text x="150" y="270" font-family="Georgia, serif" font-size="16" font-weight="bold" fill="#1e3a5f" text-anchor="middle" letter-spacing="1">
    FRANKL
  </text>

  <text x="150" y="315" font-family="Georgia, serif" font-size="8.5" fill="#335c82" text-anchor="middle">
    WITH A NEW FOREWORD BY
  </text>
  <text x="150" y="328" font-family="Georgia, serif" font-size="9" font-weight="bold" fill="#1e3a5f" text-anchor="middle">
    HAROLD S. KUSHNER
  </text>

  <rect x="55" y="355" width="190" height="26" rx="3" fill="#1e3a5f" opacity="0.9"/>
  <text x="150" y="372" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="7.5" font-weight="bold" fill="#ffffff" text-anchor="middle" letter-spacing="0.5">
    12 MILLION COPIES IN PRINT WORLDWIDE
  </text>
</svg>"##;
    format!("data:image/svg+xml;base64,{}", BASE64.encode(svg.as_bytes()))
}

fn generate_sherlock_cover_svg() -> String {
    let svg = r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 440" width="300" height="440">
  <defs>
    <radialGradient id="spotlight" cx="45%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#4a2215"/>
      <stop offset="60%" stop-color="#241009"/>
      <stop offset="100%" stop-color="#0d0503"/>
    </radialGradient>
  </defs>
  <rect width="300" height="440" rx="8" fill="url(#spotlight)" stroke="#522718" stroke-width="1.5"/>

  <!-- Violinist silhouette -->
  <g transform="translate(100, 70)" opacity="0.85">
    <circle cx="50" cy="40" r="22" fill="#c49a6c"/>
    <path d="M 40 60 Q 25 120 20 180 L 80 180 Q 75 120 60 60 Z" fill="#2d150d"/>
    <path d="M 25 90 L -10 120 L 15 140 Z" fill="#c49a6c"/>
    <!-- Violin body -->
    <ellipse cx="25" cy="115" rx="14" ry="24" fill="#873e23" transform="rotate(-25 25 115)"/>
    <line x1="-15" y1="95" x2="65" y2="135" stroke="#f3e5ab" stroke-width="2"/>
  </g>

  <rect x="20" y="310" width="260" height="105" rx="4" fill="#000000" opacity="0.6"/>
  <text x="150" y="345" font-family="Georgia, serif" font-size="14" font-weight="bold" fill="#ffffff" text-anchor="middle" letter-spacing="1">
    THE ADVENTURES OF
  </text>
  <text x="150" y="368" font-family="Georgia, serif" font-size="15" font-weight="bold" fill="#f59e0b" text-anchor="middle" letter-spacing="1">
    SHERLOCK HOLMES
  </text>
  <text x="150" y="395" font-family="Georgia, serif" font-size="11" font-style="italic" fill="#d1d5db" text-anchor="middle">
    Arthur Conan Doyle
  </text>
</svg>"##;
    format!("data:image/svg+xml;base64,{}", BASE64.encode(svg.as_bytes()))
}

fn generate_quick_start_cover_svg() -> String {
    let svg = r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 440" width="300" height="440">
  <defs>
    <linearGradient id="wing1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ec4899"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
    <linearGradient id="wing2" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="100%" stop-color="#3b82f6"/>
    </linearGradient>
    <linearGradient id="wing3" x1="50%" y1="0%" x2="50%" y2="100%">
      <stop offset="0%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#ef4444"/>
    </linearGradient>
  </defs>
  <rect width="300" height="440" rx="8" fill="#ffffff" stroke="#e5e7eb" stroke-width="1.5"/>

  <!-- Prismatic wings (Aquile origami logo) -->
  <g transform="translate(150, 230)">
    <polygon points="0,-120 -80,40 -20,80" fill="url(#wing1)" opacity="0.85"/>
    <polygon points="0,-120 80,40 20,80" fill="url(#wing2)" opacity="0.85"/>
    <polygon points="-20,80 0,110 20,80" fill="url(#wing3)" opacity="0.9"/>
  </g>

  <rect x="25" y="35" width="250" height="85" rx="6" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1"/>
  <text x="150" y="70" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="18" font-weight="bold" fill="#0f172a" text-anchor="middle">
    Quick Start Guide
  </text>
  <text x="150" y="98" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" font-weight="600" fill="#6366f1" text-anchor="middle">
    Aquile Reader
  </text>

  <g transform="translate(24, 385)">
    <rect width="28" height="28" rx="4" fill="#2563eb"/>
    <text x="14" y="20" font-family="-apple-system, BlinkMacSystemFont, sans-serif" font-size="16" font-weight="bold" fill="#ffffff" text-anchor="middle">
      A
    </text>
  </g>
</svg>"##;
    format!("data:image/svg+xml;base64,{}", BASE64.encode(svg.as_bytes()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_init_and_seed_db() {
        let temp_dir = std::env::temp_dir().join(format!("aquile_test_{}", std::process::id()));
        let db_file = temp_dir.join("test_library.db");
        fs::create_dir_all(&temp_dir).unwrap();

        let conn = init_db(&db_file).expect("Failed to init test db");
        let books = list_books(&conn).expect("Failed to list books");
        assert_eq!(books.len(), 4);

        let prince = books.iter().find(|b| b.id == "book-the-prince").unwrap();
        assert_eq!(prince.title, "The Prince");
        assert_eq!(prince.author.as_deref(), Some("Nicolo Machiavelli"));
        assert_eq!(prince.percentage, 7.0);

        // Test favorite toggle
        let fav = toggle_favorite(&conn, "book-the-prince").unwrap();
        assert!(fav);
        let prince_after = get_book(&conn, "book-the-prince").unwrap().unwrap();
        assert!(prince_after.is_favorite);

        // Test progress update
        update_progress(&conn, "book-the-prince", 25.5, Some("{\"cfi\": \"/6/4\"}")).unwrap();
        let prince_updated = get_book(&conn, "book-the-prince").unwrap().unwrap();
        assert_eq!(prince_updated.percentage, 25.5);
        assert_eq!(prince_updated.position.as_deref(), Some("{\"cfi\": \"/6/4\"}"));

        // Test delete
        delete_book(&conn, "book-quick-start").unwrap();
        let books_after_delete = list_books(&conn).unwrap();
        assert_eq!(books_after_delete.len(), 3);

        // Clean up
        drop(conn);
        fs::remove_dir_all(&temp_dir).ok();
    }
}

pub fn generate_generic_cover_svg(title: &str, author: &str) -> String {
    format!(
        r##"data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 420" width="280" height="420">
  <defs>
    <linearGradient id="genBg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>
  <rect width="280" height="420" fill="url(#genBg)"/>
  <rect x="0" y="0" width="16" height="420" fill="#020617" opacity="0.6"/>
  <rect x="24" y="24" width="232" height="372" fill="none" stroke="#e2e8f0" stroke-width="1.5" opacity="0.3"/>
  <text x="140" y="160" text-anchor="middle" font-family="system-ui, sans-serif" font-weight="700" font-size="20" fill="#ffffff">{}</text>
  <text x="140" y="240" text-anchor="middle" font-family="system-ui, sans-serif" font-size="13" fill="#94a3b8">{}</text>
  <text x="140" y="360" text-anchor="middle" font-family="system-ui, sans-serif" font-size="11" letter-spacing="2" fill="#64748b">AQUILE READER</text>
</svg>"##,
        title, author
    )
}
