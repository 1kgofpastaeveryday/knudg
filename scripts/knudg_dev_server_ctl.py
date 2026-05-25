#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys


SERVER_PATTERN = re.compile(r"scripts[\\/]+knudg_dev_server\.py", re.IGNORECASE)
PORT_PATTERN = re.compile(r"--port\s+(\d+)")


def is_knudg_dev_server_command(command_line):
    return bool(command_line and SERVER_PATTERN.search(command_line))


def extract_port(command_line):
    if not command_line:
        return None
    match = PORT_PATTERN.search(command_line)
    if not match:
        return None
    return int(match.group(1))


def windows_processes():
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -like '*knudg_dev_server.py*' } | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        ),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to list Windows processes")
    text = result.stdout.strip()
    if not text:
        return []
    decoded = json.loads(text)
    rows = decoded if isinstance(decoded, list) else [decoded]
    return [
        {"pid": int(row["ProcessId"]), "command_line": row.get("CommandLine") or ""}
        for row in rows
    ]


def posix_processes():
    result = subprocess.run(["ps", "-eo", "pid=,args="], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to list processes")
    rows = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_text, _, command_line = line.partition(" ")
        if pid_text.isdigit():
            rows.append({"pid": int(pid_text), "command_line": command_line})
    return rows


def list_processes():
    raw = windows_processes() if os.name == "nt" else posix_processes()
    current_pid = os.getpid()
    processes = []
    for row in raw:
        command_line = row["command_line"]
        if row["pid"] == current_pid or not is_knudg_dev_server_command(command_line):
            continue
        processes.append(
            {
                "pid": row["pid"],
                "port": extract_port(command_line),
                "command_line": command_line,
            }
        )
    processes.sort(key=lambda item: (item["port"] is None, item["port"] or -1, item["pid"]))
    return processes


def stop_process(pid):
    if os.name == "nt":
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {int(pid)} -Force"],
            text=True,
            capture_output=True,
            check=False,
        )
    else:
        result = subprocess.run(["kill", "-TERM", str(int(pid))], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"failed to stop process {pid}")


def select_targets(processes, *, port, all_processes):
    if all_processes:
        return processes
    if port is None:
        raise ValueError("stop requires --port or --all")
    return [process for process in processes if process["port"] == port]


def emit(value):
    print(json.dumps(value, sort_keys=True))


def build_parser():
    parser = argparse.ArgumentParser(description="List or stop local Knudg dev server processes.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    stop = sub.add_parser("stop")
    stop.add_argument("--port", type=int)
    stop.add_argument("--all", action="store_true")
    stop.add_argument("--dry-run", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        processes = list_processes()
        if args.command == "list":
            emit({"ok": True, "status": "ok", "processes": processes})
            return 0
        targets = select_targets(processes, port=args.port, all_processes=args.all)
        if not args.dry_run:
            for target in targets:
                stop_process(target["pid"])
        emit({"ok": True, "status": "ok", "dry_run": args.dry_run, "stopped": [] if args.dry_run else [item["pid"] for item in targets], "targets": targets})
        return 0
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        emit({"ok": False, "status": "error", "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
