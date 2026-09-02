#!/usr/bin/env python3
"""Extract PAIC hero-mark geometry — curated to ~24 nodes like brain-mark.ts."""

from __future__ import annotations

import json
import math
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
MAX_NODES = 24
MIN_SEG_LEN = 3.5

EXCLUDE = ((50.0, 44.0, 15.0, 6.0),)


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
    return skeletonize(ndimage.binary_opening(mask, iterations=1))


def neighbors(y: int, x: int, skel: np.ndarray) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < skel.shape[0] and 0 <= nx < skel.shape[1] and skel[ny, nx]:
                out.append((ny, nx))
    return out


def trace_segments(skel: np.ndarray) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    h, w = skel.shape
    nbr_count = np.zeros_like(skel, dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            if skel[y, x]:
                nbr_count[y, x] = len(neighbors(y, x, skel))

    visited: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    segments: list[tuple[tuple[float, float], tuple[float, float], float]] = []

    def ek(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
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
            if not skel[y, x] or nbr_count[y, x] not in (1, 3, 4):
                continue
            for ny, nx in neighbors(y, x, skel):
                key = ek((y, x), (ny, nx))
                if key in visited:
                    continue
                path = walk((y, x), (ny, nx))
                for i in range(len(path) - 1):
                    visited.add(ek(path[i], path[i + 1]))
                a = (round(path[0][1] + 0.5, 2), round(path[0][0] + 0.5, 2))
                b = (round(path[-1][1] + 0.5, 2), round(path[-1][0] + 0.5, 2))
                length = math.hypot(b[0] - a[0], b[1] - a[1])
                if length >= MIN_SEG_LEN:
                    segments.append((a, b, length))

    segments.sort(key=lambda t: -t[2])
    return [(a, b) for a, b, _ in segments]


def build_graph(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    eps: float = 2.0,
) -> tuple[list[list[float]], list[tuple[int, int]]]:
    pts: list[tuple[float, float]] = []

    def idx(p: tuple[float, float]) -> int:
        for i, q in enumerate(pts):
            if math.hypot(p[0] - q[0], p[1] - q[1]) <= eps:
                return i
        pts.append(p)
        return len(pts) - 1

    edges: list[tuple[int, int]] = []
    for a, b in segments:
        i, j = idx(a), idx(b)
        if i == j:
            continue
        pair = (min(i, j), max(i, j))
        if pair not in edges:
            edges.append(pair)

    nodes = [
        [round(x, 2), round(y, 2), 1.0, 0.0]
        for x, y in pts
    ]
    return nodes, edges


def merge_closest_nodes(
    nodes: list[list[float]],
    edges: list[tuple[int, int]],
    target: int,
) -> tuple[list[list[float]], list[tuple[int, int]]]:
    while len(nodes) > target:
        best = (1e9, -1, -1)
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                d = math.hypot(nodes[i][0] - nodes[j][0], nodes[i][1] - nodes[j][1])
                if d < best[0]:
                    best = (d, i, j)
        _, i, j = best
        if i < 0:
            break
        nodes[i][0] = round((nodes[i][0] + nodes[j][0]) / 2, 2)
        nodes[i][1] = round((nodes[i][1] + nodes[j][1]) / 2, 2)
        nodes.pop(j)
        rewired: list[tuple[int, int]] = []
        for a, b in edges:
            na = a if a < j else a - 1
            nb = b if b < j else b - 1
            if na == nb:
                continue
            if na == i or nb == i:
                other = nb if na == i else na
                pair = (min(i, other), max(i, other))
                if pair not in rewired:
                    rewired.append(pair)
            else:
                pair = (min(na, nb), max(na, nb))
                if pair not in rewired:
                    rewired.append(pair)
        edges = rewired

    return nodes, edges


def prune_edges(
    nodes: list[list[float]],
    edges: list[tuple[int, int]],
    max_edges: int,
) -> list[tuple[int, int]]:
    scored: list[tuple[float, tuple[int, int]]] = []
    for a, b in edges:
        x1, y1 = nodes[a][0], nodes[a][1]
        x2, y2 = nodes[b][0], nodes[b][1]
        scored.append((math.hypot(x2 - x1, y2 - y1), (a, b)))
    scored.sort(reverse=True)
    kept: list[tuple[int, int]] = []
    for _, pair in scored:
        if len(kept) >= max_edges:
            break
        if pair not in kept:
            kept.append(pair)
    return kept


def finalize_nodes(
    nodes: list[list[float]],
    edges: list[tuple[int, int]],
) -> list[list[float]]:
    out: list[list[float]] = []
    for i, (x, y, _, _) in enumerate(nodes):
        degree = sum(1 for a, b in edges if a == i or b == i)
        if degree >= 5:
            r, hollow = 2.85, 1
        elif degree >= 3:
            r, hollow = 2.1, 1
        elif degree == 2:
            r, hollow = 1.5, 0
        else:
            r, hollow = 1.0, 0
        if degree == 1 and r < 1.3:
            r = 0.94
        out.append([x, y, round(r, 2), hollow])
    return out


def skeleton_line_between(
    skel: np.ndarray,
    a: tuple[float, float],
    b: tuple[float, float],
) -> bool:
    x0, y0 = a
    x1, y1 = b
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 4 or dist > 36:
        return False
    steps = int(dist * 2.5)
    hits = 0
    for i in range(steps + 1):
        t = i / max(steps, 1)
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        if 0 <= x < skel.shape[1] and 0 <= y < skel.shape[0] and skel[y, x]:
            hits += 1
    return hits / (steps + 1) > 0.45


def enrich_edges(
    skel: np.ndarray,
    nodes: list[list[float]],
    edges: list[tuple[int, int]],
    max_edges: int = 38,
) -> list[tuple[int, int]]:
    out = list(edges)
    for i, (x1, y1, _, _) in enumerate(nodes):
        candidates: list[tuple[float, int]] = []
        for j, (x2, y2, _, _) in enumerate(nodes):
            if i == j:
                continue
            pair = (min(i, j), max(i, j))
            if pair in out:
                continue
            d = math.hypot(x2 - x1, y2 - y1)
            if d < 36 and skeleton_line_between(skel, (x1, y1), (x2, y2)):
                candidates.append((d, j))
        candidates.sort()
        for _, j in candidates[:4]:
            pair = (min(i, j), max(i, j))
            if pair not in out:
                out.append(pair)
            if len(out) >= max_edges:
                return out
    return out


def trace_outline() -> str:
    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    scale = SIZE / max(w, h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ox, oy = (SIZE - nw) // 2, (SIZE - nh) // 2
    canvas.paste(img, (ox, oy))
    alpha = np.array(canvas)[:, :, 3] > 40
    ring = alpha & ~ndimage.binary_erosion(alpha)
    ys, xs = np.where(ring)
    if len(xs) < 8:
        return "50,10 90,30 90,70 50,90 10,70 10,30"
    pts = [(float(xs[i]), float(ys[i])) for i in range(len(xs))]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    pts.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    every = max(1, len(pts) // 52)
    simp = [(round(pts[i][0], 2), round(pts[i][1], 2)) for i in range(0, len(pts), every)]
    return " ".join(f"{x},{y}" for x, y in simp)


def write_debug(nodes: list, edges: list) -> None:
    from PIL import ImageDraw

    img = Image.new("RGB", (SIZE, SIZE), (10, 10, 16))
    draw = ImageDraw.Draw(img)
    for a, b in edges:
        x1, y1 = nodes[a][0], nodes[a][1]
        x2, y2 = nodes[b][0], nodes[b][1]
        draw.line((x1, y1, x2, y2), fill=(80, 160, 255))
    for x, y, r, _ in nodes:
        draw.ellipse((x - r, y - r, x + r, y + r), outline=(245, 130, 30))
    DEBUG.parent.mkdir(parents=True, exist_ok=True)
    img.save(DEBUG)


def main() -> None:
    skel = load_line_mask()
    segments = trace_segments(skel)
    nodes, edges = build_graph(segments)
    nodes, edges = merge_closest_nodes(nodes, edges, MAX_NODES)
    edges = enrich_edges(skel, nodes, edges, max_edges=38)
    nodes = finalize_nodes(nodes, edges)
    outline = trace_outline()
    write_debug(nodes, edges)

    def arr(label: str, rows: list) -> str:
        inner = ",\n  ".join(str(r) for r in rows)
        return f"export const {label} = [\n  {inner},\n] as const;"

    ts = "\n\n".join(
        [
            "/** Auto-generated by scripts/trace-paic-mark.py — do not edit by hand. */",
            arr("PAIC_OUTLINE", [f'"{outline}"']),
            arr("PAIC_NODES", [f"[{x}, {y}, {r}, {h}]" for x, y, r, h in nodes]),
            arr("PAIC_EDGES", [f"[{a}, {b}]" for a, b in edges]),
            'export const PAIC_WORD = "PAIC" as const;',
            "export const PAIC_WORD_POS = [50, 44] as const;",
        ]
    ) + "\n"
    OUT.write_text(ts, encoding="utf-8")
    print(json.dumps({"nodes": len(nodes), "edges": len(edges)}, indent=2))


if __name__ == "__main__":
    main()
