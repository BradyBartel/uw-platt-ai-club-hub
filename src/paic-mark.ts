/**
 * paic-mark.ts — PAIC hero mark.
 *
 * The logo image is sharp from frame one. Mesh lines (traced from
 * paic-logo.png) draw on top, then the overlay dissolves so the mark
 * settles on the full raster art without a blurry mask-reveal phase.
 */

import { PAIC_LINES, PAIC_LOGO } from "./paic-mark-data";

type Point = readonly [number, number];

function lineLength(a: Point, b: Point): number {
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

function uniquePoints(lines: readonly (readonly [Point, Point])[]): Point[] {
  const pts: Point[] = [];
  const eps = 1.8;

  for (const [a, b] of lines) {
    for (const p of [a, b]) {
      const hit = pts.find(
        (q) => Math.hypot(p[0] - q[0], p[1] - q[1]) <= eps,
      );
      if (!hit) pts.push([p[0], p[1]]);
    }
  }
  return pts;
}

function buildPaicMarkSvg(reduce: boolean): string {
  const meshLines = PAIC_LINES.map(([a, b], i) => {
    const len = lineLength(a, b).toFixed(2);
    const delay = reduce ? 0 : 0.12 + i * 0.014;
    return `<line class="paic-mesh__line" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" style="--d:${delay}s;--len:${len}" />`;
  }).join("");

  const points = uniquePoints(PAIC_LINES);
  const meshNodes = points
    .map(([x, y], i) => {
      const delay = reduce ? 0 : 0.45 + i * 0.01;
      return `<circle class="paic-mesh__node" cx="${x}" cy="${y}" r="1.35" style="--d:${delay}s" />`;
    })
    .join("");

  const overlay = reduce
    ? ""
    : `<g class="paic-mesh__overlay" aria-hidden="true">
        <g class="paic-mesh__lines">${meshLines}</g>
        <g class="paic-mesh__nodes">${meshNodes}</g>
      </g>`;

  return `
<svg class="bmark bmark--paic${reduce ? " bmark--static" : ""}" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
  <defs>
    <linearGradient id="paic-mesh-grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="var(--color-primary, #1A64B7)" />
      <stop offset="100%" stop-color="var(--color-accent, #F58113)" />
    </linearGradient>
  </defs>
  <image class="bmark__logo" href="${PAIC_LOGO}" width="100" height="100" preserveAspectRatio="xMidYMid meet" />
  ${overlay}
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
