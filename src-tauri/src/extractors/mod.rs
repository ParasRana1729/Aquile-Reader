pub mod cbz;
pub mod epub;
pub mod pdf;

use std::path::Path;
use crate::models::ExtractedMetadata;

pub fn extract_metadata(file_path: &Path) -> Result<ExtractedMetadata, String> {
    let ext = file_path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    match ext.as_str() {
        "epub" => epub::extract_epub(file_path),
        "cbz" | "cbr" => cbz::extract_cbz(file_path),
        "pdf" => pdf::extract_pdf(file_path),
        other => Err(format!("Unsupported format: .{other}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn get_fixtures_dir() -> PathBuf {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        manifest_dir.parent().unwrap().join("fixtures")
    }

    #[test]
    fn test_extract_epub() {
        let path = get_fixtures_dir().join("canonical-text.epub");
        if path.exists() {
            let meta = extract_metadata(&path).expect("Failed to extract EPUB metadata");
            assert_eq!(meta.title, "Canonical Text Fixture");
            assert_eq!(meta.author.as_deref(), Some("Test Fixture Author"));
            assert_eq!(meta.format, "epub");
            assert_eq!(meta.chapter_count, 3);
        }
    }

    #[test]
    fn test_extract_cbz() {
        let path = get_fixtures_dir().join("sample-comic.cbz");
        if path.exists() {
            let meta = extract_metadata(&path).expect("Failed to extract CBZ metadata");
            assert_eq!(meta.format, "cbz");
            assert_eq!(meta.page_count, 3);
            assert!(meta.cover_image.is_some());
        }
    }

    #[test]
    fn test_extract_pdf() {
        let path = get_fixtures_dir().join("sample-doc.pdf");
        if path.exists() {
            let meta = extract_metadata(&path).expect("Failed to extract PDF metadata");
            assert_eq!(meta.format, "pdf");
            assert!(meta.page_count >= 1);
            assert!(meta.cover_image.is_some());
        }
    }
}

