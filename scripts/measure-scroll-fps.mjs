/**
 * Measure hero idle FPS + continuous-scroll FPS.
 * Usage: node scripts/measure-scroll-fps.mjs [url]
 */
import { chromium } from "playwright";

const url = process.argv[2] || "http://127.0.0.1:4200/";

const browser = await chromium.launch({
  headless: true,
  args: ["--disable-frame-rate-limit", "--disable-gpu-vsync"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForSelector("#hero-network", { timeout: 20000 });
await page.waitForTimeout(600);

const result = await page.evaluate(async () => {
  const measureFps = (ms) =>
    new Promise((resolve) => {
      const deltas = [];
      let last = performance.now();
      let start = last;
      const tick = (t) => {
        deltas.push(t - last);
        last = t;
        if (t - start < ms) requestAnimationFrame(tick);
        else {
          const samples = deltas.slice(3).filter((d) => d > 0 && d < 120);
          const avg =
            samples.reduce((a, b) => a + b, 0) / (samples.length || 1);
          resolve({
            samples: samples.length,
            avgMs: Number(avg.toFixed(2)),
            fps: Number((1000 / avg).toFixed(1)),
            below45: samples.filter((d) => d > 1000 / 45).length,
          });
        }
      };
      requestAnimationFrame(tick);
    });

  window.scrollTo(0, 0);
  await new Promise((r) => setTimeout(r, 200));
  const idle = await measureFps(2000);

  let y = 0;
  let scrolling = true;
  const scrollLoop = () => {
    if (!scrolling) return;
    y += 18;
    if (y > 1400) y = 0;
    window.scrollTo(0, y);
    requestAnimationFrame(scrollLoop);
  };
  requestAnimationFrame(scrollLoop);
  const scrollingFps = await measureFps(2500);
  scrolling = false;
  window.scrollTo(0, 0);

  const canvas = document.getElementById("hero-network");
  return {
    idle,
    scrolling: scrollingFps,
    isCanvas: canvas instanceof HTMLCanvasElement,
    heroClasses: document.getElementById("hero")?.className || "",
  };
});

console.log(JSON.stringify({ url, ...result }, null, 2));
await browser.close();

// Pass if idle near baseline (~40+) and scroll doesn't collapse badly.
const ok = result.idle.fps >= 35 && result.scrolling.fps >= 30;
process.exit(ok ? 0 : 2);
