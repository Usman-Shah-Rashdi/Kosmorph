import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk


def detect_system_dark_mode() -> bool:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        except (OSError, ImportError):
            return False
    if sys.platform == "darwin":
        try:
            res = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, check=False,
            )
            return res.stdout.strip().lower() == "dark"
        except OSError:
            return False
    gtk_theme = os.environ.get("GTK_THEME", "").lower()
    if "dark" in gtk_theme or os.environ.get("COLORFGBG", "").endswith(";0"):
        return True
    try:
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, check=False,
        )
        return "prefer-dark" in res.stdout.lower()
    except OSError:
        return False


def get_palette(dark_mode: bool) -> dict[str, str]:
    if dark_mode:
        return {
            "bg": "#0f172a",
            "sidebar": "#111827",
            "card": "#1e293b",
            "border": "#334155",
            "text": "#f8fafc",
            "muted": "#94a3b8",
            "accent": "#3b82f6",
            "accent_hover": "#2563eb",
            "input": "#0f172a",
            "log_bg": "#090d16",
            "log_fg": "#e2e8f0",
            "nav_active": "#1e293b",
        }
    return {
        "bg": "#f1f5f9",
        "sidebar": "#1e293b",
        "card": "#ffffff",
        "border": "#cbd5e1",
        "text": "#0f172a",
        "muted": "#475569",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "input": "#ffffff",
        "log_bg": "#0f172a",
        "log_fg": "#f1f5f9",
        "nav_active": "#334155",
    }


def apply_styles(root: tk.Tk, style: ttk.Style, dark_mode: bool) -> dict[str, str]:
    p = get_palette(dark_mode)
    style.theme_use("clam")
    root.configure(background=p["bg"])

    style.configure(".", font=("Segoe UI", 10))
    style.configure("TFrame", background=p["bg"])
    style.configure("Sidebar.TFrame", background=p["sidebar"])
    style.configure("Card.TFrame", background=p["card"], relief="flat")
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"])
    style.configure("Card.TLabel", background=p["card"], foreground=p["text"])
    style.configure("CardMuted.TLabel", background=p["card"], foreground=p["muted"])
    style.configure("CardTitle.TLabel", background=p["card"], foreground=p["text"], font=("Segoe UI", 11, "bold"))
    style.configure("Header.TLabel", background=p["bg"], foreground=p["text"], font=("Segoe UI", 17, "bold"))
    style.configure("Card.TCheckbutton", background=p["card"], foreground=p["text"])
    style.configure("Card.TRadiobutton", background=p["card"], foreground=p["text"])
    style.configure("TEntry", fieldbackground=p["input"], foreground=p["text"], padding=6)
    style.configure("TCombobox", fieldbackground=p["input"], foreground=p["text"], padding=5)
    style.configure(
        "Accent.TButton",
        font=("Segoe UI", 10, "bold"),
        foreground="#ffffff",
        background=p["accent"],
        padding=[14, 8],
        borderwidth=0,
    )
    style.map("Accent.TButton", background=[("active", p["accent_hover"])])
    style.configure("TButton", padding=[10, 7])
    style.configure("Horizontal.TProgressbar", troughcolor=p["border"], background=p["accent"], thickness=6)
    return p
