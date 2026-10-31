"""GTK 3 frontend for Linux systems that supply PyGObject instead of Tk."""
import math
import time
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk
import cairo
from .idle_display import IdleDisplay
from .config import save_config, validate_config
from .gui import number, limit, age
from .install import NAME, install, uninstall, set_startup, shortcut_paths

def run(controller, proxy):
    window = Gtk.Window(title=NAME)
    window.set_resizable(False)
    window.set_keep_above(bool(controller.get_config()["always_on_top"]))
    window.connect("destroy", lambda *_: Gtk.main_quit())
    css = Gtk.CssProvider()
    css.load_from_data(b"window,box {background:#101923;color:#edf5fa;} button {background:#162330;color:#edf5fa;} label {color:#edf5fa;}")
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_border_width(16)
    window.add(box)
    header = Gtk.HeaderBar(title=NAME, show_close_button=True)
    window.set_titlebar(header)
    menu_button = Gtk.MenuButton(label="Options")
    header.pack_end(menu_button)
    menu = Gtk.Menu()
    menu_button.set_popup(menu)
    info = Gtk.Label(label="Connecting to engine...", xalign=0)
    info.set_max_width_chars(65)
    info.set_ellipsize(3)
    box.pack_start(info, False, False, 0)
    area = Gtk.DrawingArea()
    area.set_size_request(490, 220)
    box.pack_start(area, False, False, 0)
    status = Gtk.Label(xalign=0)
    status.set_line_wrap(True)
    status.set_max_width_chars(65)
    box.pack_start(status, False, False, 0)
    limits = {"read": 5000, "write": 100}
    idle_display = IdleDisplay()
    current = controller.snapshot()
    def color(ctx, hex_color):
        ctx.set_source_rgb(*[int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)])
    def text(ctx, x, y, value, size=12, tint="#8ea3b5", bold=False):
        color(ctx, tint)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(size)
        ext = ctx.text_extents(value)
        ctx.move_to(x - ext.width / 2, y)
        ctx.show_text(value)
    def draw(_area, ctx):
        color(ctx, "#101923")
        ctx.paint()
        for key, x, label, tint in [("read", 115, "READ / PREFILL", "#73ccff"), ("write", 365, "WRITE / DECODE", "#a5e443")]:
            item = current[key]
            rate = item.get("rate")
            limits[key] = limit(rate, limits[key])
            maximum = limits[key]
            text(ctx, x, 15, label, 11, tint, True)
            ctx.set_line_width(12)
            color(ctx, "#2c4050")
            ctx.new_path()
            ctx.arc(x, 112, 84, math.pi, 2 * math.pi)
            ctx.stroke()
            if rate is not None:
                fraction = min(1, rate / maximum)
                color(ctx, tint)
                ctx.new_path()
                ctx.arc(x, 112, 84, math.pi, math.pi + fraction * math.pi)
                ctx.stroke()
                angle = math.pi * (1 - fraction)
                ctx.set_line_width(3)
                ctx.move_to(x, 112)
                ctx.line_to(x + math.cos(angle) * 66, 112 - math.sin(angle) * 66)
                ctx.stroke()
            color(ctx, tint)
            ctx.new_path()
            ctx.arc(x, 112, 5, 0, 2*math.pi)
            ctx.fill()
            text(ctx, x-103, 136, "0", 9)
            text(ctx, x, 35, f"{maximum/2:g}", 9)
            text(ctx, x+103, 136, f"{maximum:g}", 9)
            text(ctx, x, 169, number(rate), 30, tint, True)
            text(ctx, x, 190, "tok/s", 12)
            text(ctx, x, 214, age(item), 9)
        return False
    area.connect("draw", draw)
    def message(content, error=False):
        dialog = Gtk.MessageDialog(transient_for=window, modal=True,
            message_type=Gtk.MessageType.ERROR if error else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK, text=NAME)
        dialog.format_secondary_text(content)
        dialog.run()
        dialog.destroy()
    def guarded(action):
        try:
            action()
        except Exception as exc:
            message(str(exc), True)
    def settings(*_):
        config = controller.get_config()
        dialog = Gtk.Dialog(title="Engine / model", transient_for=window, modal=True)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_border_width(16)
        content.set_spacing(8)
        entries = {}
        for key, label in [("backend", "Engine: auto, vllm, llamacpp, ollama, native"), ("upstream", "Engine base URL"),
                           ("model", "Model (blank = automatic)"), ("proxy_port", "Capture port (restart to change)"),
                           ("auth_env", "API key environment variable (optional)")]:
            content.add(Gtk.Label(label=label, xalign=0))
            entry = Gtk.Entry()
            entry.set_text(str(config[key]))
            entry.set_width_chars(55)
            content.add(entry)
            entries[key] = entry
        dialog.show_all()
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                value = validate_config({**config, **{k: e.get_text().strip() for k, e in entries.items()}})
                if value["upstream"] in (f"http://127.0.0.1:{proxy.port}", f"http://localhost:{proxy.port}"):
                    raise ValueError("Upstream must be the engine, not the capture proxy.")
                save_config(value)
                controller.configure(value)
            except Exception as exc:
                message(str(exc), True)
        dialog.destroy()
    controls = Gtk.Box(spacing=12)
    choose = Gtk.Button(label="Engine / model")
    choose.connect("clicked", settings)
    controls.pack_start(choose, False, False, 0)
    copy = Gtk.Button(label="Copy capture URL")
    copy.connect("clicked", lambda *_: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(f"http://127.0.0.1:{proxy.port}", -1))
    controls.pack_end(copy, False, False, 0)
    box.pack_start(controls, False, False, 0)
    above = Gtk.CheckMenuItem(label="Always on top")
    above.set_active(bool(controller.get_config()["always_on_top"]))
    def change_above(item):
        value = {**controller.get_config(), "always_on_top": item.get_active()}
        save_config(value)
        window.set_keep_above(item.get_active())
        controller.configure(value)
    above.connect("toggled", lambda item: guarded(lambda: change_above(item)))
    menu.append(above)
    startup = Gtk.CheckMenuItem(label="Start at login")
    startup.set_active(shortcut_paths()[-1].exists())
    startup.connect("toggled", lambda item: guarded(lambda: set_startup(item.get_active())))
    menu.append(startup)
    def entry(label, action):
        item = Gtk.MenuItem(label=label)
        item.connect("activate", lambda *_: guarded(action))
        menu.append(item)
    entry("Install for this user", lambda: message("Installed in " + install()))
    def remove():
        dialog = Gtk.MessageDialog(transient_for=window, modal=True, message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL, text="Uninstall " + NAME + "?")
        dialog.format_secondary_text("Remove the widget, its settings and its shortcuts?")
        result = dialog.run()
        dialog.destroy()
        if result == Gtk.ResponseType.OK:
            uninstall()
            window.destroy()
    entry("Uninstall", remove)
    entry("About readings", lambda: message("Read / Write use engine timing, never polling duration.\nHeld readings show their age.\nOllama updates native timing at completion.\nNo prompts, responses or keys are logged."))
    entry("Quit", window.destroy)
    menu.show_all()
    def refresh():
        nonlocal current
        idle_display = IdleDisplay()
    current = controller.snapshot()
        info.set_text((current["engine"] or "Engine") + " / " + (current["model"] or "Automatic model"))
        status.set_text(current.get("message") or f"Active {current.get('active', 0)}   Queued {current.get('queued', 0)}")
        area.queue_draw()
        return True
    GLib.timeout_add(250, refresh)
    window.show_all()
    Gtk.main()
