pub mod commands;
pub mod db;
pub mod extractors;
pub mod models;

use std::sync::Mutex;
use tauri::{Manager, Window};
use commands::DbState;

#[tauri::command]
fn minimize_window(window: Window) -> Result<(), String> {
    window.minimize().map_err(|e| e.to_string())
}

#[tauri::command]
fn toggle_maximize_window(window: Window) -> Result<bool, String> {
    let is_max = window.is_maximized().map_err(|e| e.to_string())?;
    if is_max {
        window.unmaximize().map_err(|e| e.to_string())?;
        Ok(false)
    } else {
        window.maximize().map_err(|e| e.to_string())?;
        Ok(true)
    }
}

#[tauri::command]
fn close_window(window: Window) -> Result<(), String> {
    window.close().map_err(|e| e.to_string())
}

#[tauri::command]
fn is_window_maximized(window: Window) -> Result<bool, String> {
    window.is_maximized().map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            let app_dir = app.path().app_data_dir().unwrap_or_else(|_| {
                let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
                std::path::PathBuf::from(home).join(".local/share/aquile-reader")
            });
            let db_path = app_dir.join("library.db");
            let conn = db::init_db(&db_path).expect("Failed to initialize SQLite database");
            app.manage(DbState(Mutex::new(conn)));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            minimize_window,
            toggle_maximize_window,
            close_window,
            is_window_maximized,
            commands::list_books,
            commands::get_recent_reads,
            commands::import_book,
            commands::import_multiple_books,
            commands::scan_directory_books,
            commands::delete_book,
            commands::update_book_cover,
            commands::update_progress,
            commands::toggle_favorite,
            commands::read_book_bytes,
            commands::list_annotations,
            commands::add_annotation,
            commands::delete_annotation,
            commands::list_bookmarks,
            commands::add_bookmark,
            commands::delete_bookmark,
            commands::record_reading_session,
            commands::get_reading_stats,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
