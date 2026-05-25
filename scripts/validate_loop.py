#!/usr/bin/env python3
"""Validate review-loop orchestration artifacts with a small schema subset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"

TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError:
        raise SystemExit(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}")


def schema_path(name: str) -> Path:
    base = Path(name).name
    return SCHEMA_DIR / (base if base.endswith(".json") else f"{base}.json")


def type_names(rule: Any) -> list[str]:
    return rule if isinstance(rule, list) else [rule]


def validate_node(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    if "type" in schema:
        allowed = type_names(schema["type"])
        if not any(TYPES.get(kind, lambda _v: False)(value) for kind in allowed):
            errors.append(f"{path}: expected type {'/'.join(allowed)}")
            return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: missing required field")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                validate_node(child, properties[key], f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: unexpected field")
    if isinstance(value, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(f"{path}: expected at least {min_items} item(s)")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_node(item, item_schema, f"{path}[{index}]", errors)


def example_for(schema: dict[str, Any]) -> Any:
    if "enum" in schema:
        return schema["enum"][0]
    kind = type_names(schema.get("type", "object"))[0]
    if kind == "object":
        props = schema.get("properties", {})
        return {key: example_for(props.get(key, {"type": "string"})) for key in schema.get("required", [])}
    if kind == "array":
        return [example_for(schema.get("items", {"type": "string"}))] if schema.get("minItems") else []
    if kind == "integer":
        return 1
    if kind == "boolean":
        return True
    if kind == "null":
        return None
    return "example"


def invariant_errors(schema_name: str, data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    errors: list[str] = []
    artifact_type = schema_name.removesuffix(".json")
    if data.get("artifact_type") != artifact_type:
        errors.append(f"$.artifact_type: expected {artifact_type!r}")
    if artifact_type == "target-manifest":
        included = set(data.get("included_paths", []))
        excluded = set(data.get("excluded_paths", []))
        overlap = sorted(included & excluded)
        if overlap:
            errors.append(f"$.included_paths/excluded_paths: overlap {overlap!r}")
        if data.get("target_class") == "ordinary-review-target":
            forbidden_fragments = [
                ".codex/review-loop/",
                "review-loop/",
                "raw-lane",
                "lane-output",
                "prompt",
                "ledger",
                "review-report",
                "review_report",
                "prior-review",
                "sidecar",
                "tmp-artifact",
                "temp-artifact",
                "temporary",
                "/tmp/",
                "/temp/",
                "/round-",
                "round-status",
                "worker-result",
            ]
            for path in sorted(included):
                normalized = str(path).replace("\\", "/").lower()
                if any(fragment.lower() in normalized for fragment in forbidden_fragments):
                    errors.append(f"$.included_paths: ordinary target includes loop artifact {path!r}")
    if artifact_type == "round-status":
        status = data.get("status")
        if status in {"FAIL", "BLOCKED", "DEGRADED"} and not data.get("summary"):
            errors.append("$.summary: non-pass status requires summary")
        if status == "PASS" and data.get("required_lanes_missing"):
            errors.append("$.required_lanes_missing: PASS cannot have missing required lanes")
    return errors


def validate_document(schema_name: str, data: Any) -> list[str]:
    schema_file = schema_path(schema_name)
    schema = load_json(schema_file)
    errors: list[str] = []
    validate_node(data, schema, "$", errors)
    errors.extend(invariant_errors(schema_file.name, data))
    return errors


def self_test() -> int:
    required = {"target-manifest.json", "round-status.json", "ledger-record.json", "worker-result.json"}
    found = {path.name for path in SCHEMA_DIR.glob("*.json")}
    missing = sorted(required - found)
    if missing:
        for item in missing:
            print(f"missing required schema: {item}", file=sys.stderr)
        return 1
    failed = False
    for schema_file in sorted(SCHEMA_DIR.glob("*.json")):
        if schema_file.name not in required:
            continue
        errors = validate_document(schema_file.name, example_for(load_json(schema_file)))
        if errors:
            failed = True
            print(f"{schema_file.name}: generated example failed", file=sys.stderr)
            for error in errors:
                print(f"  {error}", file=sys.stderr)
    if failed:
        return 1
    print(f"ok: self-test validated {len(required)} schema file(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate review-loop JSON artifacts.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--schema")
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.schema or not args.file:
        parser.error("--schema and --file are required unless --self-test is used")
    errors = validate_document(args.schema, load_json(args.file))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"ok: {args.file} matches {schema_path(args.schema).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
