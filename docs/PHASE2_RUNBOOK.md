> Historical Phase 2 commands. For Phase 3 use PHASE3_RUNBOOK.md; API ingest commands below no longer apply.

# Phase 2 — synthetic FMCG integration

This is an extension of the existing validated generator/loader, not a second invented dataset. Vendored source hashes are recorded in pipeline/SOURCE.json. The loader validates DQ-01..17 and performs transactional reconciliation before commit. It replaces fmcg and truth schemas inside the dedicated demo database; never point DATABASE_URL at a real or shared database.

## Update safely
Extract this release into a separate temporary folder, then copy its contents (including hidden files) over the existing cloud-foundation directory. Keep your existing .env unchanged. Do not generate another password. Keep using the same directory and Compose project name so the existing volume is used.

## Build and verify connectivity
```bash
docker compose up --build -d
python3 scripts_check.py
```
Before the first ingest, run `python3 scripts_check_data.py --unloaded`: both data endpoints must return 503 even when connectivity readiness is 200. Do not use --unloaded after a successful ingest.

## Generate, validate and load
```bash
docker compose exec -e ALLOW_DEMO_REPLACE=yes api python scripts_ingest.py
python3 scripts_check_data.py
```
Generation may take several minutes and uses memory for the full synthetic scenario. Output must show status committed, data_quality passed, post_load status passed. Amounts are integer satang; the aggregate SO endpoint returns strings for exact large numeric values. Dates describe the historical synthetic dataset, not wall-clock freshness.

## Repeat-load evidence
Save output from `scripts_check_data.py`, repeat ingest, then compare counts, quantities, amounts and date bounds. They must match. This is deterministic full snapshot replacement, not incremental CDC. Existing transactional loader protects against partial commits; no new cloud rollback verification is claimed.

## Failure and recovery
Stop postgres, then run `scripts_check.py --database-down` and `scripts_check_data.py --unloaded`. Both data routes should return 503. Restart postgres, wait until healthy, then run both check scripts normally. Data should persist; no ingest is required after an ordinary restart.

## Security boundaries and incomplete work
The API uses fixed SQL and read-only transactions but still connects with the demo database owner. A dedicated least-privilege runtime role is outstanding. Do not expose this HTTP service to the Internet: HTTPS, authentication, cloud IAM, secret management and monitoring alerts remain deployment work. Business Inventory/Orders APIs are not implemented. Host-side check scripts use Python 3.10+, pipeline runtime uses Python 3.13 in Docker.
