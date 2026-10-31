# Official Etincelles bubble - 0.2.0

The palette comes from the supplied official logo PNGs, not a reconstructed logo.

| Role | Color |
| --- | --- |
| Brand green / Read needle | #95C06D |
| Brand gold / Write needle | #E1D753 |
| Warm white bubble | #FFFFFE |
| Main text | #25371F |
| Read numbers | #496C2F |
| Write numbers | #756D18 |
| Muted text | #62745A |
| Soft controls | #F0F5E8 |

The 32, 64, 128, 256, 512 and 1024 pixel PNGs are preserved byte-for-byte. The Windows ICO contains the supplied 32-256 pixel PNG images unchanged. Display scaling is performed by the GUI toolkit.

The main widget is one rounded bubble with a draggable header, logo and custom Options, Minimize and Close controls. It retains the same timing adapters and five-second idle policy. The settings dialog and operating-system confirmation dialogs remain separate windows.

The Windows frontend uses Tk and a native rounded window region. The Linux frontend uses GTK 3 with an RGBA visual when available and a rounded window shape. Window shaping is maintained when moving or restoring the widget.


## Automatic appearance - 0.3.0

Follow desktop is the default. Windows reads AppsUseLightTheme, falling back to SystemUsesLightTheme only when the app preference is absent. In Windows custom color mode the app preference wins. Linux uses the standardized appearance portal, then GNOME color-scheme and GTK theme preferences. Desktop values are read-only. A two-second appearance check updates an open widget without restarting it.

Dark mode keeps the original logo and uses neon green #A8FF4F and neon gold #FFE44D on a #0B140F background. The meter arcs and needles have a subtle static glow. Light mode retains the 0.2.0 palette. Options > Appearance provides Follow desktop, Light and Dark (neon) choices, saved per user. Changing appearance does not clear timing data or restart the engine connection.

Settings fields, menus and open app dialogs recolor with the widget. Operating-system prompts keep their native appearance.

Sources: [Windows theme preference values](https://learn.microsoft.com/en-us/windows/apps/develop/settings/settings-common), [desktop appearance portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Settings.html), [GTK settings](https://docs.gtk.org/gtk3/class.Settings.html).
