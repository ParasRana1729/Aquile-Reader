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

    let title = extract_pdf_field_from_bytes(&buffer, b"/Title").unwrap_or_else(|| {
        path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("Untitled PDF")
            .replace(['_', '-'], " ")
    });

    let author = extract_pdf_field_from_bytes(&buffer, b"/Author");

    // Count pages by matching `/Type /Page` (excluding `/Type /Pages`)
    let page_count = count_pdf_pages_from_bytes(&buffer);

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

fn find_subsequence(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack.windows(needle.len()).position(|window| window == needle)
}

fn extract_pdf_field_from_bytes(buffer: &[u8], field: &[u8]) -> Option<String> {
    let field_pos = find_subsequence(buffer, field)?;
    let remainder = &buffer[field_pos + field.len()..];
    let start_idx = remainder.iter().position(|&b| !b.is_ascii_whitespace())?;
    let slice = &remainder[start_idx..];

    if slice.first() == Some(&b'(') {
        let mut depth = 0;
        let mut i = 0;
        let mut end_pos = None;
        while i < slice.len() {
            if slice[i] == b'\\' {
                i += 2;
                continue;
            }
            if slice[i] == b'(' {
                depth += 1;
            } else if slice[i] == b')' {
                depth -= 1;
                if depth == 0 {
                    end_pos = Some(i);
                    break;
                }
            }
            i += 1;
        }

        let end_idx = end_pos?;
        let raw_literal = &slice[1..end_idx];
        let unescaped = unescape_pdf_literal_bytes(raw_literal);
        let decoded = decode_pdf_bytes(&unescaped);
        let sanitized = sanitize_string(&decoded);
        if !sanitized.is_empty() {
            return Some(sanitized);
        }
    } else if slice.first() == Some(&b'<') {
        let end_idx = slice.iter().position(|&b| b == b'>')?;
        let hex_slice = &slice[1..end_idx];
        if let Ok(bytes) = hex_bytes_to_vec(hex_slice) {
            let decoded = decode_pdf_bytes(&bytes);
            let sanitized = sanitize_string(&decoded);
            if !sanitized.is_empty() {
                return Some(sanitized);
            }
        }
    }

    None
}

fn unescape_pdf_literal_bytes(raw: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(raw.len());
    let mut i = 0;
    while i < raw.len() {
        if raw[i] == b'\\' && i + 1 < raw.len() {
            i += 1;
            match raw[i] {
                b'n' => out.push(b'\n'),
                b'r' => out.push(b'\r'),
                b't' => out.push(b'\t'),
                b'b' => out.push(8),
                b'f' => out.push(12),
                b'(' => out.push(b'('),
                b')' => out.push(b')'),
                b'\\' => out.push(b'\\'),
                c @ b'0'..=b'7' => {
                    let mut oct_val = (c - b'0') as u32;
                    let mut count = 1;
                    while count < 3 && i + 1 < raw.len() && (b'0'..=b'7').contains(&raw[i + 1]) {
                        i += 1;
                        oct_val = oct_val * 8 + (raw[i] - b'0') as u32;
                        count += 1;
                    }
                    out.push((oct_val & 0xFF) as u8);
                }
                c => out.push(c),
            }
        } else {
            out.push(raw[i]);
        }
        i += 1;
    }
    out
}

fn decode_pdf_bytes(bytes: &[u8]) -> String {
    if bytes.starts_with(&[0xFE, 0xFF]) {
        // UTF-16BE
        let u16s: Vec<u16> = bytes[2..]
            .chunks_exact(2)
            .map(|chunk| u16::from_be_bytes([chunk[0], chunk[1]]))
            .collect();
        String::from_utf16_lossy(&u16s)
    } else if bytes.starts_with(&[0xFF, 0xFE]) {
        // UTF-16LE
        let u16s: Vec<u16> = bytes[2..]
            .chunks_exact(2)
            .map(|chunk| u16::from_le_bytes([chunk[0], chunk[1]]))
            .collect();
        String::from_utf16_lossy(&u16s)
    } else if let Ok(s) = std::str::from_utf8(bytes) {
        s.to_string()
    } else {
        // Latin1 / PDFDocEncoding fallback
        bytes.iter().map(|&b| b as char).collect()
    }
}

