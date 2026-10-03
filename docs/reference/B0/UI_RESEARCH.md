# Aquile Reader UI Research (public sources only, 2026-10-03)

Observations from `aquilereader.in` screenshots (11) and public how-to/FAQ text.
Clean-room: layout/behavior notes only; no assets copied. Screenshots cached at
/tmp/opencode/aquile-shots (not committed).

## 1. App shell

- Narrow dark icon rail on the left (~48px, dark gray `#3A3A3A`-class), top to
  bottom: menu, speaker/TTS, home, library, collections, globe/catalogs,
  monitor/stats, store-bag, gear/settings, sync, account. Bottom cluster:
  settings gear, diagnostics, sync.
- Selected rail item: filled rounded-rect highlight in the theme accent color
  (blue/teal/pink depending on active color theme).
- Top dark toolbar; window title `"<Book Title> - Aquile Reader"` in reader.
- Accent color is theme-driven (teal `#009688`-class default; pink, blue seen).
- Optional transparent/blurred background with transparency slider (Settings >
  Personalization: "Transparent background" toggle + "Background transparency"
  slider + "Color themes" swatches: Vine Yard, Dark Side, Fresh Berry,
  Pulpy Orange, Clear sky, Flash, Turquoise, Green Apple, Add theme).

## 2. Home

- Two sections: "Recent Reads" (left, large) and "Favourite Books" (right).
- Covers in a grid with rounded corners + soft drop shadows; first recent cover
  rendered large.
- Bottom links: "Open Library ›" (left), "See more ›" (right).
- "+" add button at top-right of the toolbar.

## 3. Library

- Filter dropdown: All Books, Favourites, Downloads, Reading, Not Started,
  Completed (dark popup, accent marker on selection).
- Toolbar: search, view options, sort, "+" add.
- Cover grid on cream/paper background; covers carry title/author overlay band.
- Right details pane for the selected book: cover thumbnail, title, "by
  <author>", "Percentage read : N %", "Date added :", "Last read :",
  "Word count :", "Line count :", "Description :", "Language :",
  "Publisher :", "Genre :", "File path :"; buttons "Open Book",
  "Edit Book Info", "Close".

## 4. Reader

- Dark top toolbar, white icons. Left: back, menu, TOC, bookmark. Right:
  search, read-aloud, text settings ("tT"), dictionary/translate, fullscreen.
- Serif body text, two-column "book style" default; single-column options.
- Footer status bar: left `"Chapter » Section"`, center `page/total`,
  right `N.NN%`.
- Highlights in yellow/orange/green/blue; bookmark shown as ribbon glyph
  inline; selected word highlighted blue.
- Selection popup: dictionary card (word, phonetics, POS tag, numbered
  definitions, example) + action row: highlight, note, bookmark, read-aloud,
  font?, web lookup, copy.
- In-reader annotations flyout (left panel): rows with colored type icon,
  bold text snippet, `location + timestamp`, right-aligned `N %`; selected row
  light-blue; click jumps to location.
- Reader display settings popup (right panel, dark): "Text size" A- slider A+;
  "Font style" dropdown (e.g. Segoe Script); "Page themes": White, Silver,
  Sepia, Night (selected, accent border), Solarized, Custom (color quadrants);
  "Page layout": 3 icon buttons (single / two-column / book-spread); reset
  circular-arrow button.

## 5. ReadAloud mode

- Toolbar becomes media bar: settings gear + speaker left; prev / play-pause /
  next centered; close X + fullscreen right. Blue progress line under toolbar.
- Voice settings popup (light card): "Language" dropdown (e.g. English
  (United States)), "Voice" dropdown (e.g. Microsoft David), "Voice gender"
  Male/Female radios, "Highlight color" swatches (yellow, green, orange, gray,
  blue, multi). Spoken word highlighted in page (blue block).

## 6. Collections

- Filter dropdown: All, Notes, Highlights, Bookmarks; book selector ("All");
  "Show only favorites" checkbox.
- Groups per book: cover thumbnail + bold title + author + "Date added" /
  "Last read", divider + collapse chevron.
- Rows: colored circle icon per type (note/highlight/bookmark), location
  `"Chapter » Section"` + timestamp, quoted text, `Note :` line for notes.

## 7. Catalogs / store

- Left provider list with icons: Gutenberg, Standard Ebooks, EpubBooks,
  Manybooks, Smashwords, Feedbooks. Embedded web content on the right.
- "Download book / Do you want to download this book and add to library?"
  dialog with "Yes" (accent/brown) and "No" (gray) buttons.

## 8. Statistics dialog

- Dark rounded card, chart icon + "Statistics" title. 3-column tile grid;
  each tile: small white label + large accent number. Tiles: "Number of books
  in library", "Number of books read", "Total reading hours", "Number of pages
  flipped", "Avg. reading hours per day", "Avg. reading time (sec) per page",
  "Reading speed (words per minute)", "Avg. number of pages flipped per hour".
- Refresh icon button + "Close" button bottom-right.

## 9. Settings pages

- Left nav: Settings header; Reader, General, Sync folders, Personalization
  (selected, accent marker), Backup & Restore; Change log; About.
- Sync Folders page: description text, "Sync now" + "Add sync folder"
  buttons, folder rows with "Book count : N" + edit/delete icons; "Add Folder"
  dialog: folder picker + "..." browse, checkboxes ("Recursively search
  sub-folders", "Add books to recent list", "Sync this folder and
  automatically add new books", "Automatically remove books..."), "Add folder"
  / "Cancel".
- Reader settings include "Dictionary Language" ("Non-English languages may
  have limited dictionary coverage").

## 10. Hotkeys (blog 2020-06-14, updated 2021-01-19)

Left/Right page; Ctrl+R start / Ctrl+E exit ReadAloud; Ctrl+Left/Right line;
Space play-pause; Ctrl surveillance? No: Ctrl + +/- text size; Ctrl+T+1..5 page
themes (5 themes); F11 fullscreen.

## Rework scope for this repo (clean-room re-implementation)

Rail shell, Home sections, library filter + cover grid + details pane,
dark reader chrome + footer, settings popup (size/font/6 themes/layouts),
dictionary card + action row, grouped collections, tile statistics, accent
color themes, provider list for catalogs. No upstream assets, icons, or fonts
reused; Adwaita symbolic icons + open fonts only.
