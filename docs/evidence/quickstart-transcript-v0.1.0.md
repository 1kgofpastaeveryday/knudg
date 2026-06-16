# Clean-Machine Quickstart Transcript — v0.1.0

Recorded 2026-06-16 00:28 UTC in a fresh Ubuntu 24.04.4 LTS container with
no prior Knudg state. The container was provisioned with Node 20.20.2,
Python 3.12.3, and PostgreSQL 16.14 (with pgvector).

The README quickstart uses `docker compose up -d postgres` which provisions
the pgvector/pgvector:pg16 image automatically. This transcript uses a bare
Postgres install with `postgresql-16-pgvector` added manually to match.

## Environment

```
Ubuntu 24.04.4 LTS (Noble Numbat)
Node v20.20.2
Python 3.12.3
PostgreSQL 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)
pgvector extension from postgresql-16-pgvector
```

## Step 1: Clone

```
$ git clone --branch v0.1.0 --depth 1 https://github.com/1kgofpastaeveryday/knudg.git
Cloning into '/workspace/knudg'...
```

## Step 2: Install Node dependencies

```
$ npm install
(148 packages installed)
```

## Step 3: Install Python dependencies

```
$ npm run setup:python
Successfully installed annotated-doc-0.0.4 anyio-4.14.0 attrs-26.1.0
certifi-2026.5.20 charset_normalizer-3.4.7 click-8.4.1 fastembed-0.8.0
filelock-3.29.4 flatbuffers-25.12.19 fsspec-2026.4.0 h11-0.16.0
hf-xet-1.5.1 httpcore-1.0.9 httpx-0.28.1 huggingface-hub-1.19.0
idna-3.18 iniconfig-2.3.0 jsonschema-4.26.0
jsonschema-specifications-2025.9.1 loguru-0.7.3 markdown-it-py-4.2.0
mdurl-0.1.2 mmh3-5.2.1 numpy-2.4.6 onnxruntime-1.27.0 packaging-26.2
pillow-12.2.0 pluggy-1.6.0 protobuf-7.35.1 psycopg-3.3.4
psycopg-binary-3.3.4 py-rust-stemmers-0.1.8 pygments-2.20.0 pytest-9.1.0
pyyaml-6.0.3 referencing-0.37.0 requests-2.34.2 rich-15.0.0
rpds-py-2026.5.1 shellingham-1.5.4 tokenizers-0.23.1 tqdm-4.68.2
typer-0.25.1 typing-extensions-4.15.0 urllib3-2.7.0
```

## Step 4: Start Postgres and create database

```
$ pg_ctlcluster 16 main start
$ sudo -u postgres psql -c "CREATE USER knudg_migration WITH PASSWORD 'knudg_migration' SUPERUSER;"
CREATE ROLE
$ sudo -u postgres psql -c "CREATE DATABASE knudg OWNER knudg_migration;"
CREATE DATABASE
```

Note: the README quickstart uses `docker compose up -d postgres` which
handles user, database, and pgvector provisioning automatically via the
pgvector/pgvector:pg16 image.

## Step 5: Run migrations

```
$ DATABASE_URL="postgresql://knudg_migration:knudg_migration@localhost:5432/knudg" \
  npm run py -- scripts/migrate.py up
(completed with no errors)
```

## Step 6: Run tests

```
$ npm test

tests/test_knudg_closed_api.py ............................s....         [ 55%]
tests/test_knudg_live_agent.py ......                                    [ 66%]
tests/test_task_profile_schema.py ........                               [ 79%]
tests/test_knudg_client_config.py ............                           [100%]

======================== 58 passed, 1 skipped in 17.50s ========================
```

## Step 7: Public release hygiene

```
$ npm run public:release-check
Public release validation passed.
```

## Step 8: CLI status (offline)

```
$ KNUDG_OPERATOR_TOKEN="dev-local-token" npm run knudgctl -- server status
{"ok": false, "status": "not_configured", "profile": "cloud",
 "detail": "cloud custom server support is reserved for a later enterprise/auth phase."}
```

Expected: the server is not running in this offline transcript. The CLI
confirms it can parse the command and report status.

## Result

All quickstart steps completed successfully on a clean machine. 58 tests
passed, 1 skipped (database integration test gated on running server),
public release validation passed.
