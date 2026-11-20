import tkinter as tk
from kosmorph.core.registry import registry


def launch_gui() -> None:
    """Minimal placeholder bridge verifying the decoupled backend registry until Phase 5 UI."""
    root = tk.Tk()
    root.title("Kosmorph v0.1.0 — Backend Ready")
    root.geometry("680x440")

    header = tk.Label(root, text="Kosmorph Engine v0.1.0", font=("Segoe UI", 16, "bold"), pady=12)
    header.pack()

    sub = tk.Label(
        root,
        text=f"Loaded {len(registry.all_actions())} backend actions. Full UI upgrade scheduled for Phase 5.",
        font=("Segoe UI", 10),
    )
    sub.pack(pady=(0, 10))

    listbox = tk.Listbox(root, font=("Consolas", 10), width=82, height=18)
    listbox.pack(padx=16, pady=8, fill="both", expand=True)

    for spec in registry.all_actions():
        listbox.insert(tk.END, f"[{spec.category}] {spec.id} — {spec.name}")

    root.mainloop()
