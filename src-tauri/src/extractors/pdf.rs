use std::fs::File;
use std::io::Read;
use std::path::Path;
use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;

use crate::models::ExtractedMetadata;

pub fn extract_pdf(path: &Path) -> Result<ExtractedMetadata, String> {
    let mut file = File::open(path).map_err(|e| format!("Failed to open PDF: {e}"))?;
    let file_size = file.metadata().map(|m| m.len() as i64).unwrap_or(0);

    let mut buffer = Vec::new();
    file.read_to_end(&mut buffer)
        .map_err(|e| format!("Failed to read PDF bytes: {e}"))?;

    let text_content = String::from_utf8_lossy(&buffer);

    let title = extract_pdf_field(&text_content, "/Title").unwrap_or_else(|| {
        path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("Untitled PDF")
            .replace(['_', '-'], " ")
    });

    let author = extract_pdf_field(&text_content, "/Author");

    // Count pages by matching `/Type /Page` (excluding `/Type /Pages`)
    let page_count = count_pdf_pages(&text_content);

    // Generate an SVG book cover data URL
    let cover_image = generate_pdf_svg_cover(&title, author.as_deref());

    Ok(ExtractedMetadata {
        title,
        author,
        format: "pdf".to_string(),
        cover_image: Some(cover_image),
        page_count: page_count as i64,
        chapter_count: 1,
        file_size,
    })
}

fn extract_pdf_field(text: &str, field: &str) -> Option<String> {
    let field_pos = text.find(field)?;
    let remainder = &text[field_pos + field.len()..];
    let trimmed = remainder.trim_start();

    if trimmed.starts_with('(') {
        let end_pos = trimmed.find(')')?;
        let value = &trimmed[1..end_pos];
        if !value.trim().is_empty() {
            return Some(value.trim().to_string());
        }
    } else if trimmed.starts_with('<') {
        let end_pos = trimmed.find('>')?;
        let hex = &trimmed[1..end_pos];
        if let Ok(bytes) = hex_to_bytes(hex) {
            let s = String::from_utf8_lossy(&bytes);
            if !s.trim().is_empty() {
                return Some(s.trim().to_string());
            }
        }
    }

    None
}

fn hex_to_bytes(hex: &str) -> Result<Vec<u8>, ()> {
    let clean: String = hex.chars().filter(|c| c.is_ascii_hexdigit()).collect();
    if clean.len() % 2 != 0 {
        return Err(());
    }
    let mut bytes = Vec::new();
    for i in (0..clean.len()).step_by(2) {
        let byte = u8::from_str_radix(&clean[i..i + 2], 16).map_err(|_| ())?;
        bytes.push(byte);
    }
    Ok(bytes)
}

fn count_pdf_pages(text: &str) -> usize {
    let mut count = 0;
    let mut search_idx = 0;
    while let Some(pos) = text[search_idx..].find("/Type") {
        let abs_pos = search_idx + pos;
        let sub = &text[abs_pos..];
        if let Some(newline_or_bracket) = sub.find(|c| c == '\n' || c == '\r' || c == '>') {
            let line = &sub[..newline_or_bracket];
            if line.contains("/Page") && !line.contains("/Pages") {
                count += 1;
            }
        }
        search_idx = abs_pos + 5;
        if search_idx >= text.len() {
            break;
        }
    }
    if count == 0 {
        1
    } else {
        count
    }
}

fn generate_pdf_svg_cover(title: &str, author: Option<&str>) -> String {
    let escaped_title = html_escape(title);
    let escaped_author = html_escape(author.unwrap_or(""));

    let svg = format!(
        r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 400" width="280" height="400">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#f3f4f6"/>
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-opacity="0.15"/>
    </filter>
  </defs>
  <rect width="280" height="400" rx="8" fill="url(#bg)" stroke="#e5e7eb" stroke-width="1"/>
  <rect x="0" y="0" width="12" height="400" rx="3" fill="#e5e7eb" opacity="0.6"/>
  <g transform="translate(30, 80)">
    <text x="110" y="40" font-family="Georgia, serif" font-size="20" font-weight="bold" fill="#111827" text-anchor="middle">
      {}
    </text>
    <text x="110" y="80" font-family="Georgia, serif" font-size="12" font-style="italic" fill="#4b5563" text-anchor="middle">
      {}
    </text>
  </g>
  <g transform="translate(30, 290)">
    <rect x="70" y="20" width="80" height="28" rx="4" fill="#ef4444" opacity="0.9"/>
    <text x="110" y="39" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="12" font-weight="bold" fill="#ffffff" text-anchor="middle">
      PDF DOCUMENT
    </text>
  </g>
</svg>"##,
        truncate_str(&escaped_title, 26),
        truncate_str(&escaped_author, 28)
    );

    format!("data:image/svg+xml;base64,{}", BASE64.encode(svg.as_bytes()))
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

fn truncate_str(s: &str, max_len: usize) -> &str {
    if s.len() > max_len {
        let mut idx = max_len;
        while !s.is_char_boundary(idx) && idx > 0 {
            idx -= 1;
        }
        &s[..idx]
    } else {
        s
    }
}
