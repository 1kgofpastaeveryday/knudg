#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = process.cwd();
const venvDir = path.join(root, ".venv");
const venvPython =
  process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");

function run(command, args) {
  const child = spawnSync(command, args, { stdio: "inherit" });
  if (child.error) {
    console.error(`Failed to run ${command}: ${child.error.message}`);
    process.exit(1);
  }
  if (child.status !== 0) {
    process.exit(child.status === null ? 1 : child.status);
  }
}

if (!fs.existsSync(venvPython)) {
  run(process.execPath, ["scripts/run-python.js", "-m", "venv", ".venv"]);
}

run(venvPython, [
  "-m",
  "pip",
  "install",
  "-r",
  "requirements.txt",
  "-r",
  "requirements-dev.txt",
]);
