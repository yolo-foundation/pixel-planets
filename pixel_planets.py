#!/usr/bin/env python3

import argparse
import hashlib
import math
import random

GRID = 8
STEPS = 9
LATTICE = 2

def _to_lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def _from_lin(c):
    c = 12.92 * c if c <= 0.0031308 else 1.055 * (max(c, 0) ** (1 / 2.4)) - 0.055
    return c * 255

def rgb_to_oklch(rgb):
    r, g, b = (_to_lin(v) for v in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360

def _oklch_to_lin(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)

def oklch_to_rgb(L, C, h):
    def ok(c):
        return all(-1e-4 <= v <= 1 + 1e-4 for v in _oklch_to_lin(L, c, h))
    if not ok(C):
        lo, hi = 0.0, C
        for _ in range(24):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ok(mid) else (lo, mid)
        C = lo
    return tuple(min(255, max(0, round(_from_lin(v)))) for v in _oklch_to_lin(L, C, h))

def rgb_to_hex(c):
    return "#%02X%02X%02X" % tuple(c)

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def make_palette(base_rgb, rng):
    L, C, h = rgb_to_oklch(base_rgb)
    d = rng.choice([-1, 1])
    dark_shift = rng.uniform(22, 36)
    light_shift = rng.uniform(10, 18)
    drop = 0.22
    if 35 <= h <= 170:
        d = 1
        dark_shift = rng.uniform(26, 40)
        drop = 0.13
    L_lo = max(0.30, L - drop)
    L_hi = min(0.96, L + 0.16)
    stops = [
        (0.0, L_lo, C * 0.95, h - d * dark_shift),
        (0.5, L, C, h),
        (1.0, L_hi, C * 0.90, h + d * light_shift),
    ]

    def at(t):
        (t0, L0, C0, h0), (t1, L1, C1, h1) = (stops[0], stops[1]) if t <= 0.5 else (stops[1], stops[2])
        k = (t - t0) / (t1 - t0)
        return oklch_to_rgb(L0 + (L1 - L0) * k, C0 + (C1 - C0) * k, h0 + (h1 - h0) * k)

    return [at(i / (STEPS - 1)) for i in range(STEPS)]

def smooth(t):
    return t * t * (3 - 2 * t)

def make_field(rng):
    lat = [[rng.random() for _ in range(LATTICE + 1)] for _ in range(LATTICE + 1)]
    ang = rng.uniform(0, 2 * math.pi)
    ca, sa = math.cos(ang), math.sin(ang)
    field = []
    for y in range(GRID):
        row = []
        for x in range(GRID):
            u, v = (x + 0.5) / GRID, (y + 0.5) / GRID
            gx, gy = u * LATTICE, v * LATTICE
            x0, y0 = int(gx), int(gy)
            fx, fy = smooth(gx - x0), smooth(gy - y0)
            n = (lat[y0][x0] * (1 - fx) + lat[y0][x0 + 1] * fx) * (1 - fy) + \
                (lat[y0 + 1][x0] * (1 - fx) + lat[y0 + 1][x0 + 1] * fx) * fy
            grad = 0.5 + ((u - 0.5) * ca + (v - 0.5) * sa)
            row.append(0.55 * grad + 0.30 * n + 0.15 * rng.random())
        field.append(row)
    flat = [v for r in field for v in r]
    lo, hi = min(flat), max(flat)
    return [[(v - lo) / (hi - lo) for v in r] for r in field]

def make_avatar(name, color_hex):
    rng = random.Random(int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], "big"))
    pal = make_palette(hex_to_rgb(color_hex), rng)
    field = make_field(rng)
    return [[pal[round(v * (STEPS - 1))] for v in row] for row in field]

def save_png(cells, out, size=512):
    from PIL import Image, ImageDraw
    n = len(cells)
    img = Image.new("RGB", (n, n))
    img.putdata([c for row in cells for c in row])
    img = img.resize((size, size), Image.NEAREST)
    ss = 4
    mask = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * ss - 1, size * ss - 1), fill=255)
    img.putalpha(mask.resize((size, size), Image.LANCZOS))
    img.save(out)

def save_svg(cells, out, size=512):
    n = len(cells)
    rects = "".join(
        f'<rect x="{x}" y="{y}" width="1.02" height="1.02" fill="{rgb_to_hex(c)}"/>'
        for y, row in enumerate(cells) for x, c in enumerate(row))
    open(out, "w").write(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{size}" height="{size}">'
        f'<clipPath id="c"><circle cx="{n / 2}" cy="{n / 2}" r="{n / 2}"/></clipPath>'
        f'<g clip-path="url(#c)" shape-rendering="crispEdges">{rects}</g></svg>')

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="yolo")
    ap.add_argument("--color", default="#FF1999")
    ap.add_argument("--out", default="avatar.png")
    ap.add_argument("--size", type=int, default=512)
    a = ap.parse_args()
    cells = make_avatar(a.name, a.color)
    (save_svg if a.out.endswith(".svg") else save_png)(cells, a.out, a.size)
    print(a.out)