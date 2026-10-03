#!/usr/bin/env python3
"""
generate_fixtures.py — Generates lawful, deterministic test fixtures for Aquile Reader tests.
Creates valid EPUB, PDF, CBZ files and purpose-built malformed test samples.
"""

import os
import zipfile
import hashlib
import struct

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))
os.makedirs(FIXTURES_DIR, exist_ok=True)

def create_epub(filename, title, chapters, extra_files=None):
    filepath = os.path.join(FIXTURES_DIR, filename)
    with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # mimetype must be uncompressed and first entry
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        
        # META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
        z.writestr("META-INF/container.xml", container_xml)
        
        # Manifest & Spine
        manifest_items = [
            '<item id="toc" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="style" href="style.css" media-type="text/css"/>'
        ]
        spine_items = []
        
        for idx, (chap_title, chap_html) in enumerate(chapters, 1):
            chap_id = f"chap{idx}"
            chap_href = f"chapter{idx}.xhtml"
            manifest_items.append(f'<item id="{chap_id}" href="{chap_href}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{chap_id}"/>')
            
            full_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
  <title>{chap_title}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <h2>{chap_title}</h2>
  {chap_html}
</body>
</html>"""
            z.writestr(f"OEBPS/{chap_href}", full_html)
            
        if extra_files:
            for extra_path, (extra_content, media_type) in extra_files.items():
                extra_id = extra_path.replace("/", "_").replace(".", "_")
                manifest_items.append(f'<item id="{extra_id}" href="{extra_path}" media-type="{media_type}"/>')
                z.writestr(f"OEBPS/{extra_path}", extra_content)
                
        # content.opf
        manifest_str = "\n    ".join(manifest_items)
        spine_str = "\n    ".join(spine_items)
        content_opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">urn:uuid:12345678-1234-5678-1234-567812345678</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>en</dc:language>
    <dc:creator>Test Fixture Author</dc:creator>
  </metadata>
  <manifest>
    {manifest_str}
  </manifest>
  <spine toc="toc">
    {spine_str}
  </spine>
</package>"""
        z.writestr("OEBPS/content.opf", content_opf)
        
        # toc.ncx
        nav_points = []
        for idx, (chap_title, _) in enumerate(chapters, 1):
            nav_points.append(f"""  <navPoint id="navPoint-{idx}" playOrder="{idx}">
    <navLabel><text>{chap_title}</text></navLabel>
    <content src="chapter{idx}.xhtml"/>
  </navPoint>""")
        nav_points_str = "\n".join(nav_points)
        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:12345678-1234-5678-1234-567812345678"/>
    <meta name="dtb:depth" content="1"/>
  </head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
{nav_points_str}
  </navMap>
</ncx>"""
        z.writestr("OEBPS/toc.ncx", toc_ncx)
        
        # nav.xhtml
        nav_li = "\n      ".join(f'<li><a href="chapter{idx}.xhtml">{ct}</a></li>' for idx, (ct, _) in enumerate(chapters, 1))
        nav_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Navigation</title></head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>Table of Contents</h1>
    <ol>
      {nav_li}
    </ol>
  </nav>
</body>
</html>"""
        z.writestr("OEBPS/nav.xhtml", nav_xhtml)
        
        # style.css
        style_css = """body { font-family: sans-serif; line-height: 1.6; margin: 5%; }
p { margin-bottom: 1em; text-indent: 1.5em; }
h2 { color: #2a2a2a; border-bottom: 1px solid #ccc; }
.caption { font-style: italic; font-size: 0.9em; text-align: center; }
"""
        z.writestr("OEBPS/style.css", style_css)
    return filepath

def generate_canonical_text_epub():
    chapters = [
        ("Chapter 1: The Beginning of Reading",
         "<p>Reading is an essential window into thought, language, and knowledge. Aquile Reader aims to provide a serene, customizable reading environment for digital literature.</p>"
         "<p>Typography is the art and technique of arranging type to make written language legible, readable, and appealing when displayed. The arrangement of type involves selecting typefaces, point sizes, line lengths, line-spacing, and letter-spacing.</p>"
         "<p>This paragraph contains multiple sentences to test pagination calculation across multiple columns and different viewport sizes. When columns reflow, line breaks and paragraphs should preserve their deterministic boundaries.</p>"),
        ("Chapter 2: Annotations and Durability",
         "<p>Annotations allow readers to engage actively with the text. Highlights capture critical passages, while notes record spontaneous reflections and cross-references.</p>"
         "<p>Durability guarantees that every acknowledged annotation survives power faults, process termination, and application crashes. Stable character offsets and CFI anchors prevent anchor drift across layout re-flows.</p>"),
        ("Chapter 3: Large Document Pagination",
         "".join(f"<p>Paragraph {i}: The quick brown fox jumps over the lazy dog. Continuous text flow ensures that the reader pagination algorithm correctly segments content into discrete pages without clipping or overflowing boundaries.</p>" for i in range(1, 25)))
    ]
    return create_epub("canonical-text.epub", "Canonical Text Fixture", chapters)

