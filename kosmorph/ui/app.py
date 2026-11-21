"""Kosmos Desktop GUI — Powered by ActionRegistry & Threaded TaskRunner."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from kosmorph import __version__
from kosmorph.core.backends import detect_backends
from kosmorph.core.config import ConfigManager
from kosmorph.core.contracts import ConflictPolicy, TaskResult
from kosmorph.core.registry import ActionSpec, registry
from kosmorph.core.runner import JobHandle, TaskRunner
from kosmorph.core.safety import UndoJournal
from kosmorph.ui.theme import apply_styles, detect_system_dark_mode


class KosmosApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"Kosmos v{__version__} — File & Document Utility Suite")
        self.root.geometry("1080x740")
        self.root.minsize(860, 600)

        self.config = ConfigManager()
        self.runner = TaskRunner(max_workers=2)
        self.active_job: JobHandle | None = None
        self.selected_files: list[Path] = []
        self.selected_action: ActionSpec | None = None

        saved_theme = self.config.get("theme", "system")
        self.dark_mode = detect_system_dark_mode() if saved_theme == "system" else (saved_theme == "dark")

        self.style = ttk.Style()
        self._build_layout()
        self._refresh_theme()
        self._select_view("organizer")
        self._populate_diagnostics()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Layout Skeleton ────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Left Sidebar
        self.sidebar = ttk.Frame(self.root, style="Sidebar.TFrame", width=220)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        self.sidebar.grid_propagate(False)

        brand = tk.Label(
            self.sidebar,
            text="KOSMOS",
            font=("Segoe UI", 16, "bold"),
            bg="#111827",
            fg="#ffffff",
            anchor="w",
            padx=20,
            pady=18,
        )
        brand.pack(fill="x")

        self.nav_buttons: dict[str, tk.Button] = {}
        nav_items = [
            ("organizer", "  Smart Organizer"),
            ("workbench", "  Convert & Tools"),
            ("cleanup", "  Duplicates & Cleanup"),
            ("history", "  History & Undo"),
            ("diagnostics", "  System & Plugins"),
        ]
        for key, label in nav_items:
            btn = tk.Button(
                self.sidebar,
                text=label,
                font=("Segoe UI", 10, "bold"),
                bd=0,
                relief="flat",
                anchor="w",
                padx=18,
                pady=11,
                cursor="hand2",
                command=lambda k=key: self._select_view(k),
            )
            btn.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[key] = btn

        # Theme toggle at bottom of sidebar
        self.theme_btn = tk.Button(
            self.sidebar,
            text="Toggle Theme",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            padx=14,
            pady=10,
            cursor="hand2",
            command=self._toggle_theme,
        )
        self.theme_btn.pack(side="bottom", fill="x", padx=12, pady=14)

        # Main Content Container
        self.main_area = ttk.Frame(self.root)
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=22, pady=(18, 8))
        self.main_area.columnconfigure(0, weight=1)
        self.main_area.rowconfigure(0, weight=1)

        self.views: dict[str, ttk.Frame] = {
            "organizer": self._build_organizer_view(),
            "workbench": self._build_workbench_view(),
            "cleanup": self._build_cleanup_view(),
            "history": self._build_history_view(),
            "diagnostics": self._build_diagnostics_view(),
        }

        # Bottom Progress + Activity Log Drawer
        bottom = ttk.Frame(self.root)
        bottom.grid(row=1, column=1, sticky="ew", padx=22, pady=(0, 14))
        bottom.columnconfigure(0, weight=1)

        prog_row = ttk.Frame(bottom)
        prog_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        prog_row.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(prog_row, textvariable=self.status_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")

        self.cancel_btn = ttk.Button(prog_row, text="Cancel", command=self._cancel_active_job, state="disabled")
        self.cancel_btn.grid(row=0, column=1, padx=(8, 0))

        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.log_text = tk.Text(bottom, height=5, wrap="word", font=("Consolas", 9), relief="flat", padx=10, pady=6)
        self.log_text.grid(row=2, column=0, sticky="ew")
        self.log(f"Kosmos v{__version__} initialized — {len(registry.all_actions())} backend actions loaded.")

    def _select_view(self, key: str) -> None:
        for k, frame in self.views.items():
            if k == key:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()
        self._style_nav_buttons(key)
        if key == "history":
            self._refresh_history()

    def _style_nav_buttons(self, active_key: str | None = None) -> None:
        p = apply_styles(self.root, self.style, self.dark_mode)
        for k, btn in self.nav_buttons.items():
            is_active = (k == active_key)
            btn.configure(
                bg=p["nav_active"] if is_active else p["sidebar"],
                fg="#ffffff" if is_active else "#cbd5e1",
                activebackground=p["nav_active"],
                activeforeground="#ffffff",
            )
        self.theme_btn.configure(
            bg=p["nav_active"],
            fg="#f8fafc",
            activebackground=p["accent"],
            activeforeground="#ffffff",
        )

    def _refresh_theme(self) -> None:
        p = apply_styles(self.root, self.style, self.dark_mode)
        self.theme_btn.configure(text="☀ Switch to Light" if self.dark_mode else "☾ Switch to Dark")
        self.log_text.configure(bg=p["log_bg"], fg=p["log_fg"], insertbackground="#ffffff")

    def _toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.config.set("theme", "dark" if self.dark_mode else "light")
        self._refresh_theme()

    def log(self, msg: str) -> None:
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.status_var.set(msg)

    # ── View 1: Smart Organizer (FOLDR Engine) ─────────────────────────────────

    def _build_organizer_view(self) -> ttk.Frame:
        view = ttk.Frame(self.main_area)
        view.columnconfigure(0, weight=1)
        view.rowconfigure(2, weight=1)

        ttk.Label(view, text="Smart Folder Organizer", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            view,
            text="Organize directories into 31 smart categories with preview, MIME inspection, and ID-based undo.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        card = ttk.Frame(view, style="Card.TFrame", padding=18)
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)
        card.rowconfigure(4, weight=1)

        ttk.Label(card, text="Target Folder", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        self.org_dir_var = tk.StringVar()
        ttk.Entry(card, textvariable=self.org_dir_var).grid(row=0, column=1, sticky="ew", padx=10, pady=6)
        ttk.Button(card, text="Browse...", command=self._browse_org_dir).grid(row=0, column=2, pady=6)

        ttk.Label(card, text="Sort Strategy", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        strat_row = ttk.Frame(card, style="Card.TFrame")
        strat_row.grid(row=1, column=1, columnspan=2, sticky="w", padx=10, pady=6)
        self.org_strategy_var = tk.StringVar(value="extension")
        for val, lbl in [("extension", "Smart Category (31 types)"), ("date", "Year / Month"), ("size", "File Size")]:
            ttk.Radiobutton(strat_row, text=lbl, value=val, variable=self.org_strategy_var, style="Card.TRadiobutton").pack(
                side="left", padx=(0, 14)
            )

        opts_row = ttk.Frame(card, style="Card.TFrame")
        opts_row.grid(row=2, column=1, columnspan=2, sticky="w", padx=10, pady=6)
        self.org_recursive_var = tk.BooleanVar(value=False)
        self.org_smart_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts_row, text="Include subfolders (root-targeted)", variable=self.org_recursive_var, style="Card.TCheckbutton").pack(
            side="left", padx=(0, 16)
        )
        ttk.Checkbutton(opts_row, text="Content MIME override (--smart)", variable=self.org_smart_var, style="Card.TCheckbutton").pack(
            side="left"
        )

        btn_row = ttk.Frame(card, style="Card.TFrame")
        btn_row.grid(row=3, column=1, columnspan=2, sticky="w", padx=10, pady=(10, 12))
        ttk.Button(btn_row, text="Preview Plan", command=lambda: self._run_organizer(dry_run=True)).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Organize Now", style="Accent.TButton", command=lambda: self._run_organizer(dry_run=False)).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(btn_row, text="Undo Last", command=self._quick_undo).pack(side="left")

        self.org_preview_list = tk.Listbox(card, font=("Consolas", 9), relief="flat")
        self.org_preview_list.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        return view

    def _browse_org_dir(self) -> None:
        folder = filedialog.askdirectory(title="Select Folder to Organize")
        if folder:
            self.org_dir_var.set(folder)

    def _run_organizer(self, dry_run: bool) -> None:
        folder = self.org_dir_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("Invalid Directory", "Please select a valid folder to organize.")
            return

        self.org_preview_list.delete(0, tk.END)
        self._submit_job(
            "organizer.sort",
            dry_run=dry_run,
            target_dir=Path(folder),
            recursive=self.org_recursive_var.get(),
            strategy=self.org_strategy_var.get(),
            smart_mime=self.org_smart_var.get(),
            on_done=self._on_organizer_complete,
        )

    def _on_organizer_complete(self, res: TaskResult) -> None:
        self.org_preview_list.delete(0, tk.END)
        for op in res.operations[:200]:
            self.org_preview_list.insert(tk.END, f"[{op.category}]  {op.source.name}  ->  {op.destination.parent.name}/{op.destination.name}")
        if len(res.operations) > 200:
            self.org_preview_list.insert(tk.END, f"... and {len(res.operations) - 200} more file(s)")
        self.log(res.message)

    # ── View 2: Universal Convert & Tools Workbench ────────────────────────────

    def _build_workbench_view(self) -> ttk.Frame:
        view = ttk.Frame(self.main_area)
        view.columnconfigure(0, weight=1)
        view.rowconfigure(2, weight=1)

        ttk.Label(view, text="Convert & Document Workbench", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            view,
            text="Select files and search or filter any registered converter, PDF tool, or batch utility.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        card = ttk.Frame(view, style="Card.TFrame", padding=18)
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)
        card.rowconfigure(3, weight=1)

        # File selection
        ttk.Label(card, text="Selected File(s)", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        self.wb_files_var = tk.StringVar(value="No files selected.")
        ttk.Entry(card, textvariable=self.wb_files_var, state="readonly").grid(row=0, column=1, sticky="ew", padx=10, pady=6)
        ttk.Button(card, text="Select Files...", command=self._browse_workbench_files).grid(row=0, column=2, pady=6)

        # Action search filter
        ttk.Label(card, text="Filter Actions", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        self.wb_search_var = tk.StringVar()
        self.wb_search_var.trace_add("write", lambda *_: self._refresh_action_list())
        ttk.Entry(card, textvariable=self.wb_search_var).grid(row=1, column=1, sticky="ew", padx=10, pady=6)
        ttk.Button(card, text="Auto-Match Files", command=self._auto_match_actions).grid(row=1, column=2, pady=6)

        # Parameters row (target format / conflict policy / template)
        params = ttk.Frame(card, style="Card.TFrame")
        params.grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Label(params, text="Target Format:", style="Card.TLabel").pack(side="left")
        self.wb_target_var = tk.StringVar(value="pdf")
        self.wb_target_combo = ttk.Combobox(params, textvariable=self.wb_target_var, width=10, values=["pdf", "png", "jpg", "webp", "txt", "docx", "html", "csv", "json", "yaml", "xml"])
        self.wb_target_combo.pack(side="left", padx=(6, 16))

        ttk.Label(params, text="If Exists:", style="Card.TLabel").pack(side="left")
        self.wb_conflict_var = tk.StringVar(value="rename")
        ttk.Combobox(params, textvariable=self.wb_conflict_var, width=10, state="readonly", values=["rename", "overwrite", "skip"]).pack(
            side="left", padx=(6, 16)
        )

        ttk.Label(params, text="Extra Arg / Password / Template:", style="Card.TLabel").pack(side="left")
        self.wb_extra_var = tk.StringVar(value="")
        ttk.Entry(params, textvariable=self.wb_extra_var, width=22).pack(side="left", padx=(6, 0))

        # Action Listbox + Execute button
        self.wb_action_list = tk.Listbox(card, font=("Consolas", 10), relief="flat")
        self.wb_action_list.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(4, 10))
        self.wb_action_list.bind("<<ListboxSelect>>", self._on_action_selected)

        exec_row = ttk.Frame(card, style="Card.TFrame")
        exec_row.grid(row=4, column=0, columnspan=3, sticky="ew")
        self.wb_desc_var = tk.StringVar(value="Select an action from the list above.")
        ttk.Label(exec_row, textvariable=self.wb_desc_var, style="CardMuted.TLabel").pack(side="left")
        ttk.Button(exec_row, text="Execute Action", style="Accent.TButton", command=self._execute_workbench_action).pack(side="right")

        self._displayed_actions: list[ActionSpec] = []
        self._refresh_action_list()
        return view

    def _browse_workbench_files(self) -> None:
        chosen = filedialog.askopenfilenames(title="Select Files")
        if chosen:
            self.selected_files = [Path(p) for p in chosen]
            self.wb_files_var.set(f"{len(self.selected_files)} file(s): " + ", ".join(p.name for p in self.selected_files[:4]))
            self._auto_match_actions()

    def _auto_match_actions(self) -> None:
        if not self.selected_files:
            self._refresh_action_list()
            return
        exts = {p.suffix.lower() for p in self.selected_files}
        matches = registry.matching_actions(exts)
        self._populate_actions(matches or registry.all_actions())

    def _refresh_action_list(self) -> None:
        query = self.wb_search_var.get()
        self._populate_actions(registry.search(query))

    def _populate_actions(self, specs: list[ActionSpec]) -> None:
        self._displayed_actions = specs
        self.wb_action_list.delete(0, tk.END)
        for spec in specs:
            exts = ", ".join(sorted(spec.input_extensions)) or "*"
            self.wb_action_list.insert(tk.END, f"[{spec.category}]  {spec.name}  ({exts})")

    def _on_action_selected(self, _event=None) -> None:
        sel = self.wb_action_list.curselection()
        if not sel:
            return
        spec = self._displayed_actions[sel[0]]
        self.selected_action = spec
        self.wb_desc_var.set(spec.description)
        if spec.output_formats:
            self.wb_target_combo.configure(values=spec.output_formats)
            self.wb_target_var.set(spec.output_formats[0])

    def _execute_workbench_action(self) -> None:
        if not self.selected_action:
            messagebox.showinfo("Select Action", "Choose an action from the list first.")
            return
        spec = self.selected_action
        if not self.selected_files:
            messagebox.showerror("No Files", "Select one or more input files first.")
            return

        policy = ConflictPolicy(self.wb_conflict_var.get())
        target = self.wb_target_var.get().strip()
        extra = self.wb_extra_var.get().strip()
        kwargs: dict = {}

        if spec.id in {"convert.image", "convert.structured"}:
            kwargs = {"paths": self.selected_files, "target_format": target}
        elif spec.id == "pdf.split":
            kwargs = {"path": self.selected_files[0]}
        elif spec.id == "pdf.rotate":
            angle = int(extra) if extra.isdigit() else 90
            kwargs = {"paths": self.selected_files, "angle": angle}
        elif spec.id == "pdf.encrypt":
            if not extra:
                messagebox.showerror("Password Required", "Enter a password in the Extra Arg field.")
                return
            kwargs = {"paths": self.selected_files, "user_password": extra}
        elif spec.id == "files.batch_rename":
            kwargs = {"paths": self.selected_files, "template": extra or "{name}_{num:03d}{ext}"}
        elif spec.id == "files.create_zip":
            out_zip = self.selected_files[0].parent / (extra or "archive.zip")
            kwargs = {"paths": self.selected_files, "output_path": out_zip}
        elif spec.id == "tables.deduplicate_csv":
            kwargs = {"path": self.selected_files[0]}
        else:
            kwargs = {"paths": self.selected_files}

        self._submit_job(spec.id, conflict_policy=policy, **kwargs)

    # ── View 3: Duplicates & Empty Folder Cleanup ──────────────────────────────

    def _build_cleanup_view(self) -> ttk.Frame:
        view = ttk.Frame(self.main_area)
        view.columnconfigure(0, weight=1)
        view.rowconfigure(2, weight=1)

        ttk.Label(view, text="Duplicates & Empty Folder Cleanup", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            view,
            text="Two-pass SHA-256 duplicate file finder and deepest-first empty directory cleaner.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        card = ttk.Frame(view, style="Card.TFrame", padding=18)
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(1, weight=1)
        card.rowconfigure(3, weight=1)

        ttk.Label(card, text="Scan Directory", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        self.clean_dir_var = tk.StringVar()
        ttk.Entry(card, textvariable=self.clean_dir_var).grid(row=0, column=1, sticky="ew", padx=10, pady=6)
        ttk.Button(card, text="Browse...", command=self._browse_clean_dir).grid(row=0, column=2, pady=6)

        ttk.Label(card, text="Dedup Strategy", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        self.dedup_strat_var = tk.StringVar(value="keep-newest")
        ttk.Combobox(
            card,
            textvariable=self.dedup_strat_var,
            state="readonly",
            values=["keep-newest", "keep-oldest", "keep-largest"],
            width=18,
        ).grid(row=1, column=1, sticky="w", padx=10, pady=6)

        btns = ttk.Frame(card, style="Card.TFrame")
        btns.grid(row=2, column=1, columnspan=2, sticky="w", padx=10, pady=8)
        ttk.Button(btns, text="Scan Duplicates", command=lambda: self._run_dedup(delete=False)).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Delete Duplicates", command=lambda: self._run_dedup(delete=True)).pack(side="left", padx=(0, 14))
        ttk.Button(btns, text="Scan Empty Folders", command=lambda: self._run_empty_dirs(dry_run=True)).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Remove Empty Folders", style="Accent.TButton", command=lambda: self._run_empty_dirs(dry_run=False)).pack(
            side="left"
        )

        self.clean_list = tk.Listbox(card, font=("Consolas", 9), relief="flat")
        self.clean_list.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        return view

    def _browse_clean_dir(self) -> None:
        folder = filedialog.askdirectory(title="Select Directory to Scan")
        if folder:
            self.clean_dir_var.set(folder)

    def _run_dedup(self, delete: bool) -> None:
        folder = self.clean_dir_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("Invalid Directory", "Select a valid directory first.")
            return
        if delete and not messagebox.askyesno("Confirm Deletion", "Permanently delete duplicate files? This cannot be undone."):
            return
        self._submit_job(
            "files.find_duplicates",
            target_dir=Path(folder),
            strategy=self.dedup_strat_var.get(),
            delete_duplicates=delete,
            on_done=self._on_dedup_done,
        )

    def _on_dedup_done(self, res: TaskResult) -> None:
        self.clean_list.delete(0, tk.END)
        for digest, paths in res.metadata.get("duplicates", {}).items():
            self.clean_list.insert(tk.END, f"SHA256 {digest[:12]}... ({len(paths)} copies):")
            for p in paths:
                self.clean_list.insert(tk.END, f"   {p}")
        self.log(res.message)

    def _run_empty_dirs(self, dry_run: bool) -> None:
        folder = self.clean_dir_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("Invalid Directory", "Select a valid directory first.")
            return
        self._submit_job(
            "files.clean_empty_dirs",
            dry_run=dry_run,
            target_dir=Path(folder),
            on_done=self._on_empty_dirs_done,
        )

    def _on_empty_dirs_done(self, res: TaskResult) -> None:
        self.clean_list.delete(0, tk.END)
        for p in res.outputs:
            self.clean_list.insert(tk.END, str(p))
        self.log(res.message)

    # ── View 4: History & ID-Based Undo ────────────────────────────────────────

    def _build_history_view(self) -> ttk.Frame:
        view = ttk.Frame(self.main_area)
        view.columnconfigure(0, weight=1)
        view.rowconfigure(2, weight=1)

        ttk.Label(view, text="Operation History & Rollback", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            view,
            text="Revert any past organization or batch rename independently by Operation ID.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        card = ttk.Frame(view, style="Card.TFrame", padding=18)
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)

        self.history_list = tk.Listbox(card, font=("Consolas", 10), relief="flat")
        self.history_list.grid(row=0, column=0, sticky="nsew")

        btn_row = ttk.Frame(card, style="Card.TFrame")
        btn_row.grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Button(btn_row, text="Refresh", command=self._refresh_history).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Revert Selected Operation", style="Accent.TButton", command=self._undo_selected).pack(side="left")

        self._history_entries: list[dict] = []
        return view

    def _refresh_history(self) -> None:
        self._history_entries = UndoJournal().list_entries(limit=50)
        self.history_list.delete(0, tk.END)
        for e in self._history_entries:
            self.history_list.insert(
                tk.END,
                f"[{e['id']}]  {e['timestamp'][:19]}  |  {e['action']:<20}  |  {e['total_files']} file(s)  |  {e['base']}",
            )

    def _undo_selected(self) -> None:
        sel = self.history_list.curselection()
        op_id = self._history_entries[sel[0]]["id"] if sel else None
        restored, skipped, logs = UndoJournal().undo(operation_id=op_id)
        self.log(f"Undo complete: restored {restored} file(s), skipped {skipped}.")
        for line in logs:
            self.log(f"  {line}")
        self._refresh_history()

    def _quick_undo(self) -> None:
        restored, skipped, _ = UndoJournal().undo()
        self.log(f"Undo latest: restored {restored} file(s), skipped {skipped}.")

    # ── View 5: System Backends & Diagnostics ──────────────────────────────────

    def _build_diagnostics_view(self) -> ttk.Frame:
        view = ttk.Frame(self.main_area)
        view.columnconfigure(0, weight=1)
        view.rowconfigure(2, weight=1)

        ttk.Label(view, text="System Backends & Diagnostics", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            view,
            text="External tools auto-detected on this system for Office, OCR, and archive workflows.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 12))

        card = ttk.Frame(view, style="Card.TFrame", padding=18)
        card.grid(row=2, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)

        self.diag_text = tk.Text(card, font=("Consolas", 10), relief="flat", state="disabled")
        self.diag_text.grid(row=0, column=0, sticky="nsew")
        return view

    def _populate_diagnostics(self) -> None:
        def _probe() -> None:
            statuses = detect_backends()
            lines = ["External Backend Status:\n"]
            for name, st in statuses.items():
                state = "AVAILABLE" if st.available else "NOT FOUND"
                lines.append(f"  • {name:<14} : {state}")
                if st.path:
                    lines.append(f"      Path       : {st.path}")
                if st.version:
                    lines.append(f"      Version    : {st.version}")
            lines.append(f"\nRegistered Actions : {len(registry.all_actions())}")
            lines.append(f"User Config Dir    : {Path.home() / '.kosmos'}")
            report = "\n".join(lines)
            self.root.after(0, lambda: self._set_diag_text(report))

        threading.Thread(target=_probe, daemon=True).start()

    def _set_diag_text(self, text: str) -> None:
        self.diag_text.configure(state="normal")
        self.diag_text.delete("1.0", tk.END)
        self.diag_text.insert("1.0", text)
        self.diag_text.configure(state="disabled")

    # ── Background Job Execution Bridge ────────────────────────────────────────

    def _submit_job(
        self,
        action_id: str,
        *,
        conflict_policy: ConflictPolicy = ConflictPolicy.RENAME,
        dry_run: bool = False,
        on_done=None,
        **kwargs,
    ) -> None:
        self.progress["value"] = 0
        self.cancel_btn.configure(state="normal")

        def _on_progress(current: int, total: int, message: str) -> None:
            pct = int((current / max(1, total)) * 100)
            self.root.after(0, lambda: self._update_progress(pct, message))

        def _on_complete(res: TaskResult) -> None:
            self.root.after(0, lambda: self._finish_job(res, on_done))

        self.active_job = self.runner.submit(
            action_id,
            on_progress=_on_progress,
            on_complete=_on_complete,
            conflict_policy=conflict_policy,
            dry_run=dry_run,
            **kwargs,
        )

    def _update_progress(self, pct: int, message: str) -> None:
        self.progress["value"] = pct
        if message:
            self.status_var.set(message)

    def _finish_job(self, res: TaskResult, on_done=None) -> None:
        self.progress["value"] = 100
        self.cancel_btn.configure(state="disabled")
        self.active_job = None
        if on_done:
            on_done(res)
        else:
            self.log(res.message)
        for err in res.errors:
            self.log(f"[ERROR] {err}")

    def _cancel_active_job(self) -> None:
        if self.active_job:
            self.active_job.cancel()
            self.log("Cancellation requested...")

    def _on_close(self) -> None:
        self.runner.shutdown()
        self.root.destroy()


def launch_gui() -> None:
    root = tk.Tk()
    KosmosApp(root)
    root.mainloop()
