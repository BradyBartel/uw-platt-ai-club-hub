#!/usr/bin/env python3
"""Extract PAIC hero-mark geometry from public/paic-logo.png.

Outputs src/paic-mark-data.ts with nodes, edges, outline normalized to 100x100.
Excludes PAIC text and varsity-letter regions so mesh nodes land on lines only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public" / "paic-logo.png"
OUT = ROOT / "src" / "paic-mark-data.ts"
DEBUG = ROOT / "scripts" / "paic-trace-debug.png"
SIZE = 100

# Elliptical masks (cx, cy, rx, ry) in viewBox coords — keep mesh off filled art.
EXCLUDE = (
    (50.0, 44.0, 17.0, 7.0),  # PAIC wordmark
    (50.0, 82.0, 16.0, 11.0),  # mountain + varsity M
    (78.0, 52.0, 9.0, 11.0),  # varsity P
)


def load_rgba() -> np.ndarray:
    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    scale = SIZE / max(w, h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ox = (SIZE - nw) // 2
    oy = (SIZE - nh) // 2
    canvas.paste(img, (ox, oy))
    return np.array(canvas)


def alpha_mask(rgba: np.ndarray) -> np.ndarray:
    return rgba[:, :, 3] > 40


def exclusion_mask(shape: tuple[int, int]) -> np.ndarray:
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    blocked = np.zeros((h, w), dtype=bool)
    for cx, cy, rx, ry in EXCLUDE:
        blocked |= ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
    return blocked


def color_energy(rgba: np.ndarray) -> np.ndarray:
    rgb = rgba[:, :, :3].astype(np.float32)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    sat = (mx - mn) / 255.0
    bright = mx / 255.0
    # Favor saturated mid-tones (mesh lines/nodes), not white fills or dark shield.
    return sat * 0.75 + np.clip(bright, 0.15, 0.92) * 0.25


def trace_outline(mask: np.ndarray) -> str:
    h, w = mask.shape
    pts: list[tuple[float, float]] = []
    for y in range(h):
        row = mask[y]
        for x in range(1, w):
            if row[x] and not row[x - 1]:
                pts.append((float(x), float(y)))
            elif not row[x] and row[x - 1]:
                pts.append((x - 0.5, float(y)))
    for x in range(w):
        col = mask[:, x]
        for y in range(1, h):
            if col[y] and not col[y - 1]:
                pts.append((float(x), float(y)))
            elif not col[y] and col[y - 1]:
                pts.append((float(x), y - 0.5))

    if len(pts) < 8:
        return "50,10 90,30 90,70 50,90 10,70 10,30"

    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))

    every = max(1, len(pts) // 52)
    simplified = [
        (round(pts[i][0], 2), round(pts[i][1], 2))
        for i in range(0, len(pts), every)
    ]
    return " ".join(f"{x},{y}" for x, y in simplified)


def local_maxima(
    energy: np.ndarray,
    mask: np.ndarray,
    blocked: np.ndarray,
    r: int = 2,
) -> list[tuple[float, float, float]]:
    h, w = energy.shape
    found: list[tuple[float, float, float]] = []
    taken = np.zeros((h, w), dtype=bool)
    for y in range(r, h - r):
        for x in range(r, w - r):
            if not mask[y, x] or blocked[y, x]:
                continue
            patch = energy[y - r : y + r + 1, x - r : x + r + 1]
            if energy[y, x] >= patch.max() * 0.97 and energy[y, x] > 0.38:
                if taken[max(0, y - 4) : min(h, y + 5), max(0, x - 4) : min(w, x + 5)].any():
                    continue
                taken[y - 4 : y + 5, x - 4 : x + 5] = True
                found.append((float(x), float(y), float(energy[y, x])))
    found.sort(key=lambda t: -t[2])
    return found[:24]


def line_between(
    energy: np.ndarray,
    mask: np.ndarray,
    blocked: np.ndarray,
    a: tuple[float, float],
    b: tuple[float, float],
) -> bool:
    x0, y0 = a
    x1, y1 = b
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 5 or dist > 36:
        return False
    steps = int(dist * 2.5)
    hits = 0
    blocked_hits = 0
    for i in range(steps + 1):
        t = i / max(steps, 1)
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        if 0 <= x < mask.shape[1] and 0 <= y < mask.shape[0]:
            if blocked[y, x]:
                blocked_hits += 1
                continue
            if mask[y, x] and energy[y, x] > 0.24:
                hits += 1
    if blocked_hits / (steps + 1) > 0.35:
        return False
    return hits / (steps + 1) > 0.48


def build_edges(
    nodes: list[tuple[float, float, float]],
    energy: np.ndarray,
    mask: np.ndarray,
    blocked: np.ndarray,
) -> list[tuple[int, int]]:
    edges: list[tuple[int, int]] = []
    for i, (x1, y1, _) in enumerate(nodes):
        neighbors: list[tuple[float, int]] = []
        for j, (x2, y2, _) in enumerate(nodes):
            if i == j:
                continue
            d = math.hypot(x2 - x1, y2 - y1)
            if d < 36 and line_between(energy, mask, blocked, (x1, y1), (x2, y2)):
                neighbors.append((d, j))
        neighbors.sort()
        for _, j in neighbors[:3]:
            pair = (min(i, j), max(i, j))
            if pair not in edges:
                edges.append(pair)
    return edges


def node_radius(norm: float) -> float:
    return round(0.65 + norm * 2.4, 2)


def write_debug(rgba: np.ndarray, nodes: list[list[float]]) -> None:
    from PIL import ImageDraw

    img = Image.fromarray(rgba)
    draw = ImageDraw.Draw(img)
    for cx, cy, rx, ry in EXCLUDE:
        draw.ellipse(
            (cx - rx, cy - ry, cx + rx, cy + ry),
            outline=(255, 0, 0, 120),
            width=1,
        )
    for x, y, _, _ in nodes:
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), outline=(255, 255, 0, 255))
    DEBUG.parent.mkdir(parents=True, exist_ok=True)
    img.save(DEBUG)


def fmt_ts(data: dict) -> str:
    def arr_line(label: str, rows: list) -> str:
        inner = ",\n  ".join(str(r) for r in rows)
        return f"export const {label} = [\n  {inner},\n] as const;"

    lines = [
        "/** Auto-generated by scripts/trace-paic-mark.py — do not edit by hand. */",
        arr_line("PAIC_OUTLINE", [f'"{data["outline"]}"']),
        arr_line(
            "PAIC_NODES",
            [f"[{x}, {y}, {r}, {h}]" for x, y, r, h in data["nodes"]],
        ),
        arr_line(
            "PAIC_EDGES",
            [f"[{a}, {b}]" for a, b in data["edges"]],
        ),
        f'export const PAIC_WORD = "{data["word"]}" as const;',
        f"export const PAIC_WORD_POS = [{data['word_x']}, {data['word_y']}] as const;",
    ]
    return "\n\n".join(lines) + "\n"


def main() -> None:
    rgba = load_rgba()
    mask = alpha_mask(rgba)
    blocked = exclusion_mask(mask.shape)
    energy = color_energy(rgba)
    energy[~mask] = 0
    energy[blocked] *= 0.15

    outline = trace_outline(mask)
    peaks = local_maxima(energy, mask, blocked)
    if len(peaks) < 10:
        raise SystemExit(f"Too few nodes detected: {len(peaks)}")

    max_e = max(e for _, _, e in peaks) or 1.0
    nodes: list[list[float]] = []
    for x, y, e in peaks:
        norm = e / max_e
        r = node_radius(norm)
        hollow = 1 if r > 2.1 else 0
        nodes.append([round(x, 2), round(y, 2), r, hollow])

    edges = build_edges(
        [(n[0], n[1], 1.0) for n in nodes],
        energy,
        mask,
        blocked,
    )

    write_debug(rgba, nodes)

    ts = fmt_ts(
        {
            "outline": outline,
            "nodes": nodes,
            "edges": edges,
            "word": "PAIC",
            "word_x": 50,
            "word_y": 44,
        }
    )
    OUT.write_text(ts, encoding="utf-8")
    print(f"Wrote {OUT}")
    print(json.dumps({"nodes": len(nodes), "edges": len(edges)}, indent=2))


if __name__ == "__main__":
    main()
