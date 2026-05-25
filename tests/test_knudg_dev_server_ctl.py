import json
import subprocess
import sys
from pathlib import Path

from scripts.knudg_dev_server_ctl import extract_port, is_knudg_dev_server_command, select_targets


ROOT = Path(__file__).resolve().parents[1]


def test_dev_server_command_detection_is_narrow():
    assert is_knudg_dev_server_command("python scripts/knudg_dev_server.py --host 127.0.0.1 --port 8787")
    assert is_knudg_dev_server_command("python scripts\\knudg_dev_server.py --port 0 --quiet")
    assert not is_knudg_dev_server_command("python scripts/other.py --port 8787")
    assert not is_knudg_dev_server_command("node npm-cli.js run dev:server")
    assert not is_knudg_dev_server_command("")


def test_extract_port():
    assert extract_port("python scripts/knudg_dev_server.py --host 127.0.0.1 --port 8787") == 8787
    assert extract_port("python scripts/knudg_dev_server.py --port 0 --quiet") == 0
    assert extract_port("python scripts/knudg_dev_server.py") is None


def test_select_stop_targets_requires_explicit_scope():
    processes = [
        {"pid": 1, "port": 8787, "command_line": "python scripts/knudg_dev_server.py --port 8787"},
        {"pid": 2, "port": 0, "command_line": "python scripts/knudg_dev_server.py --port 0"},
    ]
    assert [item["pid"] for item in select_targets(processes, port=8787, all_processes=False)] == [1]
    assert [item["pid"] for item in select_targets(processes, port=None, all_processes=True)] == [1, 2]
    try:
        select_targets(processes, port=None, all_processes=False)
    except ValueError as exc:
        assert "--port or --all" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_dev_server_ctl_list_outputs_json():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudg_dev_server_ctl.py"), "list"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert isinstance(payload["processes"], list)
