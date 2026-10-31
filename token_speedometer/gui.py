"""Tk desktop speedometers; all network work stays off the UI thread."""
import math
import time
from . import __version__
from .idle_display import IdleDisplay
from .config import save_config
from .bubble import BubbleWindow
from .appearance import desktop_reader, resolved_mode
from .theme import palette
from .theme import WHITE, PANEL, MUTED, INK, GREEN, GOLD, TRACK, BORDER, READ_INK, WRITE_INK, asset, rounded_points
from .install import NAME, install, uninstall, set_startup, shortcut_paths

BG, TEXT = WHITE, INK
READ, WRITE = GREEN, GOLD

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
    from tkinter import font as tkfont
    reader = desktop_reader()
    theme_mode = resolved_mode(controller.get_config().get("appearance", "system"), reader)
    colors = palette(theme_mode)
    BG, TEXT, INK, PANEL, MUTED, TRACK, BORDER, READ_INK, WRITE_INK, GREEN, GOLD = (
        colors["bg"], colors["text"], colors["text"], colors["panel"], colors["muted"],
        colors["track"], colors["border"], colors["read_text"], colors["write_text"],
        colors["read"], colors["write"])
    READ, WRITE = GREEN, GOLD
    pills = []
    root = tk.Tk()
    root.title(NAME)
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", bool(controller.get_config()["always_on_top"]))
    shell = BubbleWindow(root)
    root.brand_icon = tk.PhotoImage(file=str(asset("etincelles-128.png")))
    root.iconphoto(True, root.brand_icon)
    root.brand_logo = tk.PhotoImage(file=str(asset("etincelles-64.png"))).subsample(2, 2)
    def close_view():
        config = controller.get_config()
        if root.state() == "normal":
            config.update(x=root.winfo_x(), y=root.winfo_y())
            save_config(config)
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", close_view)
    root.bind("<Alt-F4>", lambda _event: close_view())
    frame = tk.Frame(root, bg=BG, padx=24, pady=20)
    frame.pack()
    header = tk.Frame(frame, bg=BG)
    header.pack(fill="x")
    logo = tk.Label(header, image=root.brand_logo, bg=BG)
    logo.pack(side="left", padx=(0, 10))
    title_box = tk.Frame(header, bg=BG)
    title_box.pack(side="left")
    title = tk.Label(title_box, text=NAME, bg=BG, fg=TEXT, font=("Segoe UI", 13, "bold"))
    title.pack(anchor="w")
    subtitle = tk.Label(title_box, text="READ / WRITE SPEEDS", bg=BG, fg=MUTED, font=("Segoe UI", 8))
    subtitle.pack(anchor="w")
    for item in (header, logo, title_box, title, subtitle):
        shell.bind_drag(item)
    def header_button(text, action):
        result = tk.Button(header, text=text, command=action, bg=BG, fg=MUTED,
                           activebackground=PANEL, activeforeground=INK, relief="flat",
                           borderwidth=0, padx=7, pady=2, font=("Segoe UI", 15),
                           cursor="hand2", takefocus=True)
        result.pack(side="right", padx=(3, 0))
        return result
    header_button("\u00d7", close_view)
    header_button("\u2212", shell.minimize)
    menu_button = tk.Menubutton(header, text="\u22ef", bg=BG, fg=MUTED, relief="flat",
                               activebackground=PANEL, activeforeground=INK, padx=7, pady=2,
                               font=("Segoe UI", 16), cursor="hand2", takefocus=True)
    menu_button.pack(side="right", padx=(3, 0))
    menu = tk.Menu(menu_button, tearoff=False, bg=BG, fg=INK, activebackground=PANEL,
                   activeforeground=INK, borderwidth=0, selectcolor=TEXT)
    menu_button["menu"] = menu
    def pill_button(parent, text, command):
        font = tkfont.Font(family="Segoe UI", size=10)
        width = font.measure(text) + 28
        button = tk.Canvas(parent, width=width, height=34, bg=BG, highlightthickness=0,
                           cursor="hand2", takefocus=True)
        shape = button.create_polygon(rounded_points(1, 1, width-2, 32, 16), smooth=True,
                                       splinesteps=24, fill=PANEL, outline=PANEL)
        text_item = button.create_text(width/2, 17, text=text, fill=INK, font=font)
        pills.append((button, shape, text_item))
        def invoke(_event=None):
            button.focus_set()
            command()
        button.bind("<Button-1>", invoke)
        button.bind("<Return>", invoke)
        button.bind("<space>", invoke)
        button.bind("<Enter>", lambda _event: button.itemconfigure(shape, fill=BORDER))
        button.bind("<Leave>", lambda _event: button.itemconfigure(shape, fill=PANEL))
        button.bind("<FocusIn>", lambda _event: button.itemconfigure(shape, outline=GREEN))
        button.bind("<FocusOut>", lambda _event: button.itemconfigure(shape, outline=PANEL))
        return button
    engine = tk.StringVar(value="Connecting to engine...")
    model = tk.StringVar()
    tk.Label(frame, textvariable=engine, bg=BG, fg=MUTED, anchor="w", font=("Segoe UI", 9)).pack(fill="x", pady=(15, 0))
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
    pill_button(controls, "Copy capture URL", copied).pack(side="right")
    combo_style = ttk.Style(root)
    combo_style.theme_use("clam")
    def style_inputs():
        combo_style.configure("Meter.TCombobox", background=PANEL, fieldbackground=PANEL,
            foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        combo_style.map("Meter.TCombobox", fieldbackground=[("readonly", PANEL)],
                        foreground=[("readonly", TEXT)], selectbackground=[("readonly", BORDER)],
                        selectforeground=[("readonly", TEXT)])
        root.option_add("*TCombobox*Listbox.background", PANEL)
        root.option_add("*TCombobox*Listbox.foreground", TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", BORDER)
        root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    style_inputs()
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
                entry = ttk.Combobox(dialog, textvariable=variables[key], values=["auto", "vllm", "llamacpp", "ollama", "native"], state="readonly", width=54, style="Meter.TCombobox")
            else:
                entry = tk.Entry(dialog, textvariable=variables[key], width=57, bg=PANEL, fg=TEXT,
                                 insertbackground=TEXT, selectbackground=BORDER, selectforeground=TEXT)
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
        tk.Button(dialog, text="Save", command=apply, padx=20, bg=PANEL, fg=TEXT,
                  activebackground=BORDER, activeforeground=TEXT).grid(row=11, column=0, pady=(0, 16), sticky="e", padx=16)
    pill_button(controls, "Engine / model", settings).pack(side="left")
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
        controller.update_view_settings(always_on_top=above.get())
    menu.add_checkbutton(label="Always on top", variable=above, command=lambda: guarded(change_above))
    appearance_choice = tk.StringVar(value=controller.get_config().get("appearance", "system"))
    appearance_menu = tk.Menu(menu, tearoff=False, bg=BG, fg=TEXT,
                               activebackground=PANEL, activeforeground=TEXT, selectcolor=TEXT)
    def change_appearance():
        choice = appearance_choice.get()
        save_config({**controller.get_config(), "appearance": choice})
        controller.update_view_settings(appearance=choice)
        apply_appearance()
    for label, choice in [("Follow desktop", "system"), ("Light", "light"), ("Dark (neon)", "dark")]:
        appearance_menu.add_radiobutton(label=label, variable=appearance_choice, value=choice, command=change_appearance)
    menu.add_cascade(label="Appearance", menu=appearance_menu)
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
    menu.add_command(label="Quit", command=close_view)
    idle_display = IdleDisplay()
    limits = {"read": 5000, "write": 100}
    def draw_dial(x, label, item, color, key):
        rate = item.get("rate")
        limits[key] = limit(rate, limits[key])
        maximum = limits[key]
        cx, cy, radius = x + 115, 112, 84
        canvas.create_text(cx, 10, text=label.upper(), fill=READ_INK if key == "read" else WRITE_INK, font=("Segoe UI", 10, "bold"))
        canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius, start=0, extent=180,
                          style="arc", outline=TRACK, width=12)
        if rate is not None:
            fraction = min(1, rate / maximum)
            if theme_mode == "dark":
                glow = colors["read_glow"] if key == "read" else colors["write_glow"]
                canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                    start=180 - 180*fraction, extent=180*fraction, style="arc", outline=glow, width=20)
            canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius, start=180 - 180 * fraction,
                              extent=180 * fraction, style="arc", outline=color, width=12)
            angle = math.pi * (1 - fraction)
            if theme_mode == "dark":
                canvas.create_line(cx, cy, cx + math.cos(angle)*66, cy-math.sin(angle)*66, fill=glow, width=7)
            canvas.create_line(cx, cy, cx + math.cos(angle) * 66, cy - math.sin(angle) * 66, fill=color, width=3)
        canvas.create_oval(cx-5, cy-5, cx+5, cy+5, fill=color if rate is not None else MUTED, outline="")
        for value, angle in [(0, math.pi), (maximum / 2, math.pi / 2), (maximum, 0)]:
            tx, ty = cx + math.cos(angle) * 103, cy - math.sin(angle) * 58
            canvas.create_text(tx, ty + (12 if angle != math.pi / 2 else 0), text=f"{value/1000:g}k" if value >= 1000 else f"{value:g}",
                               fill=MUTED, font=("Segoe UI", 8))
        canvas.create_text(cx, 157, text=number(rate), fill=READ_INK if key == "read" else WRITE_INK, font=("Consolas", 25, "bold"))
        canvas.create_text(cx, 184, text="tok/s", fill=MUTED, font=("Segoe UI", 10))
        canvas.create_text(cx, 207, text=age(item), fill=MUTED, font=("Segoe UI", 8), width=235)
    last_dials = None
    def paint_dials(value):
        nonlocal last_dials
        dials = tuple((value[key].get("rate"), age(value[key])) for key in ("read", "write"))
        if dials != last_dials:
            canvas.delete("all")
            draw_dial(0, "Read / prefill", value["read"], READ, "read")
            draw_dial(250, "Write / decode", value["write"], WRITE, "write")
            last_dials = dials
    def apply_appearance():
        nonlocal theme_mode, colors, BG, TEXT, INK, PANEL, MUTED, TRACK, BORDER
        nonlocal READ_INK, WRITE_INK, GREEN, GOLD, READ, WRITE, last_dials
        mode = resolved_mode(appearance_choice.get(), reader)
        if mode == theme_mode:
            return
        previous, colors = colors, palette(mode)
        theme_mode = mode
        replacements = {previous[key].lower(): colors[key] for key in
                        ("bg", "text", "muted", "panel", "track", "border")}
        def recolor(widget):
            for option in ("background", "foreground", "activebackground", "activeforeground",
                           "insertbackground", "selectbackground", "selectforeground", "selectcolor"):
                try:
                    current_color = str(widget.cget(option)).lower()
                    if current_color in replacements:
                        widget.configure(**{option: replacements[current_color]})
                except tk.TclError:
                    pass
            for child in widget.winfo_children():
                recolor(child)
        recolor(root)
        BG, TEXT, INK, PANEL, MUTED, TRACK, BORDER, READ_INK, WRITE_INK, GREEN, GOLD = (
            colors["bg"], colors["text"], colors["text"], colors["panel"], colors["muted"],
            colors["track"], colors["border"], colors["read_text"], colors["write_text"],
            colors["read"], colors["write"])
        READ, WRITE = GREEN, GOLD
        for button, shape, text_item in pills:
            button.itemconfigure(shape, fill=PANEL, outline=GREEN if button.focus_get() is button else PANEL)
            button.itemconfigure(text_item, fill=INK)
        style_inputs()
        last_dials = None
        paint_dials(idle_display.apply(time.monotonic(), controller.snapshot()))
    def poll_appearance():
        apply_appearance()
        root.after(2000, poll_appearance)
    def set_text(variable, text):
        if variable.get() != text:
            variable.set(text)
    def refresh():
        nonlocal last_dials
        value = idle_display.apply(time.monotonic(), controller.snapshot())
        paint_dials(value)
        set_text(engine, (value["engine"] or "Engine") + ("  /  Connected" if value["online"] else "  /  Waiting"))
        set_text(model, value["model"] or "Choose a model or use automatic selection")
        text = value.get("message") or f"Active {value.get('active', 0)}   Queued {value.get('queued', 0)}"
        if value.get("cache") is not None:
            text += f"   KV cache {value['cache'] * 100:.1f}%"
        set_text(status, text)
        root.after(250, refresh)
    refresh()
    root.after(2000, poll_appearance)
    shell.show(controller.get_config())
    root.mainloop()
