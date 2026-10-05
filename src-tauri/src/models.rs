use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Book {
    pub id: String,
    pub title: String,
    pub author: Option<String>,
    pub file_path: String,
    pub format: String,
    pub cover_image: Option<String>,
    pub page_count: i64,
    pub chapter_count: i64,
    pub file_size: i64,
    pub is_favorite: bool,
    pub added_date: String,
    pub last_read_date: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadingProgress {
    pub book_id: String,
    pub percentage: f64,
    pub position: Option<String>,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BookWithProgress {
    pub id: String,
    pub title: String,
    pub author: Option<String>,
    pub file_path: String,
    pub format: String,
    pub cover_image: Option<String>,
    pub page_count: i64,
    pub chapter_count: i64,
    pub file_size: i64,
    pub is_favorite: bool,
    pub added_date: String,
    pub last_read_date: Option<String>,
    pub percentage: f64,
    pub position: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Annotation {
    pub id: String,
    pub book_id: String,
    pub cfi_range: Option<String>,
    pub selected_text: String,
    pub note: Option<String>,
    pub color: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AnnotationWithBookTitle {
    pub id: String,
    pub book_id: String,
    pub book_title: String,
    pub cfi_range: Option<String>,
    pub selected_text: String,
    pub note: Option<String>,
    pub color: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Bookmark {
    pub id: String,
    pub book_id: String,
    pub page: i64,
    pub title: String,
    pub excerpt: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadingSession {
    pub id: String,
    pub book_id: String,
    pub start_time: String,
    pub end_time: Option<String>,
    pub duration_seconds: i64,
    pub words_read: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MonthlyStat {
    pub month: String,
    pub days_read: i64,
    pub reading_time_minutes: i64,
    pub pages_read: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadingStats {
    pub total_books_read: i64,
    pub total_reading_time_seconds: i64,
    pub total_words_read: i64,
    pub total_days_read: i64,
    pub current_streak_days: i64,
    pub record_streak_days: i64,
    pub avg_reading_time_per_day_minutes: f64,
    pub avg_speed_wpm: f64,
    pub monthly_stats: Vec<MonthlyStat>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExtractedMetadata {
    pub title: String,
    pub author: Option<String>,
    pub format: String,
    pub cover_image: Option<String>,
    pub page_count: i64,
    pub chapter_count: i64,
    pub file_size: i64,
}
