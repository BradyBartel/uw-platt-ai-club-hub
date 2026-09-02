/**
 * paic-mark.ts — PAIC hero mark via mask-reveal of the real logo art.
 *
 * Mesh lines are extracted from public/paic-logo.png (see trace-paic-mark.py).
 * White strokes in an SVG mask uncover paic-logo.png as they draw in, so the
 * hero shows actual logo pixels — not a recreated gradient mesh.
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
  const maskLines = PAIC_LINES.map(([a, b], i) => {
    const len = lineLength(a, b).toFixed(2);
    const delay = reduce ? 0 : 0.15 + i * 0.016;
    return `<line class="paic-mask__line" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="white" stroke-width="2.8" stroke-linecap="round" style="--d:${delay}s;--len:${len}" />`;
  }).join("");

  const points = uniquePoints(PAIC_LINES);
  const maskNodes = points
    .map(([x, y], i) => {
      const delay = reduce ? 0 : 0.55 + i * 0.012;
      return `<circle class="paic-mask__node" cx="${x}" cy="${y}" r="2.1" fill="white" style="--d:${delay}s" />`;
    })
    .join("");

  return `
<svg class="bmark bmark--paic${reduce ? " bmark--static" : ""}" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
  <defs>
    <mask id="paic-reveal" maskUnits="userSpaceOnUse">
      <rect width="100" height="100" fill="black" />
      <g class="paic-mask__lines">${maskLines}</g>
      <g class="paic-mask__nodes">${maskNodes}</g>
      <rect class="paic-mask__fill" width="100" height="100" fill="white" />
    </mask>
  </defs>
  <image class="bmark__logo" href="${PAIC_LOGO}" width="100" height="100" preserveAspectRatio="xMidYMid meet" mask="url(#paic-reveal)" />
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
