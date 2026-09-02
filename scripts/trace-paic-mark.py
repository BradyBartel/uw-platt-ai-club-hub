#!/usr/bin/env python3
"""Extract mesh line segments from PAIC logo skeleton → paic-mark-data.ts."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.morphology import skeletonize

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public" / "paic-logo.png"
OUT = ROOT / "src" / "paic-mark-data.ts"
DEBUG = ROOT / "scripts" / "paic-mesh-extract.png"
SIZE = 100

EXCLUDE = (
    (50.0, 44.0, 15.0, 6.0),
)


def load_line_mask() -> np.ndarray:
    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    scale = SIZE / max(w, h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ox, oy = (SIZE - nw) // 2, (SIZE - nh) // 2
    canvas.paste(img, (ox, oy))
    arr = np.array(canvas)
    alpha = arr[:, :, 3] > 40
    rgb = arr[:, :, :3].astype(np.float32)
    sat = rgb.max(2) - rgb.min(2)
    bright = rgb.max(2)
    mask = alpha & (sat > 28) & (bright > 50) & (bright < 248)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    for cx, cy, rx, ry in EXCLUDE:
        mask &= ~(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0)
    mask = ndimage.binary_opening(mask, iterations=1)
    return skeletonize(mask)


def neighbors(y: int, x: int, skel: np.ndarray) -> list[tuple[int, int]]:
    h, w = skel.shape
    out: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and skel[ny, nx]:
                out.append((ny, nx))
    return out


def trace_segments(skel: np.ndarray) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    h, w = skel.shape
    nbr_count = np.zeros_like(skel, dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            if skel[y, x]:
                nbr_count[y, x] = len(neighbors(y, x, skel))

    visited_edge: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []

    def edge_key(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
        return (a, b) if a < b else (b, a)

    def walk(start: tuple[int, int], nxt: tuple[int, int]) -> list[tuple[int, int]]:
        path = [start, nxt]
        prev, cur = start, nxt
        while True:
            opts = [p for p in neighbors(cur[0], cur[1], skel) if p != prev]
            if len(opts) != 1:
                break
            nxt_pt = opts[0]
            path.append(nxt_pt)
            prev, cur = cur, nxt_pt
            if nbr_count[cur[0], cur[1]] != 2:
                break
        return path

    for y in range(h):
        for x in range(w):
            if not skel[y, x]:
                continue
            if nbr_count[y, x] not in (1, 3, 4):
                continue
            for ny, nx in neighbors(y, x, skel):
                ek = edge_key((y, x), (ny, nx))
                if ek in visited_edge:
                    continue
                path = walk((y, x), (ny, nx))
                for i in range(len(path) - 1):
                    visited_edge.add(edge_key(path[i], path[i + 1]))
                a = (round(path[0][1] + 0.5, 2), round(path[0][0] + 0.5, 2))
                b = (round(path[-1][1] + 0.5, 2), round(path[-1][0] + 0.5, 2))
                if math.hypot(b[0] - a[0], b[1] - a[1]) >= 2.5:
                    segments.append((a, b))

    return merge_segments(dedupe_segments(segments))


def dedupe_segments(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    seen: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    out: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for a, b in segments:
        key = (a, b) if a < b else (b, a)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def merge_segments(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    eps: float = 1.2,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    def near(p: tuple[float, float], q: tuple[float, float]) -> bool:
        return math.hypot(p[0] - q[0], p[1] - q[1]) <= eps

    merged = True
    segs = list(segments)
    while merged:
        merged = False
        next_segs: list[tuple[tuple[float, float], tuple[float, float]]] = []
        used = [False] * len(segs)
        for i, (a1, b1) in enumerate(segs):
            if used[i]:
                continue
            cur_a, cur_b = a1, b1
            used[i] = True
            changed = True
            while changed:
                changed = False
                for j, (a2, b2) in enumerate(segs):
                    if used[j]:
                        continue
                    if near(cur_b, a2):
                        cur_b = b2
                        used[j] = True
                        changed = merged = True
                    elif near(cur_b, b2):
                        cur_b = a2
                        used[j] = True
                        changed = merged = True
                    elif near(cur_a, a2):
                        cur_a = b2
                        used[j] = True
                        changed = merged = True
                    elif near(cur_a, b2):
                        cur_a = a2
                        used[j] = True
                        changed = merged = True
            if math.hypot(cur_b[0] - cur_a[0], cur_b[1] - cur_a[1]) >= 2.5:
                next_segs.append((cur_a, cur_b))
        segs = next_segs
    return segs


def build_nodes_edges(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    eps: float = 2.2,
) -> tuple[list[list[float]], list[tuple[int, int]]]:
    points: list[tuple[float, float]] = []

    def get_idx(p: tuple[float, float]) -> int:
        for i, q in enumerate(points):
            if math.hypot(p[0] - q[0], p[1] - q[1]) <= eps:
                return i
        points.append(p)
        return len(points) - 1

    edges: list[tuple[int, int]] = []
    for a, b in segments:
        i, j = get_idx(a), get_idx(b)
        if i != j:
            pair = (min(i, j), max(i, j))
            if pair not in edges:
                edges.append(pair)

    nodes: list[list[float]] = []
    for x, y in points:
        degree = sum(1 for a, b in edges if a == len(nodes) or b == len(nodes))
        r = 1.15 if degree <= 2 else 1.55 if degree <= 4 else 2.05
        hollow = 1 if r >= 2.0 else 0
        nodes.append([round(x, 2), round(y, 2), round(r, 2), hollow])

    return nodes, edges


def trace_outline(mask_full: np.ndarray) -> str:
    from PIL import Image as PILImage

    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    scale = SIZE / max(w, h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), PILImage.Resampling.LANCZOS)
    canvas = PILImage.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ox, oy = (SIZE - nw) // 2, (SIZE - nh) // 2
    canvas.paste(img, (ox, oy))
    alpha = np.array(canvas)[:, :, 3] > 40
    pts: list[tuple[float, float]] = []
    for y in range(SIZE):
        for x in range(1, SIZE):
            if alpha[y, x] and not alpha[y, x - 1]:
                pts.append((float(x), float(y)))
    for x in range(SIZE):
        for y in range(1, SIZE):
            if alpha[y, x] and not alpha[y - 1, x]:
                pts.append((float(x), float(y)))
    cx = sum(p[0] for p in pts) / max(len(pts), 1)
    cy = sum(p[1] for p in pts) / max(len(pts), 1)
    pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    every = max(1, len(pts) // 56)
    simp = [(round(pts[i][0], 2), round(pts[i][1], 2)) for i in range(0, len(pts), every)]
    return " ".join(f"{x},{y}" for x, y in simp)


def write_debug(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    nodes: list[list[float]],
) -> None:
    from PIL import ImageDraw

    img = Image.new("RGB", (SIZE, SIZE), (10, 10, 16))
    draw = ImageDraw.Draw(img)
    for (x1, y1), (x2, y2) in segments:
        draw.line((x1, y1, x2, y2), fill=(80, 160, 255), width=1)
    for x, y, r, _ in nodes:
        draw.ellipse((x - r, y - r, x + r, y + r), outline=(245, 130, 30))
    DEBUG.parent.mkdir(parents=True, exist_ok=True)
    img.save(DEBUG)


def fmt_ts(outline: str, nodes: list, edges: list) -> str:
    def arr(label: str, rows: list) -> str:
        inner = ",\n  ".join(str(r) for r in rows)
        return f"export const {label} = [\n  {inner},\n] as const;"

    return "\n\n".join(
        [
            "/** Auto-generated by scripts/trace-paic-mark.py — skeleton mesh lines. */",
            arr("PAIC_OUTLINE", [f'"{outline}"']),
            arr("PAIC_NODES", [f"[{x}, {y}, {r}, {h}]" for x, y, r, h in nodes]),
            arr("PAIC_EDGES", [f"[{a}, {b}]" for a, b in edges]),
            arr("PAIC_LINES", [f"[[{x1}, {y1}], [{x2}, {y2}]]" for (x1, y1), (x2, y2) in []]),
            'export const PAIC_WORD = "PAIC" as const;',
            "export const PAIC_WORD_POS = [50, 44] as const;",
            'export const PAIC_LOGO = "./paic-logo.png" as const;',
        ]
    ) + "\n"


def main() -> None:
    skel = load_line_mask()
    segments = trace_segments(skel)
    nodes, edges = build_nodes_edges(segments)
    outline = trace_outline(skel)
    write_debug(segments, nodes)

  # also store raw line segments for mask reveal
    lines = [[list(a), list(b)] for a, b in segments]

    def arr(label: str, rows: list) -> str:
        inner = ",\n  ".join(str(r) for r in rows)
        return f"export const {label} = [\n  {inner},\n] as const;"

    ts = "\n\n".join(
        [
            "/** Auto-generated by scripts/trace-paic-mark.py — skeleton mesh lines. */",
            arr("PAIC_OUTLINE", [f'"{outline}"']),
            arr("PAIC_NODES", [f"[{x}, {y}, {r}, {h}]" for x, y, r, h in nodes]),
            arr("PAIC_EDGES", [f"[{a}, {b}]" for a, b in edges]),
            arr("PAIC_LINES", [f"[[{a[0]}, {a[1]}], [{b[0]}, {b[1]}]]" for a, b in lines]),
            'export const PAIC_WORD = "PAIC" as const;',
            "export const PAIC_WORD_POS = [50, 44] as const;",
            'export const PAIC_LOGO = "./paic-logo.png" as const;',
        ]
    ) + "\n"
    OUT.write_text(ts, encoding="utf-8")
    print(json.dumps({"segments": len(segments), "nodes": len(nodes), "edges": len(edges)}, indent=2))


if __name__ == "__main__":
    main()
