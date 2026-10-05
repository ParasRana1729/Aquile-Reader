use std::fs::File;
use std::io::Read;
use std::path::Path;
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;
use quick_xml::events::Event;
use quick_xml::Reader;
use zip::ZipArchive;

use crate::models::ExtractedMetadata;

pub fn extract_epub(path: &Path) -> Result<ExtractedMetadata, String> {
    let file = File::open(path).map_err(|e| format!("Failed to open EPUB: {e}"))?;
    let file_size = file.metadata().map(|m| m.len() as i64).unwrap_or(0);
    let mut archive = ZipArchive::new(file).map_err(|e| format!("Invalid ZIP archive: {e}"))?;

    // 1. Locate the OPF package file from META-INF/container.xml
    let opf_path = get_opf_path(&mut archive).unwrap_or_else(|| "OEBPS/content.opf".to_string());

    // 2. Read the OPF package file
    let opf_content = {
        let mut entry = archive
            .by_name(&opf_path)
            .map_err(|e| format!("Could not read OPF at '{opf_path}': {e}"))?;
        let mut s = String::new();
        entry
            .read_to_string(&mut s)
            .map_err(|e| format!("Failed to parse OPF as text: {e}"))?;
        s
    };

    // 3. Parse title, author, cover item id, spine count, manifest items
    let (title, author, cover_href, spine_count) = parse_opf(&opf_content);

    let final_title = title.unwrap_or_else(|| {
        path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("Untitled Book")
            .replace(['_', '-'], " ")
    });

    // 4. Extract cover image if found
    let cover_image = if let Some(href) = cover_href {
        let full_cover_path = resolve_relative_path(&opf_path, &href);
        extract_image_as_data_url(&mut archive, &full_cover_path)
    } else {
        // Fallback: search zip entries for any file with "cover" in name
        find_fallback_cover(&mut archive)
    };

    Ok(ExtractedMetadata {
        title: final_title,
        author,
        format: "epub".to_string(),
        cover_image,
        page_count: 0,
        chapter_count: spine_count as i64,
        file_size,
    })
}

fn get_opf_path<R: std::io::Read + std::io::Seek>(archive: &mut ZipArchive<R>) -> Option<String> {
    let mut entry = archive.by_name("META-INF/container.xml").ok()?;
    let mut xml = String::new();
    entry.read_to_string(&mut xml).ok()?;

    let mut reader = Reader::from_str(&xml);
    reader.config_mut().trim_text(true);

    loop {
        match reader.read_event() {
            Ok(Event::Empty(ref e)) | Ok(Event::Start(ref e)) => {
                if e.name().as_ref() == b"rootfile" {
                    for attr in e.attributes().flatten() {
                        if attr.key.as_ref() == b"full-path" {
                            if let Ok(val) = std::str::from_utf8(&attr.value) {
                                return Some(val.to_string());
                            }
                        }
                    }
                }
            }
            Ok(Event::Eof) | Err(_) => break,
            _ => {}
        }
    }
    None
}

fn parse_opf(xml: &str) -> (Option<String>, Option<String>, Option<String>, usize) {
    let mut reader = Reader::from_str(xml);
    reader.config_mut().trim_text(true);

    let mut title: Option<String> = None;
    let mut author: Option<String> = None;
    let mut cover_item_id: Option<String> = None;
    let mut cover_item_href: Option<String> = None;
    let mut manifest_items: Vec<(String, String, String)> = Vec::new(); // (id, href, media_type)
    let mut spine_count = 0;

    let mut in_title = false;
    let mut in_creator = false;

    loop {
        match reader.read_event() {
            Ok(Event::Start(ref e)) => {
                match e.name().as_ref() {
                    b"dc:title" | b"title" => in_title = true,
                    b"dc:creator" | b"creator" => in_creator = true,
                    _ => {}
                }
                parse_tag_attrs(e, &mut cover_item_id, &mut cover_item_href, &mut manifest_items, &mut spine_count);
            }
            Ok(Event::Empty(ref e)) => {
                parse_tag_attrs(e, &mut cover_item_id, &mut cover_item_href, &mut manifest_items, &mut spine_count);
            }
            Ok(Event::End(ref e)) => match e.name().as_ref() {
                b"dc:title" | b"title" => in_title = false,
                b"dc:creator" | b"creator" => in_creator = false,
                _ => {}
            },
            Ok(Event::Text(ref e)) => {
                if in_title && title.is_none() {
                    if let Ok(t) = e.unescape() {
                        title = Some(t.trim().to_string());
                    }
                } else if in_creator && author.is_none() {
                    if let Ok(a) = e.unescape() {
                        author = Some(a.trim().to_string());
                    }
                }
            }
            Ok(Event::Eof) | Err(_) => break,
            _ => {}
        }
    }

    // Resolve cover href
    if cover_item_href.is_none() {
        if let Some(ref target_id) = cover_item_id {
            if let Some((_, href, _)) = manifest_items.iter().find(|(id, _, _)| id == target_id) {
                cover_item_href = Some(href.clone());
            }
        }
    }

    if cover_item_href.is_none() {
        // Find item with id containing "cover" or href containing "cover" and media-type starts with image/
        if let Some((_, href, _)) = manifest_items.iter().find(|(id, href, media_type)| {
            media_type.starts_with("image/")
                && (id.to_lowercase().contains("cover") || href.to_lowercase().contains("cover"))
        }) {
            cover_item_href = Some(href.clone());
        }
    }

    (title, author, cover_item_href, spine_count)
}

