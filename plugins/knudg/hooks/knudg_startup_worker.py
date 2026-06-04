#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKER_SCHEMA_VERSION = "knudg_startup_worker.v0"
WORKER_ROLE = "knudg_startup_subagent"
DEFAULT_TIMEOUT_SECONDS = 3.5


def emit(payload):
    payload = {
        "schema_version": WORKER_SCHEMA_VERSION,
        "role": WORKER_ROLE,
        **payload,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def load_task_profile():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def timeout_seconds():
    raw = os.environ.get("KNUDG_STARTUP_GATE_NUDGE_TIMEOUT_SECONDS")
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        return max(0.5, min(float(raw), 10.0))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def summarize_nudge_payload(payload):
    verdict = payload.get("verdict") if isinstance(payload, dict) else None
    if not isinstance(verdict, dict):
        return {"status": "unavailable", "error_class": "missing_verdict"}
    refs = verdict.get("refs") if isinstance(verdict.get("refs"), dict) else {}
    card_refs = refs.get("card_refs") if isinstance(refs.get("card_refs"), list) else []
    return {
        "status": verdict.get("status") or "unknown",
        "recommended_action": verdict.get("recommended_action"),
        "confidence": verdict.get("confidence"),
        "risk": verdict.get("risk"),
        "panel_ref": refs.get("panel_ref") if isinstance(refs.get("panel_ref"), str) else None,
        "ref_count": len(card_refs),
        "backend_query": "live_nudge",
        "crawl_status": "searched",
    }


def run_live_nudge(task_profile):
    if os.environ.get("KNUDG_STARTUP_GATE_DISABLE_NUDGE") == "1":
        return {"status": "disabled", "error_class": "disabled_by_env", "crawl_status": "skipped"}
    script = ROOT / "scripts" / "knudgctl.py"
    if not script.exists():
        return {"status": "unavailable", "error_class": "knudgctl_missing", "crawl_status": "skipped"}
    command = [
        sys.executable,
        str(script),
        "live",
        "nudge",
        "--task-profile",
        json.dumps(task_profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_seconds(),
        )
    except subprocess.TimeoutExpired:
        return {"status": "unavailable", "error_class": "timeout", "crawl_status": "timeout"}
    except OSError:
        return {"status": "unavailable", "error_class": "spawn_failed", "crawl_status": "skipped"}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"status": "unavailable", "error_class": "invalid_json", "crawl_status": "failed"}
    if result.returncode != 0 or not payload.get("ok"):
        return {
            "status": "unavailable",
            "error_class": str(payload.get("status") or payload.get("detail") or "nudge_failed")[:80],
            "crawl_status": "failed",
        }
    return summarize_nudge_payload(payload)


def main():
    task_profile = load_task_profile()
    if task_profile.get("schema_version") != "task_profile.v0":
        emit({"status": "unavailable", "error_class": "invalid_task_profile", "crawl_status": "skipped"})
        return 2
    result = run_live_nudge(task_profile)
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
