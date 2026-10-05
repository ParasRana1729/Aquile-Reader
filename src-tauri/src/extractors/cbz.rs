use std::fs::File;
use std::io::Read;
use std::path::Path;
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use zip::ZipArchive;

use crate::models::ExtractedMetadata;

pub fn extract_cbz(path: &Path) -> Result<ExtractedMetadata, String> {
    let file = File::open(path).map_err(|e| format!("Failed to open CBZ: {e}"))?;
    let file_size = file.metadata().map(|m| m.len() as i64).unwrap_or(0);
    let mut archive = ZipArchive::new(file).map_err(|e| format!("Invalid CBZ archive: {e}"))?;

    let mut image_names: Vec<String> = Vec::new();
    for i in 0..archive.len() {
        if let Ok(file) = archive.by_index(i) {
            let name = file.name().to_string();
            let lower = name.to_lowercase();
            if !lower.starts_with("__macosx")
                && !lower.starts_with('.')
                && (lower.ends_with(".jpg")
                    || lower.ends_with(".jpeg")
                    || lower.ends_with(".png")
                    || lower.ends_with(".webp")
                    || lower.ends_with(".gif"))
            {
                image_names.push(name);
            }
        }
    }

    // Natural alphanumeric sorting
    image_names.sort_by(|a, b| alphanumeric_sort::compare_str(a, b));

    let page_count = image_names.len() as i64;
    let cover_image = if let Some(first_img) = image_names.first() {
        if let Ok(mut entry) = archive.by_name(first_img) {
            let mut bytes = Vec::new();
            if entry.read_to_end(&mut bytes).is_ok() {
                let mime = if first_img.to_lowercase().ends_with(".png") {
                    "image/png"
                } else if first_img.to_lowercase().ends_with(".webp") {
                    "image/webp"
                } else {
                    "image/jpeg"
                };
                Some(format!("data:{mime};base64,{}", BASE64.encode(&bytes)))
            } else {
                None
            }
        } else {
            None
        }
    } else {
        None
    };

    let title = path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("Untitled Comic")
        .replace(['_', '-'], " ");

    Ok(ExtractedMetadata {
        title,
        author: Some("Comic Archive".to_string()),
        format: "cbz".to_string(),
        cover_image,
        page_count,
        chapter_count: 1,
        file_size,
    })
}

mod alphanumeric_sort {
    use std::cmp::Ordering;

    pub fn compare_str(a: &str, b: &str) -> Ordering {
        let mut a_chars = a.chars().peekable();
        let mut b_chars = b.chars().peekable();

        loop {
            match (a_chars.peek(), b_chars.peek()) {
                (None, None) => return Ordering::Equal,
                (None, Some(_)) => return Ordering::Less,
                (Some(_), None) => return Ordering::Greater,
                (Some(&ac), Some(&bc)) => {
                    if ac.is_ascii_digit() && bc.is_ascii_digit() {
                        let mut a_num: u64 = 0;
                        while let Some(&c) = a_chars.peek() {
                            if let Some(digit) = c.to_digit(10) {
                                a_num = a_num.saturating_mul(10).saturating_add(digit as u64);
                                a_chars.next();
                            } else {
                                break;
                            }
                        }

                        let mut b_num: u64 = 0;
                        while let Some(&c) = b_chars.peek() {
                            if let Some(digit) = c.to_digit(10) {
                                b_num = b_num.saturating_mul(10).saturating_add(digit as u64);
                                b_chars.next();
                            } else {
                                break;
                            }
                        }

                        match a_num.cmp(&b_num) {
                            Ordering::Equal => continue,
                            other => return other,
                        }
                    } else {
                        match ac.to_ascii_lowercase().cmp(&bc.to_ascii_lowercase()) {
                            Ordering::Equal => {
                                a_chars.next();
                                b_chars.next();
                            }
                            other => return other,
                        }
                    }
                }
            }
        }
    }
}
