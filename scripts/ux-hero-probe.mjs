/**
 * UX probe — capture PAIC hero mark across animation frames.
 * Run: node scripts/ux-hero-probe.mjs
 * Requires: npx playwright (no project install).
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const OUT = path.resolve("scripts/ux-captures");
const SITES = [
  {
    name: "paic",
    url: "http://127.0.0.1:4176/",
    selector: ".hero__mark .bmark--paic",
  },
  {
    name: "all-charter",
    url: "https://uw-platt-ai-club.all-ai-network.org/",
    selector: ".hero__mark .bmark",
  },
];

const FRAMES_MS = [0, 200, 400, 600, 900, 1200, 1600, 2200];

async function captureSite(page, site) {
  await page.goto(site.url, { waitUntil: "networkidle" });
  await page.waitForSelector(site.selector, { timeout: 20000 });

  const dir = path.join(OUT, site.name);
  await mkdir(dir, { recursive: true });

  for (const ms of FRAMES_MS) {
    if (ms > 0) await page.waitForTimeout(ms);
    const mark = page.locator(site.selector);
    await mark.screenshot({ path: path.join(dir, `frame-${String(ms).padStart(4, "0")}ms.png`) });
  }

  const edgeStyle = await page.evaluate((sel) => {
    const edge = document.querySelector(`${sel} .bmark__edge`);
    if (!edge) return null;
    const cs = getComputedStyle(edge);
    return {
      opacity: cs.opacity,
      strokeDasharray: cs.strokeDasharray,
      strokeDashoffset: cs.strokeDashoffset,
      animationName: cs.animationName,
      animationDuration: cs.animationDuration,
    };
  }, site.selector);

  const imagePresent = await page.locator(`${site.selector} image, ${site.selector} .bmark__logo`).count();

  return { edgeStyle, imagePresent, frames: FRAMES_MS.length };
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const report = {};

for (const site of SITES) {
  try {
    report[site.name] = await captureSite(page, site);
    console.log(site.name, JSON.stringify(report[site.name], null, 2));
  } catch (err) {
    report[site.name] = { error: String(err) };
    console.error(site.name, err);
  }
}

await browser.close();
console.log("captures ->", OUT);
