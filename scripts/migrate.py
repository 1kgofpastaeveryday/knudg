#!/usr/bin/env python3
import argparse
import hashlib
import os
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


def migration_pairs():
    ups = sorted(MIGRATIONS.glob("*.up.sql"))
    for up in ups:
        version = up.name.removesuffix(".up.sql")
        down = MIGRATIONS / f"{version}.down.sql"
        yield version, up, down if down.exists() else None


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connect():
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://knudg_migration:knudg_migration@localhost:54329/knudg",
    )
    return psycopg.connect(url, autocommit=False)


def ensure_schema_table(conn):
    conn.execute(
        """
        create table if not exists schema_migrations (
          version text primary key,
          checksum text not null,
          state text not null,
          started_at timestamptz not null default now(),
          finished_at timestamptz null,
          step text null,
          error_class text null,
          check (state in ('applying', 'applied', 'rolling_back', 'rolled_back', 'failed'))
        )
        """
    )
    conn.commit()


def apply_all():
    with connect() as conn:
        ensure_schema_table(conn)
        for version, up, _down in migration_pairs():
            digest = checksum(up)
            row = conn.execute(
                "select checksum, state from schema_migrations where version = %s",
                (version,),
            ).fetchone()
            if row:
                if row[0] != digest:
                    raise SystemExit(f"checksum mismatch for applied migration {version}")
                if row[1] == "applied":
                    continue
                raise SystemExit(f"migration {version} is in state {row[1]}")

            try:
                conn.execute(
                    """
                    insert into schema_migrations(version, checksum, state, started_at, step)
                    values (%s, %s, 'applying', now(), 'up')
                    """,
                    (version, digest),
                )
                conn.execute(up.read_text(encoding="utf-8"))
                conn.execute(
                    """
                    update schema_migrations
                    set state = 'applied', finished_at = now(), step = null, error_class = null
                    where version = %s
                    """,
                    (version,),
                )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                conn.execute(
                    """
                    insert into schema_migrations(version, checksum, state, started_at, finished_at, step, error_class)
                    values (%s, %s, 'failed', now(), now(), 'up', %s)
                    on conflict (version) do update
                    set state = 'failed', finished_at = now(), step = 'up', error_class = excluded.error_class
                    """,
                    (version, digest, exc.__class__.__name__),
                )
                conn.commit()
                raise


def rollback_all():
    with connect() as conn:
        ensure_schema_table(conn)
        for version, _up, down in reversed(list(migration_pairs())):
            row = conn.execute(
                "select state from schema_migrations where version = %s",
                (version,),
            ).fetchone()
            if not row or row[0] != "applied":
                continue
            if down is None:
                raise SystemExit(f"migration {version} has no down file")
            conn.execute(
                "update schema_migrations set state = 'rolling_back', step = 'down' where version = %s",
                (version,),
            )
            conn.execute(down.read_text(encoding="utf-8"))
            conn.execute("delete from schema_migrations where version = %s", (version,))
            conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Apply or roll back Knudg SQL migrations.")
    parser.add_argument("command", choices=["up", "down"])
    args = parser.parse_args()
    if args.command == "up":
        apply_all()
    else:
        rollback_all()


if __name__ == "__main__":
    main()
