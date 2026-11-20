# Kosmorph - Special Thanks to Foldr:https://github.com/foldrhq/Foldr


**Kosmorph** is a modular, lightweight, cross-platform file transformation, folder organization, and document utility suite built on a decoupled Python backend.

Designed for speed and minimal footprint, Kosmorph keeps its core engine completely independent of any UI layer—allowing the same actions to run seamlessly from a desktop GUI, a CLI, or automated watch-folder workflows.

---

## Core Architecture

```text
Kosmorph/
├── kosmorph/
│   ├── __main__.py              # Entry point (CLI + GUI router)
│   ├── core/                    # Shared infrastructure
│   │   ├── contracts.py         # TaskContext, TaskResult, MoveOperation, ConflictPolicy
│   │   ├── registry.py          # @register_action decorator, auto-detection & search
│   │   ├── runner.py            # Background ThreadPoolExecutor, cancel tokens, retry
│   │   ├── safety.py            # Atomic writes, collision policies, persistent UndoJournal
│   │   ├── backends.py          # Auto-detection for LibreOffice, MS Office, Tesseract, 7-Zip
│   │   ├── config.py            # Persistent JSON configuration & user preferences
│   │   └── plugins.py           # Dynamic external plugin loader
│   ├── modules/                 # Self-contained pure-Python feature engines
│   │   ├── organizer/           # Rule-based & MIME-aware folder organizer + undo
│   │   ├── converters/          # Image, Document, Office, and Structured Data converters
│   │   ├── pdf_tools/           # PyMuPDF-powered merge, split, compress, rotate, protect
│   │   ├── file_ops/            # Batch renamer, duplicate finder, checksums, archives
│   │   ├── image_tools/         # Pillow-powered resize, crop, compress, EXIF strip, sheets
│   │   └── spreadsheets/        # Lightweight CSV/JSON table utilities
│   ├── cli/                     # Command-line interface bound to ActionRegistry
│   └── ui/                      # Legacy Tkinter UI bridge (to be upgraded in Phase 5)
├── packaging/                   # Arch PKGBUILD & packaging templates
├── .github/workflows/           # Automated CI/CD builds for .deb, .rpm, Arch, and Windows
└── tests/                       # Pytest test suite
```

---

## Installation

### Minimal Core (Recommended)
```bash
git clone https://github.com/Usman-Shah-Rashdi/PyUtilSuite.git Kosmorph
cd Kosmorph
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### With Optional Extras (`pdf2docx`, `openpyxl`)
```bash
pip install -e ".[full]"
```

---

## CLI Usage

```bash
# List all registered actions and supported extensions
kosmorph list

# Search actions by keyword
kosmorph search pdf

# Check detected system backends (LibreOffice, MS Office, Tesseract, 7-Zip)
kosmorph diagnostics

# Preview folder organization (dry run)
kosmorph organize ./Downloads --strategy extension --dry-run

# Execute folder organization and undo if needed
kosmorph organize ./Downloads --strategy extension
kosmorph undo

# Convert files
kosmorph convert image.png --to webp
kosmorph convert data.json --to csv
kosmorph convert document.md --to html

# Launch the desktop UI
kosmorph gui
```

---

## Packaging & Releases

Every Git tag matching `v*` triggers `.github/workflows/package.yml` to build and attach native distributables:
- **Debian / Ubuntu:** `.deb` package
- **Fedora / RHEL / openSUSE:** `.rpm` package
- **Arch Linux:** `.pkg.tar.zst` package via `makepkg`
- **Windows:** Standalone `.exe` bundle via PyInstaller

---

## License

MIT License — see [LICENSE](LICENSE) for details.
