```text
█▄▀ █▀█ █▀ █▀▄▀█ █▀█ █▀█ █▀█ █ █
█ █ █▄█ ▄█ █ ▀ █ █▄█ █▀▄ █▀▀ █▀█
```
# Kosmorph - Special Thanks to Foldr: https://github.com/foldrhq/Foldr


**Kosmos** is a modular, lightweight, cross-platform file transformation, smart folder organization, and document utility suite powered by a decoupled Python backend and a modern desktop GUI.

Built for speed and low memory overhead, Kosmos integrates **FOLDR's** 31-category smart sorting engine, TOML custom rules, MIME-type override detection, non-sequential ID-based undo history, empty-directory cleanup, and watch-folder automation alongside multi-format document, PDF, spreadsheet, and image utilities.

---

## Architecture

```text
Kosmos/
├── kosmorph/
│   ├── __main__.py              # Entry point: launches GUI when no args given, or routes CLI
│   ├── core/                    # Shared infrastructure
│   │   ├── contracts.py         # TaskContext, TaskResult, MoveOperation, ConflictPolicy
│   │   ├── registry.py          # @register_action decorator, auto-detection & search
│   │   ├── runner.py            # Background ThreadPoolExecutor, cancel tokens, job history
│   │   ├── safety.py            # Atomic writes, collision policies, ID-based UndoJournal
│   │   ├── backends.py          # Auto-detection for LibreOffice, MS Office, Tesseract, 7-Zip
│   │   ├── config.py            # Persistent JSON configuration & user preferences
│   │   └── plugins.py           # Dynamic external plugin loader (~/.kosmos/plugins)
│   ├── modules/                 # Self-contained pure-Python feature engines
│   │   ├── organizer/           # Adapted FOLDR engine: 31 categories, TOML rules, MIME, watch
│   │   ├── converters/          # Image, Document, Office (LibreOffice + COM), Data converters
│   │   ├── pdf_tools/           # PyMuPDF-powered merge, split, compress, rotate, protect
│   │   ├── file_ops/            # Batch renamer, duplicate finder, empty dirs, checksums, ZIP
│   │   ├── image_tools/         # Pillow-powered resize, compress, EXIF strip
│   │   └── spreadsheets/        # Lightweight CSV deduplication
│   ├── cli/                     # Full CLI bound to ActionRegistry
│   └── ui/                      # Modern Tkinter GUI (dark/light theme, sidebar, live search)
├── packaging/                   # Arch PKGBUILD & Linux .desktop entry
├── .github/workflows/           # Automated CI/CD builds for .deb, .rpm, Arch, and Windows
└── tests/                       # Pytest test suite
```

---

## Running & Installation

### Run Directly from Source (No Install Required)
```bash
# Launch the desktop GUI
python -m kosmorph

# Or run CLI commands
python -m kosmorph list
python -m kosmorph organize ./Downloads --dry-run
```

### Install as a Package
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[full,dev]"
```

---

## CLI Quick Reference

```bash
kosmos                       # Launch desktop GUI
kosmos gui                   # Launch desktop GUI
kosmos list                  # List all registered actions
kosmos search pdf            # Search actions by keyword
kosmos diagnostics           # Check LibreOffice, MS Office, Tesseract, 7-Zip
kosmos organize ./Downloads --strategy extension --smart --dry-run
kosmos organize ./Downloads --recursive --depth 2
kosmos watch ./Downloads --recursive
kosmos watches               # List active background watchers
kosmos unwatch ./Downloads   # Stop a background watcher
kosmos history               # View operation history
kosmos undo                  # Undo latest operation
kosmos undo --id <ID>        # Undo specific operation by ID
kosmos convert report.docx --to pdf
kosmos convert data.json --to csv
```

---

## Acknowledgments

Special thanks to my friend https://github.com/MQSethar, creator of **Foldr**, whose 31-category sorting architecture, TOML rule engine, MIME detection, and undo-journal design inspired and power the smart organization engine at the heart of Kosmos.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
