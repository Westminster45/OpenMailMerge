"""Draw the extension icons: a white envelope on a blue rounded square. Plain Python, no image
library needed.
  extension/images/icon.png      42x42, Extension Manager
  extension/images/icon_16.png   16x16, menu and small toolbar
  extension/images/icon_26.png   26x26, large toolbar

Run: python3 dev/make_icon.py
"""

import struct
import zlib
from pathlib import Path

SIZE = 42  # the design is drawn in a 42x42 space and scaled to each output size
SS = 4  # supersampling per axis, for smooth edges
BLUE = (31, 111, 209)
WHITE = (255, 255, 255)


def in_rounded_square(x, y, r=9.0):
    cx, cy = min(max(x, r), SIZE - r), min(max(y, r), SIZE - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def near_segment(x, y, a, b, w):
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    px, py = x1 + t * dx, y1 + t * dy
    return (x - px) ** 2 + (y - py) ** 2 <= w * w


def colour_at(x, y):
    """(r, g, b, a) of the icon at point (x, y)."""
    if not in_rounded_square(x, y):
        return (0, 0, 0, 0)
    left, right, top, bottom = 8.5, 33.5, 12.5, 29.5
    if left <= x <= right and top <= y <= bottom:
        # envelope flap: a blue V from the top corners to the middle
        mid = ((left + right) / 2, 22.0)
        if near_segment(x, y, (left + 1, top + 1), mid, 1.3) or near_segment(x, y, (right - 1, top + 1), mid, 1.3):
            return BLUE + (255,)
        return WHITE + (255,)
    return BLUE + (255,)


def render(size):
    k = SIZE / size
    rows = []
    for py in range(size):
        row = bytearray([0])  # PNG filter type 0
        for px in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(SS):
                for sx in range(SS):
                    r, g, b, a = colour_at((px + (sx + 0.5) / SS) * k, (py + (sy + 0.5) / SS) * k)
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            n = SS * SS
            alpha = acc[3] / n
            if acc[3]:
                row += bytes(round(c / acc[3]) for c in acc[:3]) + bytes([round(alpha)])
            else:
                row += bytes(4)
        rows.append(bytes(row))
    return b"".join(rows)


def png(raw, size):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    images = Path(__file__).resolve().parents[1] / "extension" / "images"
    images.mkdir(exist_ok=True)
    for name, size in (("icon.png", 42), ("icon_16.png", 16), ("icon_26.png", 26)):
        (images / name).write_bytes(png(render(size), size))
        print(images / name)
