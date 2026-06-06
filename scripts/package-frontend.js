#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const DIST = path.join(ROOT, "dist");
const STAGE = path.join(DIST, "knudg-frontend");
const rootPackage = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
const version = rootPackage.version;
const bundledToken = "knudg-frontend-public-beta-v0";

function ensureInside(parent, child) {
  const relative = path.relative(parent, child);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`${child} is outside ${parent}`);
  }
}

function copyFile(relativePath) {
  const source = path.join(ROOT, relativePath);
  const target = path.join(STAGE, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

function copyDirectory(relativePath) {
  const source = path.join(ROOT, relativePath);
  const target = path.join(STAGE, relativePath);
  fs.cpSync(source, target, { recursive: true });
}

function quoteWindowsArg(value) {
  if (/[\r\n]/.test(value)) {
    throw new Error("invalid command argument");
  }
  if (!/[\s"&|<>^]/.test(value)) {
    return value;
  }
  return `"${value.replace(/"/g, '""')}"`;
}

function runNpmPack(args) {
  if (process.platform === "win32") {
    const command = ["npm", ...args.map(quoteWindowsArg)].join(" ");
    return spawnSync(process.env.ComSpec || "cmd.exe", ["/d", "/s", "/c", command], {
      cwd: ROOT,
      encoding: "utf8",
    });
  }
  return spawnSync("npm", args, {
    cwd: ROOT,
    encoding: "utf8",
  });
}

fs.mkdirSync(DIST, { recursive: true });
ensureInside(DIST, STAGE);
fs.rmSync(STAGE, { recursive: true, force: true });
fs.mkdirSync(STAGE, { recursive: true });

copyDirectory("operator-ui");
copyFile("scripts/knudg_local_frontend.py");
copyFile("scripts/run-python.js");
copyFile("fixtures/consent-revocation-gate.draft.json");

fs.mkdirSync(path.join(STAGE, "bin"), { recursive: true });
fs.writeFileSync(
  path.join(STAGE, "bin", "knudg-frontend.js"),
  `#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..");
const runner = path.join(packageRoot, "scripts", "run-python.js");
const frontend = path.join(packageRoot, "scripts", "knudg_local_frontend.py");
const child = spawnSync(process.execPath, [runner, frontend, ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
});

if (child.error) {
  console.error(child.error.message);
  process.exit(1);
}

process.exit(child.status === null ? 1 : child.status);
`,
  { encoding: "utf8", mode: 0o755 },
);

fs.writeFileSync(
  path.join(STAGE, "package.json"),
  `${JSON.stringify(
    {
      name: "knudg-frontend",
      version,
      description: "Local Knudg operator frontend and same-origin proxy.",
      license: rootPackage.license,
      homepage: rootPackage.homepage,
      repository: rootPackage.repository,
      bin: {
        "knudg-frontend": "bin/knudg-frontend.js",
      },
      engines: {
        node: ">=20",
      },
      files: ["bin/", "fixtures/", "operator-ui/", "scripts/", ".env.example", "README.md"],
    },
    null,
    2,
  )}\n`,
  "utf8",
);

fs.writeFileSync(
  path.join(STAGE, ".env.example"),
  [
    "# Optional overrides for the packaged Knudg frontend.",
    "# The frontend uses the bundled public token when neither variable is set.",
    `KNUDG_FRONTEND_TOKEN=${bundledToken}`,
    "KNUDG_FRONTEND_API_BASE_URL=http://api.knudg.com",
    "",
  ].join("\n"),
  "utf8",
);

fs.writeFileSync(
  path.join(STAGE, "README.md"),
  [
    "# Knudg Frontend",
    "",
    "This package contains the local Knudg operator frontend and its same-origin proxy.",
    "The browser never receives the bearer token; the proxy process attaches it to backend requests.",
    "",
    "Run:",
    "",
    "```powershell",
    "npx knudg-frontend --api-base-url http://api.knudg.com",
    "```",
    "",
    "Configuration:",
    "",
    "- `KNUDG_FRONTEND_API_BASE_URL` selects the backend origin.",
    "- `KNUDG_FRONTEND_TOKEN` or `KNUDG_OPERATOR_TOKEN` overrides the bundled public frontend token.",
    `- Bundled public frontend token: \`${bundledToken}\`.`,
    "",
    "Backend note: the public frontend token is accepted only when the backend operator explicitly sets `KNUDG_DISTRIBUTION_TOKEN` to the same value.",
    "",
  ].join("\n"),
  "utf8",
);

const pack = runNpmPack(["pack", STAGE, "--pack-destination", DIST]);

if (pack.error) {
  throw pack.error;
}
if (pack.status !== 0) {
  process.stderr.write(pack.stderr || pack.stdout);
  process.exit(pack.status || 1);
}

const tarball = (pack.stdout || "").trim().split(/\r?\n/).filter(Boolean).pop();
console.log(JSON.stringify({ status: "packed", tarball: path.join("dist", tarball) }, null, 2));
