/**
 * Hero mark QA — captures animation frames + side-by-side with source logo.
 * Run: npm run build && npx vite preview --port 4173 & node scripts/verify-hero.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(".");
const OUT = path.join(ROOT, "scripts/ux-captures/verify");
const URL = process.env.PREVIEW_URL ?? "http://127.0.0.1:4173/";
const FRAMES = [0, 300, 600, 900, 1200, 1700, 2200, 2800];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await mkdir(OUT, { recursive: true });

const report = { frames: [], checks: {} };

for (const ms of FRAMES) {
  await page.goto(URL, { waitUntil: "networkidle" });
  await page.waitForSelector(".hero__mark .bmark--paic", { timeout: 30000 });
  if (ms > 0) await page.waitForTimeout(ms);
  const mark = page.locator(".hero__mark .bmark--paic");
  const file = `hero-${String(ms).padStart(4, "0")}ms.png`;
  await mark.screenshot({ path: path.join(OUT, file) });
  const snap = await page.evaluate(() => {
    const logo = document.querySelector(".bmark--paic .bmark__logo");
    const wire = document.querySelector(".bmark--paic .bmark__wire");
    if (!logo || !wire) return null;
    const lo = getComputedStyle(logo);
    const wo = getComputedStyle(wire);
    return {
      logoOpacity: lo.opacity,
      wireOpacity: wo.opacity,
      lockVar: lo.getPropertyValue("--lock").trim() || wire.getAttribute("style"),
    };
  });
  report.frames.push({ ms, file, ...snap });
}

// Full hero context at end state
await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForTimeout(2800);
await page.locator(".hero").screenshot({ path: path.join(OUT, "hero-section-final.png") });

// Source vs locked mark
await page.evaluate(() => {
  const old = document.getElementById("qa-compare");
  old?.remove();
  const host = document.createElement("div");
  host.id = "qa-compare";
  host.style.cssText =
    "position:fixed;inset:0;z-index:99999;background:#0b0f18;display:flex;gap:40px;align-items:center;justify-content:center;padding:24px";
  const src = document.createElement("div");
  src.innerHTML =
    '<div style="color:#9ab;font:12px sans-serif;text-align:center;margin-bottom:8px">Source</div>';
  const img = document.createElement("img");
  img.src = "./paic-logo.png";
  img.width = 160;
  img.height = 160;
  src.appendChild(img);
  const hero = document.createElement("div");
  hero.innerHTML =
    '<div style="color:#9ab;font:12px sans-serif;text-align:center;margin-bottom:8px">Hero (locked)</div>';
  const clone = document.querySelector(".hero__mark .bmark--paic")?.cloneNode(true);
  if (clone) {
    clone.style.width = "160px";
    clone.style.height = "160px";
    hero.appendChild(clone);
  }
  host.append(src, hero);
  document.body.appendChild(host);
});
await page.waitForTimeout(200);
await page.screenshot({ path: path.join(OUT, "compare-source-vs-hero.png") });

report.checks.logoLoads = await page.evaluate(async () => {
  const res = await fetch("./paic-logo.png", { method: "HEAD" });
  return res.ok;
});

report.checks.edgeCount = await page.evaluate(
  () => document.querySelectorAll(".bmark--paic .bmark__edge").length,
);

console.log(JSON.stringify(report, null, 2));
await browser.close();
