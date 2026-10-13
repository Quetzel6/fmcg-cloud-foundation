# Phase 3 — separate API database permissions

## Existing-install migration
Copy the release over the existing directory, excluding .env. Preserve the existing volume and POSTGRES_PASSWORD. From the existing cloud-foundation directory:

```bash
python3 scripts_env_upgrade.py
docker compose config --quiet
docker compose build api loader
docker compose run --rm --no-deps loader
docker compose up -d api
python3 scripts_check.py
python3 scripts_check_data.py
docker compose exec api python scripts_check_access.py
```
Postgres must already be running and healthy before the no-deps setup. If it is stopped, run `docker compose up -d postgres` and wait for healthy. API password is generated locally, never bundled. Existing data are not replaced by setup. The setup transaction creates or updates the dedicated role, removes memberships, grants database CONNECT, schema USAGE and SELECT on only fmcg.fact_sales_daily. It removes PUBLIC CREATE and TEMPORARY rights for this disposable database and PUBLIC CREATE on schema public. No other database is modified.

## Repeat snapshot loading
The old `docker compose exec ... api python scripts_ingest.py` command is retired. The API no longer has database-owner credentials. Use:

```bash
python3 scripts_check_data.py > /tmp/fmcg-phase3-before.jsonl
docker compose run --rm --no-deps -e ALLOW_DEMO_REPLACE=yes loader python scripts_ingest.py
python3 scripts_check_data.py > /tmp/fmcg-phase3-after.jsonl
diff -u /tmp/fmcg-phase3-before.jsonl /tmp/fmcg-phase3-after.jsonl
docker compose exec api python scripts_check_access.py
```
The loader drops and recreates the snapshot schemas; an optional callback reapplies SELECT grants before the same transaction commits. If granting fails, the snapshot replacement rolls back. Loader source modification and hashes are in pipeline/SOURCE.json. Do not run ingest before access setup. Keep the loader privileged only in this disposable local lab; a narrowly scoped deployment/migration role is future work.

## Expected permission checks
sales_select and all seven denial probes report passed. The checks use the API's real login and rollback each probe. UPDATE, INSERT and DELETE use zero-row statements; CREATE probes and SET ROLE are rolled back if unexpectedly allowed and the test fails. Readiness stays connectivity-only; data health checks queryability, not wall-clock freshness.

## Boundaries
API has no admin DATABASE_URL or API_DB_PASSWORD environment variable; it has its own password within DATABASE_URL. Local Docker access and .env access remain powerful. This is database privilege separation, not a credential vault or cloud IAM implementation. The image contains loader code but the API does not have loader credentials. API remains localhost-only. No TLS, public deployment or production-readiness claim.
