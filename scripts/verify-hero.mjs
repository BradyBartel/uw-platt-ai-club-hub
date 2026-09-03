/**
 * Hero mark QA — original mesh assemble with PAIC wordmark.
 * Run: PREVIEW_URL=http://127.0.0.1:4189/ node scripts/verify-hero.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(".");
const OUT = path.join(ROOT, "scripts/ux-captures/verify");
const URL = process.env.PREVIEW_URL ?? "http://127.0.0.1:4189/";
const FRAMES = [0, 500, 1000, 1400, 1800, 2200, 2800];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await mkdir(OUT, { recursive: true });

const report = { url: URL, frames: [], checks: {} };

for (const ms of FRAMES) {
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForSelector(".hero__mark .bmark", { timeout: 30000 });
  if (ms > 0) await page.waitForTimeout(ms);
  const mark = page.locator(".hero__mark .bmark").first();
  const file = `hero-${String(ms).padStart(4, "0")}ms.png`;
  await mark.screenshot({ path: path.join(OUT, file) });
  const snap = await page.evaluate(() => {
    const svg = document.querySelector(".hero__mark .bmark");
    const word = svg?.querySelector(".bmark__word");
    return {
      edgeCount: svg?.querySelectorAll(".bmark__edge").length ?? 0,
      nodeCount: svg?.querySelectorAll(".bmark__node").length ?? 0,
      word: word?.textContent ?? "",
      wordOpacity: word ? parseFloat(getComputedStyle(word).opacity || "0") : 0,
      isImg: svg instanceof HTMLImageElement,
    };
  });
  report.frames.push({ ms, file, ...snap });
}

await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForTimeout(2800);
await page.locator(".hero").screenshot({ path: path.join(OUT, "hero-section-final.png") });

console.log(JSON.stringify(report, null, 2));
await browser.close();
