"""Etincelles palette sampled from the supplied official logo; pixels are unchanged."""
from pathlib import Path

GREEN = "#95C06D"
GOLD = "#E1D753"
WHITE = "#FFFFFE"
INK = "#25371F"
MUTED = "#62745A"
PANEL = "#F0F5E8"
TRACK = "#E5ECD9"
BORDER = "#D6E3C7"
READ_INK = "#496C2F"
WRITE_INK = "#756D18"
RADIUS = 32

def asset(name):
    return Path(__file__).resolve().parent / "assets" / name

def rounded_points(x, y, width, height, radius):
    r = min(radius, width / 2, height / 2)
    return (x+r,y, x+width-r,y, x+width,y, x+width,y+r,
            x+width,y+height-r, x+width,y+height, x+width-r,y+height,
            x+r,y+height, x,y+height, x,y+height-r, x,y+r, x,y)


LIGHT = {"bg": WHITE, "text": INK, "muted": MUTED, "panel": PANEL,
         "track": TRACK, "border": BORDER, "read": GREEN, "write": GOLD,
         "read_text": READ_INK, "write_text": WRITE_INK,
         "read_glow": TRACK, "write_glow": TRACK}
DARK = {"bg": "#0B140F", "text": "#F4FFE9", "muted": "#AFBDA7", "panel": "#18271D",
        "track": "#26392B", "border": "#344E39", "read": "#A8FF4F", "write": "#FFE44D",
        "read_text": "#A8FF4F", "write_text": "#FFE44D",
        "read_glow": "#28491E", "write_glow": "#4C4215"}

def palette(mode):
    return dict(DARK if mode == "dark" else LIGHT)
