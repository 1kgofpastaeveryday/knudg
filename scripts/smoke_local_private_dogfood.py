#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg"


def run_knudgctl(database_url, *args):
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "knudgctl.py"), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if not result.stdout:
        raise RuntimeError(result.stderr.strip() or f"knudgctl exited {result.returncode}")
    payload = json.loads(result.stdout)
    if result.returncode != 0:
        detail = payload.get("detail") or payload.get("error_class") or payload.get("status")
        raise RuntimeError(f"knudgctl {' '.join(args)} failed: {detail}")
    return payload


def seed_workspace(database_url):
    tenant_id = uuid.uuid4()
    namespace_id = uuid.uuid4()
    principal_id = uuid.uuid4()
    slug = f"local-private-{uuid.uuid4().hex}"
    with psycopg.connect(database_url, connect_timeout=3) as conn:
        with conn.transaction():
            conn.execute(
                "insert into tenants(id, slug, name) values (%s, %s, 'Local Private Dogfood')",
                (tenant_id, slug),
            )
            conn.execute(
                "insert into principals(id, principal_type, display_name) values (%s, 'human_user', 'Local Dogfood')",
                (principal_id,),
            )
            conn.execute(
                """
                insert into tenant_memberships(tenant_id, id, principal_id, membership_role, status, valid_from)
                values (%s, %s, %s, 'member', 'active', now() - interval '1 minute')
                """,
                (tenant_id, uuid.uuid4(), principal_id),
            )
            conn.execute(
                "insert into namespaces(tenant_id, id, key, name, visibility) values (%s, %s, 'local-private', 'Local Private', 'private')",
                (tenant_id, namespace_id),
            )
            conn.execute(
                """
                insert into namespace_grants(tenant_id, id, namespace_id, principal_id, grant_scope, status, valid_from)
                values (%s, %s, %s, %s, 'submit', 'active', now() - interval '1 minute')
                """,
                (tenant_id, uuid.uuid4(), namespace_id, principal_id),
            )
    return tenant_id, namespace_id, principal_id


def assert_decision(payload, expected):
    actual = payload["result"]["decision"]
    if actual != expected:
        raise RuntimeError(f"expected decision {expected}, got {actual}")


def main():
    parser = argparse.ArgumentParser(description="Run the local-private capture/search/revoke/purge smoke loop.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--card-input", default=str(ROOT / "fixtures" / "local-private-card.sample.json"))
    parser.add_argument("--task-profile", default=str(ROOT / "fixtures" / "local-private-task-profile.sample.json"))
    args = parser.parse_args()

    database_url = args.database_url
    tenant_id, namespace_id, principal_id = seed_workspace(database_url)

    preflight = run_knudgctl(database_url, "local", "preflight-db")
    if not preflight.get("local_private_schema_ready"):
        raise RuntimeError("local private schema is not ready")

    captured = run_knudgctl(
        database_url,
        "local",
        "capture",
        "--tenant",
        str(tenant_id),
        "--namespace",
        str(namespace_id),
        "--created-by",
        str(principal_id),
        "--input",
        args.card_input,
    )
    card_id = captured["card_id"]

    found = run_knudgctl(
        database_url,
        "local",
        "search",
        "--tenant",
        str(tenant_id),
        "--namespace",
        str(namespace_id),
        "--principal",
        str(principal_id),
        "--task-profile",
        args.task_profile,
    )
    assert_decision(found, "cards_found")

    audit = run_knudgctl(
        database_url,
        "local",
        "audit-boundary",
        "--tenant",
        str(tenant_id),
        "--principal",
        str(principal_id),
    )
    if not audit.get("local_private_publication_boundary_clear"):
        raise RuntimeError("local private publication boundary is not clear")

    revoked = run_knudgctl(
        database_url,
        "local",
        "revoke",
        "--tenant",
        str(tenant_id),
        "--namespace",
        str(namespace_id),
        "--principal",
        str(principal_id),
        "--card-id",
        card_id,
        "--reason",
        "local private smoke revoke",
    )
    if not revoked.get("revoked"):
        raise RuntimeError("local private revoke did not affect the captured card")

    hidden = run_knudgctl(
        database_url,
        "local",
        "search",
        "--tenant",
        str(tenant_id),
        "--namespace",
        str(namespace_id),
        "--principal",
        str(principal_id),
        "--task-profile",
        args.task_profile,
    )
    assert_decision(hidden, "no_suggestion")

    purged = run_knudgctl(
        database_url,
        "local",
        "purge",
        "--tenant",
        str(tenant_id),
        "--namespace",
        str(namespace_id),
        "--principal",
        str(principal_id),
        "--card-id",
        card_id,
        "--reason",
        "local private smoke purge",
    )
    if not purged.get("purged"):
        raise RuntimeError("local private purge did not affect the captured card")

    fences = run_knudgctl(
        database_url,
        "local",
        "verify-fences",
        "--tenant",
        str(tenant_id),
        "--card-id",
        card_id,
        "--principal",
        str(principal_id),
    )
    if fences["active_search_documents"] != 0 or fences["active_bodies"] != 0 or fences["purged_bodies"] != 1:
        raise RuntimeError("local private fences did not settle after purge")

    print(
        json.dumps(
            {
                "schema_version": "local-private-dogfood-smoke-v0",
                "ok": True,
                "tenant_id": str(tenant_id),
                "namespace_id": str(namespace_id),
                "card_id": card_id,
                "capture_status": captured["status"],
                "initial_search_decision": found["result"]["decision"],
                "post_revoke_search_decision": hidden["result"]["decision"],
                "purged_bodies": fences["purged_bodies"],
                "publication_enabled": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
