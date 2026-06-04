const { chromium } = require("playwright");
const fs = require("fs");
const http = require("http");
const path = require("path");

const targets = [
  ["en", "site/index.html", "en", true],
  ["ja", "site/ja/index.html", "ja", true],
  ["zh-cn", "site/zh-cn/index.html", "zh", true],
  ["install", "site/install/index.html", "en", false],
  ["ja-install", "site/ja/install/index.html", "ja", false],
  ["zh-cn-install", "site/zh-cn/install/index.html", "zh", false],
];
const widths = [320, 375, 768, 1024, 1280];

function contentType(filePath) {
  if (filePath.endsWith(".html")) return "text/html; charset=utf-8";
  if (filePath.endsWith(".css")) return "text/css; charset=utf-8";
  if (filePath.endsWith(".svg")) return "image/svg+xml";
  return "application/octet-stream";
}

function startSiteServer(siteRoot) {
  const server = http.createServer((request, response) => {
    const requestUrl = new URL(request.url, "http://127.0.0.1");
    const pathname = decodeURIComponent(requestUrl.pathname);
    const normalized = pathname === "/" ? "/index.html" : pathname.endsWith("/") ? `${pathname}index.html` : pathname;
    const candidate = path.resolve(siteRoot, `.${normalized}`);

    if (!candidate.startsWith(siteRoot)) {
      response.writeHead(403);
      response.end("Forbidden");
      return;
    }

    if (!fs.existsSync(candidate) || !fs.statSync(candidate).isFile()) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }

    response.writeHead(200, { "Content-Type": contentType(candidate) });
    response.end(fs.readFileSync(candidate));
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
  });
}

function targetUrl(baseUrl, relativePath) {
  const siteRelative = relativePath.replace(/^site[\\/]/, "").replace(/\\/g, "/");
  if (siteRelative === "index.html") return `${baseUrl}/`;
  if (siteRelative.endsWith("/index.html")) return `${baseUrl}/${siteRelative.replace(/index\.html$/, "")}`;
  return `${baseUrl}/${siteRelative}`;
}

(async () => {
  const siteRoot = path.resolve("site");
  const { server, baseUrl } = await startSiteServer(siteRoot);
  const browser = await chromium.launch({ headless: true });
  const failures = [];

  for (const [name, relativePath, expectedLang, requiresDiagram] of targets) {
    for (const width of widths) {
      const requests = [];
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      page.on("request", (request) => requests.push(request.url()));
      await page.goto(targetUrl(baseUrl, relativePath));
      await page.waitForLoadState("load");

      const result = await page.evaluate(({ expectedLang, requiresDiagram }) => {
        const allowedAnchor = (href) => {
          if (href === "/" || href === "../" || href === "ja/" || href === "zh-cn/") return true;
          if (href === "../ja/" || href === "../zh-cn/") return true;
          if (href === "https://knudg.com/install") return true;
          if (href === "https://knudg.com/ja/install") return true;
          if (href === "https://knudg.com/zh-cn/install") return true;
          if (href === "https://github.com/1kgofpastaeveryday/knudg") return true;
          return false;
        };

        const disallowedSelectors = [
          "script",
          "form",
          "button",
          'input[type="submit"], input[type="image"], input[type="button"]',
          "iframe",
          "object",
          "embed",
          "video",
          "audio",
        ];

        const badAnchors = Array.from(document.querySelectorAll("a[href]"))
          .map((anchor) => anchor.getAttribute("href"))
          .filter((href) => !allowedAnchor(href));
        const disallowedFound = disallowedSelectors.some((selector) => document.querySelector(selector));
        const langOk = document.documentElement.lang === expectedLang;
        const cssLoaded = getComputedStyle(document.body).maxWidth !== "none";
        const diagram = document.querySelector(".starting-point-diagram img");
        const diagramOk = !requiresDiagram || Boolean(
          diagram &&
          /knudg-start-shift/.test(diagram.getAttribute("src") || "") &&
          diagram.getBoundingClientRect().width > 0
        );

        const visibleElements = Array.from(document.querySelectorAll("body, h1, h2, p, li, figure, img"))
          .filter((element) => {
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
          });
        const clipped = visibleElements
          .map((element) => {
            const rect = element.getBoundingClientRect();
            return {
              tag: element.tagName,
              left: rect.left,
              right: rect.right,
              scrollWidth: element.scrollWidth,
              clientWidth: element.clientWidth,
            };
          })
          .filter((rect) => rect.left < -1 || rect.right > window.innerWidth + 1 || rect.scrollWidth > rect.clientWidth + 1);

        return {
          innerWidth: window.innerWidth,
          scrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body.scrollWidth,
          badAnchors,
          disallowedFound,
          langOk,
          cssLoaded,
          diagramOk,
          clipped,
        };
      }, { expectedLang, requiresDiagram });

      const externalRequests = requests.filter((url) => {
        if (!/^https?:\/\//i.test(url) || url.startsWith(baseUrl)) return false;
        return !/^https:\/\/fonts\.(googleapis|gstatic)\.com\//.test(url);
      });

      if (
        result.scrollWidth > result.innerWidth ||
        result.bodyScrollWidth > result.innerWidth ||
        result.badAnchors.length > 0 ||
        result.disallowedFound ||
        !result.langOk ||
        !result.cssLoaded ||
        !result.diagramOk ||
        result.clipped.length > 0 ||
        externalRequests.length > 0
      ) {
        failures.push({ name, width, result, externalRequests });
      }

      await page.close();
    }
  }

  await browser.close();
  server.close();

  if (failures.length > 0) {
    console.error(JSON.stringify(failures, null, 2));
    process.exit(1);
  }

  console.log("knudg.com layout checks passed");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
