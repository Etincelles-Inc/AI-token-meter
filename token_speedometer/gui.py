"""Tk desktop speedometers; all network work stays off the UI thread."""
import math
import time
from . import __version__
from .idle_display import IdleDisplay
from .config import save_config
from .install import NAME, install, uninstall, set_startup, shortcut_paths

BG, PANEL, MUTED, TEXT = "#101923", "#162330", "#8ea3b5", "#edf5fa"
READ, WRITE = "#73ccff", "#a5e443"

def number(value):
    return "--" if value is None else f"{value:,.1f}"

def limit(value, current):
    if value is None or value <= current:
        return current
    power = 10 ** math.floor(math.log10(value))
    return next((x * power for x in (1, 2, 5, 10) if x * power >= value), 10 * power)

def age(item):
    stamp = item.get("updated_at")
    if stamp is None:
        return item.get("kind", "Unavailable")
    elapsed = max(0, time.monotonic() - stamp)
    return item["kind"] + (f" / {elapsed:.0f}s ago" if elapsed >= 2 else " / just measured")

def run(controller, proxy):
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        from .gtk_gui import run as gtk_run
        return gtk_run(controller, proxy)
    root = tk.Tk()
    root.title(NAME)
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", bool(controller.get_config()["always_on_top"]))
    frame = tk.Frame(root, bg=BG, padx=18, pady=14)
    frame.pack()
    header = tk.Frame(frame, bg=BG)
    header.pack(fill="x")
    tk.Label(header, text=NAME, bg=BG, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(side="left")
    menu_button = tk.Menubutton(header, text="Options", bg=PANEL, fg=TEXT, relief="flat",
                               activebackground=PANEL, activeforeground=TEXT, padx=9, pady=4)
    menu_button.pack(side="right")
    menu = tk.Menu(menu_button, tearoff=False)
    menu_button["menu"] = menu
    engine = tk.StringVar(value="Connecting to engine...")
    model = tk.StringVar()
    tk.Label(frame, textvariable=engine, bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 10)).pack(fill="x", pady=(10, 0))
    tk.Label(frame, textvariable=model, bg=BG, fg=TEXT, anchor="w", wraplength=475, font=("Segoe UI", 10)).pack(fill="x")
    canvas = tk.Canvas(frame, width=490, height=218, bg=BG, highlightthickness=0)
    canvas.pack(pady=(8, 0))
    status = tk.StringVar()
    tk.Label(frame, textvariable=status, bg=BG, fg=MUTED, anchor="w", wraplength=490,
             justify="left", font=("Segoe UI", 9)).pack(fill="x", pady=(2, 10))
    controls = tk.Frame(frame, bg=BG)
    controls.pack(fill="x")
    def copied():
        root.clipboard_clear()
        root.clipboard_append(f"http://127.0.0.1:{proxy.port}")
        status.set("Capture URL copied. Use it in place of your engine's base URL.")
    tk.Button(controls, text="Copy capture URL", command=copied, bg=PANEL, fg=TEXT, relief="flat", padx=10, pady=5).pack(side="right")
    def settings():
        dialog = tk.Toplevel(root)
        dialog.title("Engine / model")
        dialog.transient(root)
        dialog.configure(bg=BG)
        dialog.grab_set()
        config = controller.get_config()
        variables = {}
        for index, (key, title) in enumerate([("backend", "Engine"), ("upstream", "Engine base URL"),
                                              ("model", "Model (blank = automatic)"), ("proxy_port", "Local capture port"),
                                              ("auth_env", "API key environment variable (optional)")]):
            tk.Label(dialog, text=title, bg=BG, fg=TEXT).grid(row=index * 2, column=0, sticky="w", padx=16, pady=(10, 2))
            variables[key] = tk.StringVar(value=str(config[key]))
            if key == "backend":
                entry = ttk.Combobox(dialog, textvariable=variables[key], values=["auto", "vllm", "llamacpp", "ollama", "native"], state="readonly", width=54)
            else:
                entry = tk.Entry(dialog, textvariable=variables[key], width=57)
            entry.grid(row=index * 2 + 1, column=0, padx=16, sticky="ew")
        note = "vLLM / llama.cpp: poll engine metrics.\nOllama / native: send application requests through the capture URL.\nCapture port changes take effect after reopening this widget."
        tk.Label(dialog, text=note, bg=BG, fg=MUTED, justify="left").grid(row=10, column=0, padx=16, pady=12, sticky="w")
        def apply():
            try:
                from .config import validate_config
                value = validate_config({**config, **{k: v.get().strip() for k, v in variables.items()}})
                if value["upstream"] in (f"http://127.0.0.1:{proxy.port}", f"http://localhost:{proxy.port}"):
                    raise ValueError("The upstream must be the engine, not this widget's capture port.")
                save_config(value)
                controller.configure(value)
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror(NAME, str(exc), parent=dialog)
        tk.Button(dialog, text="Save", command=apply, padx=20).grid(row=11, column=0, pady=(0, 16), sticky="e", padx=16)
    tk.Button(controls, text="Engine / model", command=settings, bg=PANEL, fg=TEXT, relief="flat", padx=10, pady=5).pack(side="left")
    def guarded(action):
        try:
            action()
        except Exception as exc:
            messagebox.showerror(NAME, str(exc), parent=root)
    above = tk.BooleanVar(value=bool(controller.get_config()["always_on_top"]))
    def change_above():
        config = {**controller.get_config(), "always_on_top": above.get()}
        save_config(config)
        root.attributes("-topmost", above.get())
        controller.configure(config)
    menu.add_checkbutton(label="Always on top", variable=above, command=lambda: guarded(change_above))
    startup = tk.BooleanVar(value=shortcut_paths()[-1].exists())
    menu.add_checkbutton(label="Start at login", variable=startup, command=lambda: guarded(lambda: set_startup(startup.get())))
    menu.add_command(label="Install for this user", command=lambda: guarded(lambda: messagebox.showinfo(NAME, "Installed in " + install(), parent=root)))
    def remove():
        if messagebox.askyesno("Uninstall " + NAME, "Remove this widget, its settings and its shortcuts?", parent=root):
            guarded(lambda: (uninstall(), root.destroy()))
    menu.add_command(label="Uninstall", command=remove)
    menu.add_separator()
    menu.add_command(label="About readings", command=lambda: messagebox.showinfo(NAME,
        NAME + " " + __version__ + "\n\nRead = native prompt processing speed.\nWrite = native generation speed.\n"
        "Polling time is never the speed denominator.\nHeld readings show their age. Multiple requests are time weighted.\n"
        "Ollama reports timing at completion; it cannot give a continuous native live rate.\n"
        "This tool does not log prompts, responses or API keys.", parent=root))
    menu.add_command(label="Quit", command=root.destroy)
    idle_display = IdleDisplay()
    limits = {"read": 5000, "write": 100}
    def draw_dial(x, label, item, color, key):
        rate = item.get("rate")
        limits[key] = limit(rate, limits[key])
        maximum = limits[key]
        cx, cy, radius = x + 115, 112, 84
        canvas.create_text(cx, 10, text=label.upper(), fill=color, font=("Segoe UI", 10, "bold"))
        canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius, start=0, extent=180,
                          style="arc", outline="#2c4050", width=12)
        if rate is not None:
            fraction = min(1, rate / maximum)
            canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius, start=180 - 180 * fraction,
                              extent=180 * fraction, style="arc", outline=color, width=12)
            angle = math.pi * (1 - fraction)
            canvas.create_line(cx, cy, cx + math.cos(angle) * 66, cy - math.sin(angle) * 66, fill=color, width=3)
        canvas.create_oval(cx-5, cy-5, cx+5, cy+5, fill=color if rate is not None else MUTED, outline="")
        for value, angle in [(0, math.pi), (maximum / 2, math.pi / 2), (maximum, 0)]:
            tx, ty = cx + math.cos(angle) * 103, cy - math.sin(angle) * 58
            canvas.create_text(tx, ty + (12 if angle != math.pi / 2 else 0), text=f"{value/1000:g}k" if value >= 1000 else f"{value:g}",
                               fill=MUTED, font=("Segoe UI", 8))
        canvas.create_text(cx, 157, text=number(rate), fill=color, font=("Consolas", 25, "bold"))
        canvas.create_text(cx, 184, text="tok/s", fill=MUTED, font=("Segoe UI", 10))
        canvas.create_text(cx, 207, text=age(item), fill=MUTED, font=("Segoe UI", 8), width=235)
    def refresh():
        value = idle_display.apply(time.monotonic(), controller.snapshot())
        canvas.delete("all")
        draw_dial(0, "Read / prefill", value["read"], READ, "read")
        draw_dial(250, "Write / decode", value["write"], WRITE, "write")
        engine.set((value["engine"] or "Engine") + ("  /  Connected" if value["online"] else "  /  Waiting"))
        model.set(value["model"] or "Choose a model or use automatic selection")
        text = value.get("message") or f"Active {value.get('active', 0)}   Queued {value.get('queued', 0)}"
        if value.get("cache") is not None:
            text += f"   KV cache {value['cache'] * 100:.1f}%"
        status.set(text)
        root.after(250, refresh)
    refresh()
    root.mainloop()
