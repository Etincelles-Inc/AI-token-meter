"""Read-only desktop appearance detection; never changes OS preferences."""
import os

def windows_dark():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
                try:
                    value, kind = winreg.QueryValueEx(key, name)
                    if kind == winreg.REG_DWORD and value in (0, 1):
                        return value == 0
                except OSError:
                    pass
    except OSError:
        pass
    return False

def linux_preference(portal=None, gnome="", gtk_name="", gtk_dark=False):
    if portal in (1, 2):
        return portal == 1
    if gnome in ("prefer-dark", "prefer-light"):
        return gnome == "prefer-dark"
    return bool(gtk_dark or "dark" in gtk_name.lower())

class LinuxDesktop:
    def __init__(self, gtk_settings=None, pump=False):
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib
        self.GLib, self.gtk, self.pump = GLib, gtk_settings, pump
        self.portal_value = None
        self.gnome = None
        source = Gio.SettingsSchemaSource.get_default()
        schema = source.lookup("org.gnome.desktop.interface", True) if source else None
        if schema and schema.has_key("color-scheme"):
            self.gnome = Gio.Settings.new("org.gnome.desktop.interface")
        self.portal = None
        try:
            self.portal = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION,
                Gio.DBusProxyFlags.DO_NOT_AUTO_START, None, "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop", "org.freedesktop.portal.Settings", None)
            if self.portal.get_name_owner():
                for method in ("ReadOne", "Read"):
                    try:
                        value = self.portal.call_sync(method,
                            GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
                            Gio.DBusCallFlags.NONE, 250, None)
                        self.portal_value = self.unwrap(value)
                        break
                    except GLib.Error:
                        continue
                self.portal.connect("g-signal", self._changed)
        except GLib.Error:
            self.portal = None

    def unwrap(self, value):
        while isinstance(value, self.GLib.Variant) or isinstance(value, (tuple, list)):
            value = value.unpack() if isinstance(value, self.GLib.Variant) else value[0]
        return value

    def _changed(self, _proxy, _sender, name, parameters):
        if name == "SettingChanged":
            namespace, key, value = parameters.unpack()
            if (namespace, key) == ("org.freedesktop.appearance", "color-scheme"):
                self.portal_value = self.unwrap(value)

    def __call__(self):
        if self.pump:
            context = self.GLib.MainContext.default()
            for _ in range(8):
                if not context.pending():
                    break
                context.iteration(False)
        gnome = self.gnome.get_string("color-scheme") if self.gnome else ""
        gtk_name, gtk_dark = "", False
        if self.gtk:
            gtk_name = self.gtk.get_property("gtk-theme-name") or ""
            gtk_dark = bool(self.gtk.get_property("gtk-application-prefer-dark-theme"))
        return linux_preference(self.portal_value, gnome, gtk_name, gtk_dark)

def desktop_reader(gtk_settings=None):
    if os.name == "nt":
        return windows_dark
    try:
        return LinuxDesktop(gtk_settings, pump=gtk_settings is None)
    except (ImportError, ValueError, RuntimeError):
        return lambda: False

def resolved_mode(preference, reader):
    if preference == "system":
        return "dark" if reader() else "light"
    if preference not in ("light", "dark"):
        raise ValueError("Appearance must be system, light or dark.")
    return preference
