const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const outputDir = process.argv[2] || ".codex/adversarial-review/lp-screenshots";
const baseUrl = process.argv[3] || "https://knudg.com";

const captures = [
  { name: "ja-desktop", path: "/ja/", width: 1440, height: 1000, fullPage: false },
  { name: "ja-desktop-full", path: "/ja/", width: 1440, height: 1000, fullPage: true },
  { name: "ja-mobile", path: "/ja/", width: 390, height: 844, fullPage: false },
  { name: "ja-mobile-full", path: "/ja/", width: 390, height: 844, fullPage: true },
  { name: "en-desktop", path: "/", width: 1440, height: 1000, fullPage: false },
  { name: "en-mobile", path: "/", width: 390, height: 844, fullPage: false },
  { name: "zh-desktop", path: "/zh-cn/", width: 1440, height: 1000, fullPage: false },
  { name: "zh-mobile", path: "/zh-cn/", width: 390, height: 844, fullPage: false },
];

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  for (const capture of captures) {
    const page = await browser.newPage({ viewport: { width: capture.width, height: capture.height } });
    await page.goto(new URL(capture.path, baseUrl).toString(), { waitUntil: "networkidle" });
    await page.screenshot({
      path: path.join(outputDir, `${capture.name}.png`),
      fullPage: capture.fullPage,
    });
    await page.close();
  }

  await browser.close();
  console.log(`captured ${captures.length} screenshot(s) in ${outputDir}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
