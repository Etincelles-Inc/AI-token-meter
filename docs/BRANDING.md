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
