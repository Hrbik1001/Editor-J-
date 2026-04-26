[ui_utils.py](https://github.com/user-attachments/files/27099981/ui_utils.py)
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox


def confirm_delete(name: str) -> bool:
    """
    Potvrzení mazání položky
    """
    return messagebox.askyesno(
        "Smazat",
        f"Opravdu chceš smazat:\n{name} ?",
        icon="warning",
    )


def info(text: str):
    """
    Informační hláška
    """
    messagebox.showinfo("Informace", text)


def error(text: str):
    """
    Chybová hláška
    """
    messagebox.showerror("Chyba", text)


def center_window(win: tk.Toplevel | tk.Tk):
    """
    Vycentruje okno na obrazovku
    """
    win.update_idletasks()

    width = win.winfo_width()
    height = win.winfo_height()

    screen_w = win.winfo_screenwidth()
    screen_h = win.winfo_screenheight()

    x = int((screen_w / 2) - (width / 2))
    y = int((screen_h / 2) - (height / 2))

    win.geometry(f"{width}x{height}+{x}+{y}")


def ask_string(title: str, prompt: str) -> str | None:
    """
    Jednoduchý dialog pro zadání textu
    """
    root = tk.Toplevel()
    root.title(title)
    root.resizable(False, False)

    value = {"text": None}

    tk.Label(root, text=prompt, padx=10, pady=10).pack()

    entry = tk.Entry(root, width=40)
    entry.pack(padx=10)
    entry.focus()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    def ok():
        value["text"] = entry.get().strip()
        root.destroy()

    def cancel():
        root.destroy()

    tk.Button(btn_frame, text="OK", width=10, command=ok).pack(side="left", padx=5)
    tk.Button(btn_frame, text="Zrušit", width=10, command=cancel).pack(side="left", padx=5)

    root.grab_set()
    root.wait_window()

    return value["text"]
