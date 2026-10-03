"""
EPUB Parser for Aquile Reader.
Safely extracts metadata, table of contents, and chapters from EPUB 2/3 containers (NFR-06).
"""

import os
import zipfile
import xml.etree.ElementTree as ET
import re
from typing import List, Dict, Any, Optional

class SecurityError(Exception):
    """Raised when an archive attempts directory traversal or resource exhaustion (NFR-06)."""
    pass

class CorruptEpubError(Exception):
    """Raised when an EPUB file is malformed or invalid."""
    pass

class EpubParser:
    MAX_FILE_SIZE = 50 * 1024 * 1024     # 50 MB single file limit
    MAX_TOTAL_SIZE = 250 * 1024 * 1024   # 250 MB total archive limit
    MAX_COVER_SIZE = 5 * 1024 * 1024     # 5 MB cover image limit

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.title: str = "Untitled"
        self.author: str = "Unknown Author"
        self.identifier: str = ""
        self.cover_data: Optional[bytes] = None
        self.cover_mime: str = ""
        self.manifest: Dict[str, str] = {}
        self.manifest_media: Dict[str, str] = {}
        self.spine_items: List[str] = []
        self.toc_items: List[Dict[str, str]] = []
        self.chapters: List[Dict[str, Any]] = []
        self._parse()

    def _validate_archive(self, z: zipfile.ZipFile):
        total_size = 0
        for info in z.infolist():
            # Check for path traversal attacks (NFR-06)
            norm_name = os.path.normpath(info.filename)
            if norm_name.startswith("..") or os.path.isabs(info.filename) or "../" in info.filename:
                raise SecurityError(f"Malicious path traversal detected: {info.filename}")
            if info.file_size > self.MAX_FILE_SIZE:
                raise SecurityError(f"File {info.filename} exceeds size limit")
            total_size += info.file_size
            if total_size > self.MAX_TOTAL_SIZE:
                raise SecurityError("Total archive size exceeds limit")

    def _parse(self):
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        if not zipfile.is_zipfile(self.file_path):
            raise CorruptEpubError(f"Invalid EPUB zip container: {os.path.basename(self.file_path)}")

        try:
            with zipfile.ZipFile(self.file_path, "r") as z:
                self._validate_archive(z)

                # 1. Parse META-INF/container.xml
                try:
                    container_xml = z.read("META-INF/container.xml").decode("utf-8")
                except KeyError:
                    raise CorruptEpubError("Missing META-INF/container.xml in EPUB")

                root = ET.fromstring(container_xml)
                ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
                rootfile = root.find(".//c:rootfile", ns)
                if rootfile is None or "full-path" not in rootfile.attrib:
                    raise CorruptEpubError("Malformed container.xml: no rootfile entry")

                opf_path = rootfile.attrib["full-path"]
                opf_dir = os.path.dirname(opf_path)

                # 2. Parse OPF package file
                try:
                    opf_xml = z.read(opf_path).decode("utf-8")
                except KeyError:
                    raise CorruptEpubError(f"Missing OPF file at {opf_path}")

                opf_root = ET.fromstring(opf_xml)
                ns_opf = {
                    "opf": "http://www.idpf.org/2007/opf",
                    "dc": "http://purl.org/dc/elements/1.1/"
                }

                # Metadata
                title_elem = opf_root.find(".//dc:title", ns_opf)
                if title_elem is not None and title_elem.text:
                    self.title = title_elem.text.strip()

                creator_elem = opf_root.find(".//dc:creator", ns_opf)
                if creator_elem is not None and creator_elem.text:
                    self.author = creator_elem.text.strip()

                id_elem = opf_root.find(".//dc:identifier", ns_opf)
                if id_elem is not None and id_elem.text:
                    self.identifier = id_elem.text.strip()

                # Manifest
                for item in opf_root.findall(".//opf:item", ns_opf):
                    item_id = item.attrib.get("id", "")
                    href = item.attrib.get("href", "")
                    media = item.attrib.get("media-type", "")
                    full_href = os.path.normpath(os.path.join(opf_dir, href)) if opf_dir else href
                    self.manifest[item_id] = full_href
                    self.manifest_media[item_id] = media

                # Spine
                spine = opf_root.find(".//opf:spine", ns_opf)
                if spine is not None:
                    for itemref in spine.findall(".//opf:itemref", ns_opf):
                        idref = itemref.attrib.get("idref", "")
                        if idref in self.manifest:
                            self.spine_items.append(self.manifest[idref])

                # 3. Parse Chapters
                for idx, path in enumerate(self.spine_items):
                    try:
                        raw_content = z.read(path).decode("utf-8")
                        clean_text = self._extract_clean_text(raw_content)
                        chap_title = self._extract_chapter_title(raw_content) or f"Chapter {idx + 1}"
                        self.chapters.append({
                            "index": idx,
                            "path": path,
                            "title": chap_title,
                            "raw_html": raw_content,
                            "clean_text": clean_text
                        })
                    except Exception:
                        continue

                # 4. Parse TOC (from nav or ncx)
                self._parse_toc(z, opf_root, opf_dir, ns_opf)

                # 5. Cover image (EPUB3 properties="cover-image" or EPUB2 meta name="cover")
                self._extract_cover(z, opf_root, opf_dir, ns_opf)

        except (zipfile.BadZipFile, ET.ParseError) as e:
            raise CorruptEpubError(f"Corrupt or malformed EPUB archive: {e}")

    def _extract_cover(self, z: zipfile.ZipFile, opf_root: ET.Element,
                         opf_dir: str, ns_opf: dict) -> None:
        """Best-effort cover extraction. Never raises: covers are optional."""
        try:
            cover_href: Optional[str] = None
            cover_mime = ""
            # EPUB3: manifest item with properties="cover-image".
            for item in opf_root.findall(".//opf:item", ns_opf):
                props = item.attrib.get("properties", "")
                if "cover-image" in props.split():
                    cover_href = item.attrib.get("href", "")
                    cover_mime = item.attrib.get("media-type", "")
                    break
            # EPUB2: <meta name="cover" content="<manifest id>"/>.
            if not cover_href:
                for meta in opf_root.findall(".//opf:meta", ns_opf):
                    if meta.attrib.get("name") == "cover":
                        ref = meta.attrib.get("content", "")
                        for item in opf_root.findall(".//opf:item", ns_opf):
                            if item.attrib.get("id") == ref:
                                cover_href = item.attrib.get("href", "")
                                cover_mime = item.attrib.get("media-type", "")
                                break
                        break
            if not cover_href:
                return
            full = os.path.normpath(os.path.join(opf_dir, cover_href)) if opf_dir else cover_href
            if full.startswith("..") or os.path.isabs(full):
                return
            info = z.getinfo(full)
            if info.file_size <= 0 or info.file_size > self.MAX_COVER_SIZE:
                return
            data = z.read(full)
            if not cover_mime:
                low = full.lower()
                if low.endswith(".png"):
                    cover_mime = "image/png"
                elif low.endswith((".jpg", ".jpeg")):
                    cover_mime = "image/jpeg"
                elif low.endswith(".webp"):
                    cover_mime = "image/webp"
                elif low.endswith(".gif"):
                    cover_mime = "image/gif"
            if not cover_mime.startswith("image/"):
                return
            self.cover_data = data
            self.cover_mime = cover_mime
        except Exception:
            pass

    def _extract_clean_text(self, html_content: str) -> str:
        # Strip script & style tags
        cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        # Convert <p>, <br>, <div>, <h1>-<h6> to double newlines
        cleaned = re.sub(r"<(?:p|br|div|h[1-6])[^>]*>", "\n\n", cleaned, flags=re.IGNORECASE)
        # Remove remaining tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        # Unescape common XML entities
        cleaned = cleaned.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        # Normalize excessive whitespace
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n\s*\n", "\n\n", cleaned)
        return cleaned.strip()

    def _extract_chapter_title(self, html_content: str) -> Optional[str]:
        h_match = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html_content, flags=re.DOTALL | re.IGNORECASE)
        if h_match:
            title_text = re.sub(r"<[^>]+>", "", h_match.group(1)).strip()
            if title_text:
                return title_text
        return None

    def _parse_toc(self, z: zipfile.ZipFile, opf_root: ET.Element, opf_dir: str, ns_opf: dict):
        # Check for NCX
        spine = opf_root.find(".//opf:spine", ns_opf)
        toc_id = spine.attrib.get("toc", "") if spine is not None else ""
        if toc_id and toc_id in self.manifest:
            ncx_path = self.manifest[toc_id]
            try:
                ncx_xml = z.read(ncx_path).decode("utf-8")
                ncx_root = ET.fromstring(ncx_xml)
                ns_ncx = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
                for np in ncx_root.findall(".//ncx:navPoint", ns_ncx):
                    label_elem = np.find(".//ncx:text", ns_ncx)
                    content_elem = np.find(".//ncx:content", ns_ncx)
                    title = label_elem.text.strip() if label_elem is not None and label_elem.text else "Section"
                    src = content_elem.attrib.get("src", "") if content_elem is not None else ""
                    self.toc_items.append({"title": title, "src": src})
                return
            except Exception:
                pass

        # Fallback TOC from chapter titles
        if not self.toc_items:
            for chap in self.chapters:
                self.toc_items.append({"title": chap["title"], "src": chap["path"]})