fn sanitize_string(s: &str) -> String {
    s.chars()
        .filter(|&c| c != '\0' && c != '\u{FFFD}')
        .collect::<String>()
        .trim()
        .to_string()
}

fn hex_bytes_to_vec(hex: &[u8]) -> Result<Vec<u8>, ()> {
    let clean: Vec<u8> = hex
        .iter()
        .copied()
        .filter(|b| b.is_ascii_hexdigit())
        .collect();
    if clean.len() % 2 != 0 {
        return Err(());
    }
    let mut bytes = Vec::with_capacity(clean.len() / 2);
    for chunk in clean.chunks_exact(2) {
        let s = std::str::from_utf8(chunk).map_err(|_| ())?;
        let byte = u8::from_str_radix(s, 16).map_err(|_| ())?;
        bytes.push(byte);
    }
    Ok(bytes)
}

fn count_pdf_pages_from_bytes(buffer: &[u8]) -> usize {
    let mut count = 0;
    let mut search_idx = 0;
    while let Some(pos) = find_subsequence(&buffer[search_idx..], b"/Type") {
        let abs_pos = search_idx + pos;
        let sub = &buffer[abs_pos..];
        let newline_pos = sub
            .iter()
            .position(|&b| b == b'\n' || b == b'\r' || b == b'>')
            .unwrap_or(sub.len().min(60));
        let line = &sub[..newline_pos];
        if find_subsequence(line, b"/Page").is_some() && find_subsequence(line, b"/Pages").is_none() {
            count += 1;
        }
        search_idx = abs_pos + 5;
        if search_idx >= buffer.len() {
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

fn truncate_str(s: &str, max_chars: usize) -> String {
    if s.chars().count() <= max_chars {
        s.to_string()
    } else {
        let truncated: String = s.chars().take(max_chars - 3).collect();
        format!("{truncated}...")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_utf16be_pdf_literal_decoding() {
        // /Title (\xfe\xff\x00T\x00h\x00e\x00 \x00P\x00r\x00i\x00n\x00c\x00e\x00 \x00\\(\x001\x009\x008\x005\x00\\))
        let raw = b"/Title (\xfe\xff\x00T\x00h\x00e\x00 \x00P\x00r\x00i\x00n\x00c\x00e\x00 \x00\\(\x001\x009\x008\x005\x00\\))\n";
        let title = extract_pdf_field_from_bytes(raw, b"/Title").expect("Should decode UTF-16BE title");
        assert_eq!(title, "The Prince (1985)");
    }

    #[test]
    fn test_utf16be_pdf_author_decoding() {
        // /Author (\xfe\xff\x00N\x00i\x00c\x00c\x00o\x00l\x00\xf2\x00 \x00M\x00a\x00c\x00h\x00i\x00a\x00v\x00e\x00l\x00l\x00i)
        let raw = b"/Author (\xfe\xff\x00N\x00i\x00c\x00c\x00o\x00l\x00\xf2\x00 \x00M\x00a\x00c\x00h\x00i\x00a\x00v\x00e\x00l\x00l\x00i)\n";
        let author = extract_pdf_field_from_bytes(raw, b"/Author").expect("Should decode UTF-16BE author");
        assert_eq!(author, "Niccolò Machiavelli");
    }

    #[test]
    fn test_standard_ascii_pdf_field() {
        let raw = b"/Title (Clean ASCII Title)\n/Author (Standard Author)";
        assert_eq!(extract_pdf_field_from_bytes(raw, b"/Title").unwrap(), "Clean ASCII Title");
        assert_eq!(extract_pdf_field_from_bytes(raw, b"/Author").unwrap(), "Standard Author");
    }

    #[test]
    fn test_extract_real_world_pdf() {
        let path = Path::new("/home/paras/Documents/Books/machiavelli-niccolo-the-prince-1985.pdf");
        if path.exists() {
            let meta = extract_pdf(path).expect("Failed to extract metadata");
            assert_eq!(meta.title, "The Prince (1985)");
            assert_eq!(meta.author.as_deref(), Some("Niccolò Machiavelli"));
            assert_eq!(meta.format, "pdf");
        }
    }
}
