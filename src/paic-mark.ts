/**
 * paic-mark.ts — PAIC hero mark.
 *
 * Same SVG assemble as brain-mark.ts: edges fade, nodes pop, wordmark last.
 * Geometry is the PAIC mesh; the finished mark is PAIC, not a PNG overlay.
 */

import {
  PAIC_EDGES,
  PAIC_NODES,
  PAIC_WORD,
  PAIC_WORD_POS,
} from "./paic-mark-data";

const WORD_SPAN = 30;

function escapeXml(v: string): string {
  return v
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildPaicMarkSvg(reduce: boolean): string {
  const [wordX, wordY] = PAIC_WORD_POS;
  const fontSize =
    Math.round((WORD_SPAN / (0.85 * PAIC_WORD.length)) * 10) / 10;

  const edges = PAIC_EDGES.map(([a, b], i) => {
    const [x1, y1] = PAIC_NODES[a];
    const [x2, y2] = PAIC_NODES[b];
    const delay = reduce ? 0 : 0.35 + i * 0.022;
    return `<line class="bmark__edge" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" style="--d:${delay}s" />`;
  }).join("");

  const nodes = PAIC_NODES.map(([x, y, r, hollow], i) => {
    const delay = reduce ? 0 : 0.15 + i * 0.03;
    return `<circle class="bmark__node${hollow ? " bmark__node--hollow" : ""}" cx="${x}" cy="${y}" r="${r}" style="--d:${delay}s" />`;
  }).join("");

  const word = `<text class="bmark__word" x="${wordX}" y="${wordY}" text-anchor="middle"
      dominant-baseline="central" font-size="${fontSize}">${escapeXml(PAIC_WORD)}</text>`;

  return `
<svg class="bmark bmark--paic${reduce ? " bmark--static" : ""}" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
  <defs>
    <linearGradient id="bmark-grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="var(--color-primary, #1A64B7)" />
      <stop offset="100%" stop-color="var(--color-accent, #F58113)" />
    </linearGradient>
  </defs>
  <g class="bmark__edges">${edges}</g>
  <g class="bmark__nodes">${nodes}</g>
  ${word}
</svg>`;
}

export function renderPaicMark(
  el: Element | null,
  _logoUrl?: string,
  reduce = false,
): void {
  if (!el) return;
  el.innerHTML = buildPaicMarkSvg(reduce);
}
