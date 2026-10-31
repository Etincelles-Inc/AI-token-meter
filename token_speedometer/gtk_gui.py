"""GTK 3 frontend for Linux systems that supply PyGObject instead of Tk."""
import math
import time
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf
import cairo
from .idle_display import IdleDisplay
from .config import save_config, validate_config
from .theme import WHITE, PANEL, MUTED, INK, GREEN, GOLD, TRACK, BORDER, READ_INK, WRITE_INK, RADIUS, asset
from .gui import number, limit, age
from .install import NAME, install, uninstall, set_startup, shortcut_paths

def run(controller, proxy):
    window = Gtk.Window(title=NAME)
    window.set_resizable(False)
    window.set_keep_above(bool(controller.get_config()["always_on_top"]))
    window.connect("destroy", lambda *_: Gtk.main_quit())
    window.set_decorated(False)
    window.set_app_paintable(True)
    visual = window.get_screen().get_rgba_visual()
    if visual:
        window.set_visual(visual)
    window.set_icon_from_file(str(asset("etincelles-128.png")))
    window.get_style_context().add_class("etincelles-bubble")
    css = Gtk.CssProvider()
    css.load_from_data(("""
        window.etincelles-bubble { background: transparent; color: %s; }
        .etincelles-bubble box, .etincelles-bubble eventbox { background: transparent; }
        .etincelles-bubble label { color: %s; }
        .etincelles-bubble .muted { color: %s; font-size: 11px; }
        .etincelles-bubble button { background: %s; color: %s; border: none;
            border-radius: 17px; box-shadow: none; text-shadow: none; padding: 7px 14px; }
        .etincelles-bubble button:hover { background: %s; }
        .etincelles-bubble .chrome { background: transparent; color: %s;
            min-width: 22px; min-height: 22px; padding: 3px; }
        .etincelles-bubble .brand-title { font-size: 15px; font-weight: bold; }
        .etincelles-bubble .brand-caption { color: %s; font-size: 9px; }
        menu { background: %s; color: %s; }
        menuitem label { color: %s; }
    """ % (INK, INK, MUTED, PANEL, INK, BORDER, MUTED, MUTED, WHITE, INK, INK)).encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    def css_class(widget, name):
        widget.get_style_context().add_class(name)
        return widget
    def rounded(ctx, width, height):
        radius = min(RADIUS, width/2, height/2)
        ctx.new_sub_path()
        for x, y, start in [(width-radius,radius,-math.pi/2),(width-radius,height-radius,0),
                            (radius,height-radius,math.pi/2),(radius,radius,math.pi)]:
            ctx.arc(x,y,radius,start,start+math.pi/2)
        ctx.close_path()
    def background(_widget, ctx):
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0,0,0,0)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)
        color(ctx, WHITE)
        rounded(ctx,window.get_allocated_width(),window.get_allocated_height())
        ctx.fill()
        return False
    window.connect("draw", background)
    last_shape = None
    def shape(*_):
        nonlocal last_shape
        width,height = window.get_allocated_width(),window.get_allocated_height()
        if (width,height) == last_shape or not window.get_window():
            return False
        last_shape = width,height
        region = cairo.Region()
        radius = min(RADIUS, width//2, height//2)
        for y in range(height):
            dy = max(0, radius-y-0.5, y-(height-radius)+0.5)
            inset = math.ceil(radius-math.sqrt(max(0,radius*radius-dy*dy))) if dy else 0
            region.union(cairo.RectangleInt(inset,y,max(1,width-2*inset),1))
        window.get_window().shape_combine_region(region,0,0)
        return False
    window.connect("size-allocate", shape)
    window.connect("realize", shape)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_border_width(24)
    window.add(box)
    header = Gtk.Box(spacing=10)
    drag_area = Gtk.EventBox()
    drag_area.set_visible_window(False)
    drag_area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
    brand = Gtk.Box(spacing=10)
    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(asset("etincelles-64.png")),32,32,True)
    brand.pack_start(Gtk.Image.new_from_pixbuf(pixbuf),False,False,0)
    titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=2)
    titles.pack_start(css_class(Gtk.Label(label=NAME,xalign=0),"brand-title"),False,False,0)
    titles.pack_start(css_class(Gtk.Label(label="READ / WRITE SPEEDS",xalign=0),"brand-caption"),False,False,0)
    brand.pack_start(titles,False,False,0)
    drag_area.add(brand)
    def begin_drag(_widget, event):
        if event.button == 1:
            window.begin_move_drag(1,int(event.x_root),int(event.y_root),event.time)
            return True
        return False
    drag_area.connect("button-press-event",begin_drag)
    header.pack_start(drag_area,True,True,0)
    menu_button = css_class(Gtk.MenuButton(label="\\u22ef"),"chrome")
    menu_button.set_label("\u22ef")
    menu_button.set_tooltip_text("Options")
    header.pack_start(menu_button,False,False,0)
    minimize = css_class(Gtk.Button(label="\u2212"),"chrome")
    minimize.set_tooltip_text("Minimize")
    minimize.connect("clicked",lambda *_:window.iconify())
    header.pack_start(minimize,False,False,0)
    close = css_class(Gtk.Button(label="\u00d7"),"chrome")
    close.set_tooltip_text("Close")
    close.connect("clicked",lambda *_:window.destroy())
    header.pack_start(close,False,False,0)
    box.pack_start(header,False,False,0)
    menu = Gtk.Menu()
    menu_button.set_popup(menu)
    info = Gtk.Label(label="Connecting to engine...", xalign=0)
    css_class(info,"muted")
    info.set_max_width_chars(65)
    info.set_ellipsize(3)
    box.pack_start(info, False, False, 0)
    area = Gtk.DrawingArea()
    area.set_size_request(490, 220)
    box.pack_start(area, False, False, 0)
    status = Gtk.Label(xalign=0)
    css_class(status,"muted")
    status.set_line_wrap(True)
    status.set_max_width_chars(65)
    box.pack_start(status, False, False, 0)
    limits = {"read": 5000, "write": 100}
    idle_display = IdleDisplay()
    current = controller.snapshot()
    def color(ctx, hex_color):
        ctx.set_source_rgb(*[int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)])
    def text(ctx, x, y, value, size=12, tint=MUTED, bold=False):
        color(ctx, tint)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(size)
        ext = ctx.text_extents(value)
        ctx.move_to(x - ext.width / 2, y)
        ctx.show_text(value)
    def draw(_area, ctx):
        color(ctx, WHITE)
        ctx.paint()
        for key, x, label, tint in [("read", 115, "READ / PREFILL", GREEN), ("write", 365, "WRITE / DECODE", GOLD)]:
            item = current[key]
            rate = item.get("rate")
            limits[key] = limit(rate, limits[key])
            maximum = limits[key]
            number_color = READ_INK if key == "read" else WRITE_INK
            text(ctx, x, 15, label, 11, number_color, True)
            ctx.set_line_width(12)
            color(ctx, TRACK)
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
            text(ctx, x, 169, number(rate), 30, number_color, True)
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
        current = idle_display.apply(time.monotonic(), controller.snapshot())
        info.set_text((current["engine"] or "Engine") + " / " + (current["model"] or "Automatic model"))
        status.set_text(current.get("message") or f"Active {current.get('active', 0)}   Queued {current.get('queued', 0)}")
        area.queue_draw()
        return True
    GLib.timeout_add(250, refresh)
    window.show_all()
    Gtk.main()
