const { chromium } = require("playwright");
const fs = require("fs");
const http = require("http");
const path = require("path");
const { fileURLToPath } = require("url");

const targets = [
  ["en", "site/index.html", "en", true],
  ["ja", "site/ja/index.html", "ja", true],
  ["zh-cn", "site/zh-cn/index.html", "zh-CN", true],
  ["404", "site/404.html", "en", false],
  ["ja-404", "site/ja/404.html", "ja", false],
  ["zh-cn-404", "site/zh-cn/404.html", "zh-CN", false],
];
const widths = [320, 375, 767, 768, 899, 900, 1024, 1100, 1101, 1280];

function fileUrl(relativePath) {
  return `file:///${path.resolve(relativePath).replace(/\\/g, "/")}`;
}

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
      const notFoundPath = pathname.startsWith("/ja/") ? "ja/404.html" : pathname.startsWith("/zh-cn/") ? "zh-cn/404.html" : "404.html";
      const fallback = path.resolve(siteRoot, notFoundPath);
      response.writeHead(404, { "Content-Type": contentType(fallback) });
      response.end(fs.readFileSync(fallback));
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

  for (const [name, relativePath, expectedLang, requiresMetadata] of targets) {
    const pagePath = path.resolve(relativePath);
    const cssPath = path.resolve("site/styles.css");

    for (const width of widths) {
      const requests = [];
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      page.on("request", (request) => {
        requests.push(request.url());
      });
      await page.goto(targetUrl(baseUrl, relativePath));
      await page.waitForLoadState("load");
      const result = await page.evaluate(({ viewportWidth, expectedLang, requiresMetadata }) => {
        const disallowedSelectors = {
          scripts: "script",
          forms: "form",
          buttons: "button",
          submitInputs: 'input[type="submit"], input[type="image"], input[type="button"]',
          formActions: "[formaction]",
          buttonRoles: '[role="button"]',
          iframes: "iframe",
          objects: "object, embed",
          media: "video, audio, source, picture",
          externalAssets: [
            'link[rel~="stylesheet"][href^="http:"]',
            'link[rel~="stylesheet"][href^="https:"]',
            'link[rel~="preload"][href^="http:"]',
            'link[rel~="preload"][href^="https:"]',
            'link[rel~="icon"][href^="http:"]',
            'link[rel~="icon"][href^="https:"]',
            'link[rel~="manifest"][href^="http:"]',
            'link[rel~="manifest"][href^="https:"]',
            'img[src^="http:"]',
            'img[src^="https:"]',
          ].join(", "),
          clickableClosedState: [
            "a.status-chip",
            "a.disabled-chip",
            "a.disabled-reason",
            "a.action-status",
            "[role='link'].status-chip",
            "[role='link'].disabled-chip",
            "[role='link'].disabled-reason",
          ].join(", "),
        };

        const disallowedCounts = Object.fromEntries(
          Object.entries(disallowedSelectors).map(([key, selector]) => [
            key,
            document.querySelectorAll(selector).length,
          ]),
        );

        const allowedAnchor = (href) => {
          const validFragments = new Set(["#top", "#flow", "#memory", "#trust", "#status", "#main"]);
          if (validFragments.has(href)) return true;
          if (href === "/" || href === "/ja/" || href === "/zh-cn/") return true;
          if (/^\/(#flow|#memory|#trust|#status|#top)$/.test(href)) return true;
          if (/^\/ja\/(#flow|#memory|#trust|#status|#top)$/.test(href)) return true;
          if (/^\/zh-cn\/(#flow|#memory|#trust|#status|#top)$/.test(href)) return true;
          if (href === "index.html" || href === "ja/index.html" || href === "zh-cn/index.html") return true;
          return false;
        };

        const expectedMeta = {
          en: {
            canonical: "https://knudg.com/",
            alternates: {
              en: "https://knudg.com/",
              ja: "https://knudg.com/ja/",
              "zh-CN": "https://knudg.com/zh-cn/",
              "x-default": "https://knudg.com/",
            },
          },
          ja: {
            canonical: "https://knudg.com/ja/",
            alternates: {
              en: "https://knudg.com/",
              ja: "https://knudg.com/ja/",
              "zh-CN": "https://knudg.com/zh-cn/",
              "x-default": "https://knudg.com/",
            },
          },
          "zh-CN": {
            canonical: "https://knudg.com/zh-cn/",
            alternates: {
              en: "https://knudg.com/",
              ja: "https://knudg.com/ja/",
              "zh-CN": "https://knudg.com/zh-cn/",
              "x-default": "https://knudg.com/",
            },
          },
        };

        const lang = document.documentElement.lang;
        const langOk = lang === expectedLang;
        const metaContract = expectedMeta[expectedLang];
        const canonical = document.querySelector('link[rel="canonical"]')?.getAttribute("href") || "";
        const alternateLinks = Object.fromEntries(
          Array.from(document.querySelectorAll('link[rel="alternate"][hreflang]')).map((link) => [
            link.getAttribute("hreflang"),
            link.getAttribute("href"),
          ]),
        );
        const metadataOk = !requiresMetadata || (
          canonical === metaContract.canonical &&
          Object.entries(metaContract.alternates).every(([alternateLang, href]) => alternateLinks[alternateLang] === href)
        );

        const badAnchors = Array.from(document.querySelectorAll("a[href]"))
          .map((anchor) => anchor.getAttribute("href"))
          .filter((href) => !allowedAnchor(href));

        const stylesheetText = Array.from(document.styleSheets)
          .map((sheet) => {
            try {
              return Array.from(sheet.cssRules).map((rule) => rule.cssText).join("\n");
            } catch {
              return "";
            }
          })
          .join("\n");

        const stylesheetLeaks = /@import|@font-face|url\s*\(/i.test(stylesheetText);
        const cssLoaded = window.getComputedStyle(document.documentElement).getPropertyValue("--ink").trim() !== "";

        const languageLinks = Array.from(document.querySelectorAll(".language-link"));
        const languageRects = languageLinks.map((language) => {
          const rect = language.getBoundingClientRect();
          return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
        });
        const languageLinksInViewport = languageRects.every((rect) =>
          rect.left >= -1 && rect.right <= viewportWidth + 1 && rect.top >= -1 && rect.bottom <= window.innerHeight + 1
        );
        const headerNav = document.querySelector(".primary-nav");
        const headerStatus = document.querySelector(".nav-actions .status-chip");
        const heroClosedState = document.querySelector(".launch-strip");

        const isVisible = (element) => {
          if (!element) return false;
          if (element.classList.contains("sr-only")) return false;
          const styles = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return styles.display !== "none" && styles.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
        };

        const headerNavVisible = isVisible(headerNav);
        const headerStatusVisible = isVisible(headerStatus);
        const closedStateRect = heroClosedState ? heroClosedState.getBoundingClientRect() : null;
        const closedStateAboveFold = Boolean(closedStateRect && closedStateRect.top >= 0 && closedStateRect.bottom <= window.innerHeight);
        const checkedElements = Array.from(
          document.querySelectorAll([
            ".site-header",
            ".hero-copy > *",
            ".workspace",
            ".terminal-lines li",
            ".signal-card",
            ".section-head",
            ".flow-step",
            ".memory-item",
            ".trust-item",
            ".state-card",
            ".launch-strip",
          ].join(", ")),
        ).filter(isVisible);

        const rectangles = checkedElements.map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            element,
            selector: element.className || element.tagName,
            left: rect.left,
            right: rect.right,
            top: rect.top,
            bottom: rect.bottom,
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
          };
        });

        const clipped = rectangles.filter((rect) =>
          rect.left < -1 ||
          rect.right > viewportWidth + 1 ||
          rect.top < -1 ||
          rect.scrollWidth > rect.clientWidth + 1
        );

        const overlaps = [];
        for (let i = 0; i < rectangles.length; i += 1) {
          for (let j = i + 1; j < rectangles.length; j += 1) {
            const a = rectangles[i];
            const b = rectangles[j];
            if (a.element.contains(b.element) || b.element.contains(a.element)) {
              continue;
            }
            const xOverlap = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const yOverlap = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (xOverlap > 1 && yOverlap > 1) {
              overlaps.push([a.selector, b.selector, xOverlap, yOverlap]);
            }
          }
        }

        const cjkParagraphTooWide = (lang === "ja" || lang === "zh-CN")
          ? Array.from(document.querySelectorAll("p, dd, li"))
              .filter(isVisible)
              .some((element) => {
                const rect = element.getBoundingClientRect();
                const computed = window.getComputedStyle(element);
                const fontSize = parseFloat(computed.fontSize) || 16;
                return viewportWidth <= 767 && rect.width / fontSize > 34;
              })
          : false;

        return {
          innerWidth: window.innerWidth,
          scrollWidth: document.documentElement.scrollWidth,
          bodyScrollWidth: document.body.scrollWidth,
          languageRects,
          languageLinksInViewport,
          disallowedCounts,
          badAnchors,
          stylesheetLeaks,
          cssLoaded,
          lang,
          langOk,
          metadataOk,
          headerNavVisible,
          headerStatusVisible,
          closedStateAboveFold,
          clipped,
          overlaps,
          cjkParagraphTooWide,
        };
      }, { viewportWidth: width, expectedLang, requiresMetadata });

      const externalRequests = requests.filter((url) => /^https?:\/\//i.test(url) && !url.startsWith(baseUrl));
      const unexpectedFileRequests = requests.filter((url) => {
        if (!url.startsWith("file:///")) return false;
        const cleanUrl = url.split("?")[0];
        const requestPath = path.resolve(fileURLToPath(cleanUrl));
        const rootStylesheetRequest = path.basename(requestPath) === "styles.css" && /[?&]v=layout-/.test(url);
        return (
          requestPath !== pagePath &&
          requestPath !== cssPath &&
          requestPath !== path.resolve("site/favicon.svg") &&
          !rootStylesheetRequest
        );
      });

      const expectedMobileHeader = width <= 767;
      const disallowedFound = Object.values(result.disallowedCounts).some((count) => count > 0);

      if (
        result.scrollWidth > result.innerWidth ||
        result.bodyScrollWidth > result.innerWidth ||
        !result.languageLinksInViewport ||
        disallowedFound ||
        result.badAnchors.length > 0 ||
        result.stylesheetLeaks ||
        !result.cssLoaded ||
        !result.langOk ||
        !result.metadataOk ||
        externalRequests.length > 0 ||
        unexpectedFileRequests.length > 0 ||
        (expectedMobileHeader && (result.headerNavVisible || result.headerStatusVisible)) ||
        (!expectedMobileHeader && (!result.headerNavVisible || !result.headerStatusVisible)) ||
        !result.closedStateAboveFold ||
        result.clipped.length > 0 ||
        result.overlaps.length > 0 ||
        result.cjkParagraphTooWide
      ) {
        failures.push({ name, width, result, requests, externalRequests, unexpectedFileRequests });
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