def generate_illustrated_epub():
    # 1x1 transparent PNG
    png_1x1 = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\r\xef\x85\xaa\x00\x00\x00\x00IEND\xaeB`\x82'
    chapters = [
        ("Illustration Test",
         '<p>Here is an illustrated section test.</p>'
         '<div style="text-align: center;"><img src="image1.png" alt="Sample Illustration" style="max-width: 100%; height: auto;"/>'
         '<p class="caption">Figure 1.1: A sample transparent test graphic.</p></div>'
         '<p>After the figure, text resumes normally to verify layout flow around embedded media assets.</p>')
    ]
    extra_files = {
        "image1.png": (png_1x1, "image/png")
    }
    return create_epub("illustrated.epub", "Illustrated EPUB Fixture", chapters, extra_files)

def generate_multilingual_rtl_epub():
    chapters = [
        ("Multilingual and RTL Test",
         '<p dir="ltr">This is standard left-to-right English text testing bidirectional switching.</p>'
         '<p dir="rtl" style="direction: rtl; text-align: right;">هذا نص تجريبي باللغة العربية لاختبار اتجاه النص من اليمين إلى اليسار وتشكيل الحروف بشكل صحيح.</p>'
         '<p dir="rtl" style="direction: rtl; text-align: right;">זהו טקסט בעברית לבדיקת כיווניות מימין לשמאל ותמיכה בפונטים.</p>'
         '<p dir="ltr">日本語のテスト文章です。文字エンコーディングと改行処理が正常に行われるか確認します。</p>')
    ]
    return create_epub("multilingual-rtl.epub", "Multilingual RTL Fixture", chapters)

def generate_sample_pdf():
    # Minimal valid PDF file with 2 pages
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R 4 0 R] /Count 2>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 6 0 R >> >> >> endobj\n"
        b"4 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 7 0 R /Resources << /Font << /F1 6 0 R >> >> >> endobj\n"
        b"5 0 obj <</Length 44>> stream\nBT /F1 24 Tf 100 700 Td (Page 1: Aquile Reader PDF Fixture) Tj ET\nendstream\nendobj\n"
        b"6 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        b"7 0 obj <</Length 44>> stream\nBT /F1 24 Tf 100 700 Td (Page 2: Second Page of Test Document) Tj ET\nendstream\nendobj\n"
        b"xref\n0 8\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000244 00000 n \n0000000373 00000 n \n0000000468 00000 n \n0000000547 00000 n \n"
        b"trailer <</Size 8 /Root 1 0 R>>\nstartxref\n642\n%%EOF\n"
    )
    filepath = os.path.join(FIXTURES_DIR, "sample-doc.pdf")
    with open(filepath, "wb") as f:
        f.write(pdf_content)
    return filepath

def generate_sample_cbz():
    # Comic archive containing 3 page images
    filepath = os.path.join(FIXTURES_DIR, "sample-comic.cbz")
    png_1x1 = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\r\xef\x85\xaa\x00\x00\x00\x00IEND\xaeB`\x82'
    with zipfile.ZipFile(filepath, "w") as z:
        z.writestr("001_cover.png", png_1x1)
        z.writestr("002_page1.png", png_1x1)
        z.writestr("003_page2.png", png_1x1)
    return filepath

def generate_malformed_samples():
    # 1. Corrupt archive
    corrupt_path = os.path.join(FIXTURES_DIR, "malformed-archive.epub")
    with open(corrupt_path, "wb") as f:
        f.write(b"PK\x03\x04\x00\x00\x00\x00ThisIsNotAValidZipArchiveCorruptedData")
        
    # 2. Path traversal attack attempt
    traversal_path = os.path.join(FIXTURES_DIR, "path-traversal.epub")
    with zipfile.ZipFile(traversal_path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("../../../evil.txt", "Malicious content trying directory traversal")
        z.writestr("OEBPS/content.opf", "<package/>")
        
    return corrupt_path, traversal_path

def compute_checksums():
    results = {}
    for filename in sorted(os.listdir(FIXTURES_DIR)):
        filepath = os.path.join(FIXTURES_DIR, filename)
        if os.path.isfile(filepath):
            hasher = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            results[filename] = hasher.hexdigest()
    return results

if __name__ == "__main__":
    generate_canonical_text_epub()
    generate_illustrated_epub()
    generate_multilingual_rtl_epub()
    generate_sample_pdf()
    generate_sample_cbz()
    generate_malformed_samples()
    
    checksums = compute_checksums()
    print("Generated fixtures:")
    for fname, sha in checksums.items():
        size = os.path.getsize(os.path.join(FIXTURES_DIR, fname))
        print(f"  {fname:<25} {size:>8} bytes  SHA-256: {sha}")
