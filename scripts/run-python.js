#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");

const MIN_MAJOR = 3;
const MIN_MINOR = 12;

const requested = process.env.KNUDG_PYTHON;
const candidates = requested
  ? [{ command: requested, prefix: [], label: "KNUDG_PYTHON" }]
  : [
      { command: process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python", prefix: [], label: ".venv" },
      { command: "python3.12", prefix: [], label: "python3.12" },
      { command: "python3", prefix: [], label: "python3" },
      { command: "python", prefix: [], label: "python" },
      { command: "py", prefix: ["-3.12"], label: "py -3.12" },
      { command: "py", prefix: ["-3"], label: "py -3" },
    ];

function parseVersion(output) {
  const match = output.match(/Python\s+(\d+)\.(\d+)\.(\d+)/);
  if (!match) {
    return null;
  }
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    text: match[0],
  };
}

function supportsVersion(version) {
  if (!version) {
    return false;
  }
  if (version.major > MIN_MAJOR) {
    return true;
  }
  return version.major === MIN_MAJOR && version.minor >= MIN_MINOR;
}

const attempts = [];
let selected = null;

for (const candidate of candidates) {
  const probe = spawnSync(candidate.command, [...candidate.prefix, "--version"], {
    encoding: "utf8",
  });
  const output = `${probe.stdout || ""}${probe.stderr || ""}`.trim();

  if (probe.error) {
    attempts.push(`${candidate.label}: ${probe.error.code || probe.error.message}`);
    continue;
  }

  const version = parseVersion(output);
  if (!supportsVersion(version)) {
    attempts.push(`${candidate.label}: ${output || "no version output"}`);
    continue;
  }

  selected = { ...candidate, version };
  break;
}

if (!selected) {
  console.error(`Knudg requires Python ${MIN_MAJOR}.${MIN_MINOR}+.`);
  console.error("Set KNUDG_PYTHON to a compatible interpreter, or install Python 3.12+.");
  if (attempts.length > 0) {
    console.error("Checked interpreters:");
    for (const attempt of attempts) {
      console.error(`- ${attempt}`);
    }
  }
  process.exit(1);
}

const args = process.argv.slice(2);
const finalArgs = args.length > 0 ? args : ["--version"];
const child = spawnSync(selected.command, [...selected.prefix, ...finalArgs], {
  stdio: "inherit",
});

if (child.error) {
  console.error(`Failed to run ${selected.label}: ${child.error.message}`);
  process.exit(1);
}

process.exit(child.status === null ? 1 : child.status);