fn parse_tag_attrs(
    e: &quick_xml::events::BytesStart,
    cover_item_id: &mut Option<String>,
    cover_item_href: &mut Option<String>,
    manifest_items: &mut Vec<(String, String, String)>,
    spine_count: &mut usize,
) {
    let name = e.name();
    if name.as_ref() == b"meta" {
        let mut is_cover_meta = false;
        let mut content_val: Option<String> = None;
        for attr in e.attributes().flatten() {
            if attr.key.as_ref() == b"name" && attr.value.as_ref() == b"cover" {
                is_cover_meta = true;
            }
            if attr.key.as_ref() == b"content" {
                if let Ok(val) = std::str::from_utf8(&attr.value) {
                    content_val = Some(val.to_string());
                }
            }
        }
        if is_cover_meta {
            *cover_item_id = content_val;
        }
    } else if name.as_ref() == b"item" {
        let mut id = String::new();
        let mut href = String::new();
        let mut media_type = String::new();
        let mut properties = String::new();

        for attr in e.attributes().flatten() {
            match attr.key.as_ref() {
                b"id" => id = std::str::from_utf8(&attr.value).unwrap_or("").to_string(),
                b"href" => href = std::str::from_utf8(&attr.value).unwrap_or("").to_string(),
                b"media-type" => media_type = std::str::from_utf8(&attr.value).unwrap_or("").to_string(),
                b"properties" => properties = std::str::from_utf8(&attr.value).unwrap_or("").to_string(),
                _ => {}
            }
        }

        if properties.contains("cover-image") {
            *cover_item_href = Some(href.clone());
        }
        if !id.is_empty() && !href.is_empty() {
            manifest_items.push((id, href, media_type));
        }
    } else if name.as_ref() == b"itemref" {
        *spine_count += 1;
    }
}


fn resolve_relative_path(base_path: &str, href: &str) -> String {
    let decoded_href = urlencoding_decode(href);
    if decoded_href.starts_with('/') {
        return decoded_href.trim_start_matches('/').to_string();
    }
    if let Some(parent) = Path::new(base_path).parent() {
        let parent_str = parent.to_str().unwrap_or("");
        if !parent_str.is_empty() {
            let combined = format!("{}/{}", parent_str, decoded_href);
            return normalize_path(&combined);
        }
    }
    normalize_path(&decoded_href)
}

fn normalize_path(path: &str) -> String {
    let mut parts: Vec<&str> = Vec::new();
    for part in path.split('/') {
        if part == "." || part.is_empty() {
            continue;
        } else if part == ".." {
            parts.pop();
        } else {
            parts.push(part);
        }
    }
    parts.join("/")
}

fn urlencoding_decode(input: &str) -> String {
    // Basic url-decoding for %20, etc.
    let mut result = String::new();
    let mut chars = input.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '%' {
            let hex: String = chars.by_ref().take(2).collect();
            if let Ok(byte) = u8::from_str_radix(&hex, 16) {
                result.push(byte as char);
            } else {
                result.push('%');
                result.push_str(&hex);
            }
        } else {
            result.push(c);
        }
    }
    result
}

fn extract_image_as_data_url<R: std::io::Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
    path: &str,
) -> Option<String> {
    let mut entry = archive.by_name(path).ok()?;
    let mut bytes = Vec::new();
    entry.read_to_end(&mut bytes).ok()?;

    let mime = mime_from_ext(path);
    Some(format!("data:{mime};base64,{}", BASE64.encode(&bytes)))
}

fn find_fallback_cover<R: std::io::Read + std::io::Seek>(
    archive: &mut ZipArchive<R>,
) -> Option<String> {
    let mut cover_entry_name: Option<String> = None;
    for i in 0..archive.len() {
        if let Ok(file) = archive.by_index(i) {
            let name = file.name().to_lowercase();
            if (name.ends_with(".jpg")
                || name.ends_with(".jpeg")
                || name.ends_with(".png")
                || name.ends_with(".webp"))
                && name.contains("cover")
            {
                cover_entry_name = Some(file.name().to_string());
                break;
            }
        }
    }

    if let Some(name) = cover_entry_name {
        extract_image_as_data_url(archive, &name)
    } else {
        None
    }
}

fn mime_from_ext(path: &str) -> &'static str {
    let lower = path.to_lowercase();
    if lower.ends_with(".png") {
        "image/png"
    } else if lower.ends_with(".jpg") || lower.ends_with(".jpeg") {
        "image/jpeg"
    } else if lower.ends_with(".webp") {
        "image/webp"
    } else if lower.ends_with(".gif") {
        "image/gif"
    } else if lower.ends_with(".svg") {
        "image/svg+xml"
    } else {
        "image/jpeg"
    }
}
