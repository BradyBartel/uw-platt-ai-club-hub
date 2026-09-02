/**
 * paic-mark.ts — PAIC hero mark, line-assemble animation.
 *
 * Same motion model as brain-mark.ts (ALL template): shield outline,
 * mesh edges stagger in, nodes pop, PAIC wordmark last. Geometry from
 * scripts/trace-paic-mark.py.
 */

import {
  PAIC_LINES,
  PAIC_OUTLINE,
  PAIC_WORD,
  PAIC_WORD_POS,
} from "./paic-mark-data";

type Point = readonly [number, number];

const WORD_SPAN = 28;

function escapeXml(v: string): string {
  return v
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildNodes(
  lines: readonly (readonly [Point, Point])[],
): Array<[number, number, number, number]> {
  const pts: Point[] = [];
  const eps = 2.0;

  const idx = (p: Point): number => {
    for (let i = 0; i < pts.length; i++) {
      if (Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]) <= eps) return i;
    }
    pts.push(p);
    return pts.length - 1;
  };

  const degree: number[] = [];

  for (const [a, b] of lines) {
    const i = idx(a);
    const j = idx(b);
    if (i === j) continue;
    while (degree.length <= Math.max(i, j)) degree.push(0);
    degree[i]++;
    degree[j]++;
  }

  return pts.map(([x, y], i) => {
    const d = degree[i] ?? 1;
    const r = d <= 2 ? 0.95 : d <= 4 ? 1.45 : 2.05;
    const hollow = r >= 2 ? 1 : 0;
    return [x, y, r, hollow];
  });
}

function buildPaicMarkSvg(reduce: boolean): string {
  const outline = PAIC_OUTLINE[0];
  const [wordX, wordY] = PAIC_WORD_POS;
  const fontSize =
    Math.round((WORD_SPAN / (0.85 * PAIC_WORD.length)) * 10) / 10;
  const nodes = buildNodes(PAIC_LINES);

  const edges = PAIC_LINES.map(([a, b], i) => {
    const delay = reduce ? 0 : 0.35 + i * 0.014;
    return `<line class="bmark__edge" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" style="--d:${delay}s" />`;
  }).join("");

  const nodeEls = nodes
    .map(([x, y, r, hollow], i) => {
      const delay = reduce ? 0 : 0.15 + i * 0.022;
      return `<circle class="bmark__node${hollow ? " bmark__node--hollow" : ""}" cx="${x}" cy="${y}" r="${r}" style="--d:${delay}s" />`;
    })
    .join("");

  const word = `<text class="bmark__word" x="${wordX}" y="${wordY}" text-anchor="middle"
      dominant-baseline="central" font-size="${fontSize}">${escapeXml(PAIC_WORD)}</text>`;

  return `
<svg class="bmark bmark--paic${reduce ? " bmark--static" : ""}" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
  <defs>
    <linearGradient id="bmark-grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="var(--color-primary, #1A64B7)" />
      <stop offset="55%" stop-color="var(--color-primary, #1A64B7)" />
      <stop offset="100%" stop-color="var(--color-accent, #F58113)" />
    </linearGradient>
  </defs>
  <polygon class="bmark__outline" points="${outline}" />
  <g class="bmark__edges">${edges}</g>
  <g class="bmark__nodes">${nodeEls}</g>
  ${word}
</svg>`;
}

export function renderPaicMark(el: Element | null): void {
  if (!el) return;

  const reduce =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  el.innerHTML = buildPaicMarkSvg(reduce);
}
