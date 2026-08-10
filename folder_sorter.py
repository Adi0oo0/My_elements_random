#!/usr/bin/env python3
"""
folder_sorter_modern.py

A modern desktop GUI front-end for the folder-sorting logic.
Powered by CustomTkinter for a sleek, responsive UI.

Run it with:
    pip install customtkinter
    python folder_sorter_modern.py
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

# ---------------------------------------------------------------------------
# Sorting rules & logic (Unchanged)
# ---------------------------------------------------------------------------

CATEGORIES: list[dict] = [
    {
        "folder_name": "Images",
        "color": "#ec4899",
        "description": "Image files: photos, drawings, screenshots, icons.\nCommon extensions: .jpg .jpeg .png .gif .bmp .webp .svg .heic .tiff",
        "extensions": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".heif", ".tiff", ".tif", ".ico", ".raw", ".psd", ".ai", ".eps"},
    },
    {
        "folder_name": "Videos",
        "color": "#ef4444",
        "description": "Video files: recordings, movies, screen captures.\nCommon extensions: .mp4 .mov .avi .mkv .webm .flv .wmv .m4v",
        "extensions": {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v", ".mpg", ".mpeg", ".3gp"},
    },
    {
        "folder_name": "Audio",
        "color": "#14b8a6",
        "description": "Audio files: music, recordings, sound effects, voice memos.\nCommon extensions: .mp3 .wav .flac .aac .ogg .m4a .wma .opus",
        "extensions": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus", ".aiff", ".alac"},
    },
    {
        "folder_name": "Documents",
        "color": "#3b82f6",
        "description": "Text-based documents: PDFs, Word, spreadsheets, presentations,\nplain text, markdown, ebooks.",
        "extensions": {".pdf", ".doc", ".docx", ".txt", ".md", ".markdown", ".rtf", ".odt", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".csv", ".epub", ".mobi", ".tex", ".pages", ".numbers", ".key"},
    },
    {
        "folder_name": "Code",
        "color": "#8b5cf6",
        "description": "Source code and developer files: scripts, source, config, notebooks.",
        "extensions": {".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".html", ".htm", ".css", ".scss", ".sass", ".less", ".json", ".yaml", ".yml", ".toml", ".xml", ".sh", ".bash", ".bat", ".ps1", ".java", ".class", ".c", ".cpp", ".cc", ".h", ".hpp", ".rs", ".go", ".rb", ".php", ".sql", ".ipynb", ".ini", ".env", ".dockerfile", ".vue", ".svelte"},
    },
    {
        "folder_name": "Archives",
        "color": "#f59e0b",
        "description": "Compressed archives and disk images.\nCommon extensions: .zip .rar .7z .tar .gz .bz2 .xz .tgz .iso .dmg",
        "extensions": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".tbz2", ".txz", ".iso", ".dmg"},
    },
    {
        "folder_name": "Installers",
        "color": "#78716c",
        "description": "Software installers, executables, and packages.\nCommon extensions: .exe .msi .apk .deb .rpm .pkg .appx .whl",
        "extensions": {".exe", ".msi", ".apk", ".deb", ".rpm", ".pkg", ".appx", ".whl", ".jar", ".bin", ".run"},
    },
    {
        "folder_name": "Fonts",
        "color": "#22c55e",
        "description": "Font files.\nCommon extensions: .ttf .otf .woff .woff2 .eot",
        "extensions": {".ttf", ".otf", ".woff", ".woff2", ".eot"},
    },
    {
        "folder_name": "Other",
        "color": "#6b7280",
        "description": "Files that did not match a known category. Stored here so nothing\nis lost -- review and rename later.",
        "extensions": set(),
    },
]

CATEGORY_BY_NAME = {c["folder_name"]: c for c in CATEGORIES}

@dataclass
class PlanEntry:
    source: Path
    target_dir: Path
    category: str

def classify(path: Path) -> str | None:
    if path.is_dir():
        return None
    ext = path.suffix.lower()
    for cat in CATEGORIES:
        if not cat["extensions"]:
            continue
        if ext in cat["extensions"]:
            return cat["folder_name"]
    return "Other"

def build_plan(folder: Path) -> list[PlanEntry]:
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")
    plan: list[PlanEntry] = []
    for child in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir():
            continue
        category = classify(child)
        if category is None:
            continue
        plan.append(PlanEntry(
            source=child,
            target_dir=folder / category,
            category=category,
        ))
    return plan

def move_with_collision_handling(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / src.name
    if not target.exists():
        shutil.move(str(src), str(target))
        return target
    stem, suffix = src.stem, src.suffix
    n = 1
    while True:
        candidate = dst_dir / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            shutil.move(str(src), str(candidate))
            return candidate
        n += 1

def write_readme(target_dir: Path, description: str) -> None:
    readme = target_dir / "README.txt"
    if readme.exists():
        return
    readme.write_text(
        f"This folder is auto-generated by Folder Sorter.\n\n"
        f"{description}\n\n"
        f"You can safely delete this README.txt once you no longer\n"
        f"need the explanation.\n",
        encoding="utf-8",
    )

def open_in_file_manager(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Modern Application GUI (CustomTkinter)
# ---------------------------------------------------------------------------

ctk.set_appearance_mode("System")  # "System", "Dark", or "Light"
ctk.set_default_color_theme("blue")

class FolderSorterApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Folder Sorter")
        self.geometry("1040x700")
        self.minsize(860, 580)

        # State Variables
        self.folder: Path | None = None
        self.full_plan: list[PlanEntry] = []
        self.category_vars: dict[str, tk.BooleanVar] = {}
        self.readme_var = tk.BooleanVar(value=True)
        self.msg_queue: "queue.Queue[tuple]" = queue.Queue()
        self.busy = False

        self._configure_treeview_style()
        self._build_layout()
        self._refresh_summary()
        self.after(120, self._poll_queue)

    def _configure_treeview_style(self):
        """Theme the ttk.Treeview to blend nicely with CustomTkinter"""
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#f9f9fa",
            fieldbackground="#2b2b2b" if ctk.get_appearance_mode() == "Dark" else "#f9f9fa",
            foreground="white" if ctk.get_appearance_mode() == "Dark" else "black",
            rowheight=28, borderwidth=0, font=("Segoe UI", 10)
        )
        style.map('Treeview', background=[('selected', '#1f538d')])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. SIDEBAR
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1) # Makes the category frame expand

        # Sidebar: Header
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Folder Sorter", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        self.sub_label = ctk.CTkLabel(self.sidebar, text="Select & sort automatically.", font=ctk.CTkFont(size=12), text_color="gray")
        self.sub_label.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # Sidebar: Folder Selection
        self.folder_var = tk.StringVar(value="No folder selected")
        self.path_entry = ctk.CTkEntry(self.sidebar, textvariable=self.folder_var, state="disabled")
        self.path_entry.grid(row=3, column=0, padx=20, pady=(0, 5), sticky="ew")
        
        self.browse_btn = ctk.CTkButton(self.sidebar, text="Browse Folder...", fg_color="transparent", border_width=2, command=self.browse_folder)
        self.browse_btn.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="ew")

        # Sidebar: Categories (Scrollable so buttons don't hide)
        self.cat_frame = ctk.CTkScrollableFrame(self.sidebar, label_text="Categories to sort")
        self.cat_frame.grid(row=2, column=0, padx=10, pady=(10, 10), sticky="nsew")

        for cat in CATEGORIES:
            var = tk.BooleanVar(value=True)
            self.category_vars[cat["folder_name"]] = var
            cb = ctk.CTkCheckBox(
                self.cat_frame, 
                text=cat["folder_name"], 
                variable=var, 
                command=self._refresh_tree,
                text_color=cat["color"]
            )
            cb.pack(anchor="w", pady=5, padx=10)

        # Sidebar: Settings & Actions (Pinned to bottom)
        self.settings_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.settings_frame.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.readme_cb = ctk.CTkCheckBox(self.settings_frame, text="Generate READMEs", variable=self.readme_var)
        self.readme_cb.pack(anchor="w", pady=(0, 15))

        self.scan_btn = ctk.CTkButton(self.settings_frame, text="Scan Folder", command=self.scan_folder)
        self.scan_btn.pack(fill="x", pady=(0, 10))

        self.sort_btn = ctk.CTkButton(self.settings_frame, text="Sort Files", command=self.confirm_and_sort, state="disabled", fg_color="#16a34a", hover_color="#15803d")
        self.sort_btn.pack(fill="x")

        # 2. MAIN PANEL
        self.main_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.main_panel.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_panel.grid_rowconfigure(1, weight=3)
        self.main_panel.grid_rowconfigure(3, weight=1)
        self.main_panel.grid_columnconfigure(0, weight=1)

        self.summary_label = ctk.CTkLabel(self.main_panel, text="Summary details...", font=ctk.CTkFont(size=14, weight="bold"))
        self.summary_label.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Main Panel: Treeview for preview
        self.tree_frame = ctk.CTkFrame(self.main_panel)
        self.tree_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.tree_frame, show="tree", selectmode="none")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        tree_scroll = ctk.CTkScrollbar(self.tree_frame, command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)

        for cat in CATEGORIES:
            self.tree.tag_configure(f"cat_{cat['folder_name']}", foreground=cat["color"])

        # Main Panel: Logs
        ctk.CTkLabel(self.main_panel, text="Activity Log", font=ctk.CTkFont(size=12, weight="bold")).grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        self.log_text = ctk.CTkTextbox(self.main_panel, state="disabled", font=("Consolas", 12))
        self.log_text.grid(row=3, column=0, sticky="nsew")

        # 3. STATUS BAR
        self.status_bar = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.status_bar.grid(row=1, column=1, sticky="ew", padx=20, pady=(0, 20))
        self.status_bar.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(self.status_bar, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(self.status_bar, text="Ready.", text_color="gray")
        self.status_label.grid(row=0, column=1, padx=(0, 20))

        self._log("Ready. Pick a folder to get started.")
        self._show_empty_tree("Choose a folder and click 'Scan Folder' to preview the sort.")

    # -- helpers ---------------------------------------------------------

    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _show_empty_tree(self, text: str) -> None:
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("", "end", text=text)

    def _filtered_plan(self) -> list[PlanEntry]:
        return [e for e in self.full_plan if self.category_vars[e.category].get()]

    def _refresh_summary(self) -> None:
        plan = self._filtered_plan()
        if not self.folder:
            self.summary_label.configure(text="No folder selected yet")
        elif not self.full_plan:
            self.summary_label.configure(text=f"{self.folder.name} — scanned, nothing to sort here")
        else:
            cats = {e.category for e in plan}
            self.summary_label.configure(
                text=f"{len(plan)} file(s) ready across {len(cats)} category(s)  ·  {self.folder.name}"
            )

    def _refresh_tree(self) -> None:
        plan = self._filtered_plan()
        self.tree.delete(*self.tree.get_children())
        
        if not self.folder:
            self._show_empty_tree("Choose a folder and click 'Scan Folder'.")
            self.sort_btn.configure(state="disabled")
            return
        if not self.full_plan:
            self._show_empty_tree("Nothing to sort — this folder is already tidy.")
            self.sort_btn.configure(state="disabled")
            return
        if not plan:
            self._show_empty_tree("All categories unticked — nothing selected.")
            self.sort_btn.configure(state="disabled")
            return

        by_cat: dict[str, list[PlanEntry]] = {}
        for entry in plan:
            by_cat.setdefault(entry.category, []).append(entry)

        for cat in CATEGORIES:
            name = cat["folder_name"]
            if name not in by_cat:
                continue
            items = by_cat[name]
            node = self.tree.insert("", "end", text=f"{name} ({len(items)})", tags=(f"cat_{name}",), open=True)
            for entry in items:
                self.tree.insert(node, "end", text=entry.source.name)

        self._refresh_summary()
        self.sort_btn.configure(state="normal" if plan else "disabled")

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.scan_btn.configure(state=state)
        self.browse_btn.configure(state=state)
        self.sort_btn.configure(state="normal" if (not busy and self._filtered_plan()) else "disabled")

    # -- actions -----------------------------------------------------------

    def browse_folder(self) -> None:
        if self.busy: return
        chosen = filedialog.askdirectory(title="Choose a folder to sort")
        if not chosen: return
        
        self.folder = Path(chosen)
        self.folder_var.set(str(self.folder))
        self.full_plan = []
        self.sort_btn.configure(state="disabled")
        self._show_empty_tree("Click 'Scan Folder' to preview the sort.")
        self._refresh_summary()
        self._log(f"Selected folder: {self.folder}")
        self._set_status("Folder selected.")

    def scan_folder(self) -> None:
        if not self.folder:
            messagebox.showinfo("Choose a folder", "Pick a folder first.")
            return
        try:
            self.full_plan = build_plan(self.folder)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        self._refresh_tree()
        n = len(self.full_plan)
        self._log(f"Scanned '{self.folder.name}' — found {n} file(s).")
        self._set_status(f"Scan complete. {n} file(s) found.")

    def confirm_and_sort(self) -> None:
        plan = self._filtered_plan()
        if not plan: return
        cats = sorted({e.category for e in plan})
        ok = messagebox.askyesno(
            "Sort files?",
            f"This will move {len(plan)} file(s) into {len(cats)} subfolder(s).\n\nContinue?"
        )
        if ok:
            self._start_sort(plan)

    def _start_sort(self, plan: list[PlanEntry]) -> None:
        self._set_busy(True)
        self.progress.set(0)
        self._set_status("Sorting...")
        thread = threading.Thread(target=self._worker_sort, args=(plan, self.readme_var.get()), daemon=True)
        thread.start()

    def _worker_sort(self, plan: list[PlanEntry], write_notes: bool) -> None:
        moved, failed = 0, 0
        touched_categories: set[str] = set()
        total = len(plan)
        
        for i, entry in enumerate(plan, start=1):
            try:
                dest = move_with_collision_handling(entry.source, entry.target_dir)
                touched_categories.add(entry.category)
                self.msg_queue.put(("log", f"Moved: {entry.source.name} → {entry.category}/{dest.name}"))
                moved += 1
            except Exception as exc:
                self.msg_queue.put(("log", f"Skipped: {entry.source.name} — {exc}"))
                failed += 1
            
            # Send progress percentage
            self.msg_queue.put(("progress", i / total))

        if write_notes:
            for name in touched_categories:
                cat = CATEGORY_BY_NAME[name]
                target_dir = self.folder / name  # type: ignore[union-attr]
                if target_dir.exists():
                    try: write_readme(target_dir, cat["description"])
                    except Exception: pass

        self.msg_queue.put(("done", (moved, failed, len(touched_categories))))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "progress":
                    self.progress.set(payload)
                elif kind == "done":
                    moved, failed, ncats = payload
                    self._on_sort_done(moved, failed, ncats)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _on_sort_done(self, moved: int, failed: int, ncats: int) -> None:
        self._set_busy(False)
        self.progress.set(1.0)
        summary = f"Done! Moved {moved} file(s) into {ncats} folder(s)."
        if failed: summary += f" {failed} failed."
        
        self._log(summary)
        self._set_status(summary)

        # Rescan
        if self.folder:
            try: self.full_plan = build_plan(self.folder)
            except Exception: self.full_plan = []
        self._refresh_tree()

        if messagebox.askyesno("Done", summary + "\n\nOpen the folder now?"):
            if self.folder:
                open_in_file_manager(self.folder)

if __name__ == "__main__":
    app = FolderSorterApp()
    app.mainloop()