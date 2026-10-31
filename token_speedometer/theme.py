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
