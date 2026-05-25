#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from card_payload import canonical_digest_hex
from knudg_local_private import validate_local_private_card_v0


def load_token(args):
    if args.token:
        return args.token
    if args.token_env and os.environ.get(args.token_env):
        return os.environ[args.token_env]
    if os.environ.get("KNUDG_OPERATOR_TOKEN"):
        return os.environ["KNUDG_OPERATOR_TOKEN"]
    raise SystemExit("operator token is required via --token, --token-env, or KNUDG_OPERATOR_TOKEN")


def post_json(url, token, payload, digest):
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/private/cards:publish",
        data=body,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "x-knudg-artifact-digest": digest,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Post a sanitized local-private card to the Knudg closed API.")
    parser.add_argument("--api-url", default=os.environ.get("KNUDG_API_URL", "https://knudg-api-dev-390745.azurewebsites.net"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--workspace", default="closed-launch-manual")
    parser.add_argument("--approve-digest", help="Required digest approval. Use --print-digest first or pass the printed digest.")
    parser.add_argument("--print-digest", action="store_true")
    parser.add_argument("--token")
    parser.add_argument("--token-env")
    args = parser.parse_args()

    card = validate_local_private_card_v0(json.loads(Path(args.input).read_text(encoding="utf-8")))
    digest = canonical_digest_hex(card)
    if args.print_digest or not args.approve_digest:
        print(json.dumps({"status": "approval_required", "artifact_digest": digest, "card": card}, sort_keys=True, indent=2))
        if not args.approve_digest:
            return 2
    if args.approve_digest.lower() != digest:
        print(json.dumps({"status": "digest_mismatch", "expected": digest, "provided": args.approve_digest}, sort_keys=True))
        return 3
    status, payload = post_json(args.api_url, load_token(args), {"workspace": args.workspace, "card": card}, digest)
    print(json.dumps({"http_status": status, **payload}, sort_keys=True))
    return 0 if 200 <= status < 300 and payload.get("status") == "private_published" else 4


if __name__ == "__main__":
    raise SystemExit(main())
