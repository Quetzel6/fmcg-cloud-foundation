# Backup restore drill: recover data and API permissions

## Selected gap and current system

This is a personal Data Engineering lab with synthetic data, a Python HTTP API,
PostgreSQL 16 and Docker. It has one database and no standby. The most consequential
gap was recovery verification: restarting retained storage was automated, but the
historical restore evidence compared only sales aggregates and did not test API
permissions on the restored database.

The new `scripts_recovery_drill.py` exercises the existing generator, loader, API
and access scripts against a new isolated database. It adds no cloud services and
does not change application behavior.

| Path / control | What the current repository implements | Evidence and boundary |
|---|---|---|
| Start | Compose waits for PostgreSQL; API has a liveness Docker healthcheck | Existing acceptance workflow; a healthy API container alone does not prove usable data |
| Liveness | `/health/live` checks the HTTP process | Real HTTP probes in the new drill |
| Readiness | `/health/ready` performs `SELECT 1` as the API login | Remains 200 when sales is missing or SELECT is denied; connectivity only |
| Data health | Authenticated `/health/data` queries sales, requires a nonempty snapshot | New drill detects both missing sales and missing restored grants as 503; not wall-clock freshness |
| Authorization | Bearer token for data routes; API DB login has sales SELECT only | Real 401 probes and existing seven permission-denial probes before and after restore |
| Detect DB outage | `scripts_monitor.py` checks live/ready/anonymous 401, with watch/alert states | Existing unit tests and historical Mac drill; does not query authenticated data and therefore misses this data-loss scenario |
| Restart | Existing CI stops/starts PostgreSQL on retained storage | New drill additionally shows restarting cannot reconstruct a missing table |
| Restore | Custom-format `pg_dump`, transactional `pg_restore`, then separate role/grant provisioning | New local drill, complete table fingerprints and real API/permission probes on the restored database |
| AWS | Historical author-supplied EC2 evidence described in README | This new recovery drill: **ยังไม่ได้ทดสอบบน AWS** (not tested on AWS) |
| Backups and alerts | Manual historical backup/off-host checksum and bounded local monitor | No scheduled backups, independent backup storage, retention policy, external alert delivery or automatic failover implemented |

`verification.json` is historical metadata, not a current test runner result.
The workflow file defines CI checks; editing it is not proof a remote CI run passed.

## Run safely on your machine

Prerequisites: Python 3.10+, Docker Engine with Linux containers, and enough local
disk for a temporary synthetic snapshot and dump (allow about 1 GiB). Docker access
is an administrator-level boundary. No AWS credentials, `.env`, existing Compose
stack, or Python host packages are needed by this drill.

From this checkout:

```bash
docker pull postgres:16
docker build -t fmcg-recovery-app .
python3 -m unittest discover -s tests -v
mkdir -p backups
python3 scripts_recovery_drill.py --image fmcg-recovery-app --output backups/recovery-01.json
```

Use a **new** output filename for every run. Existing evidence is never overwritten.
The runner rejects an image whose bundled application/pipeline files do not match
this checkout, and records immutable image IDs. Docker build must retain normal TLS
verification; proxy-based cloud workers need the platform's CA build-secret setup.
The recorded cloud-worker trial reused a cached image and verified its bundled
source hashes; it does not claim a fresh image build in this trial.

The runner creates only new random `fmcg-recovery-*` resources: an internal Docker
network, a named volume, a PostgreSQL container, API and short-lived jobs. It
publishes no host ports. SQL and fault injection address only container IDs returned
by its own create calls. There is no caller-supplied DSN, container, volume or
existing-stack target. Fresh random credentials are held in mode-0600 temporary
files under ignored `.env.recovery-*`; it never reads the existing `.env`.

It removes its own containers, volume, network, credentials and dump on normal exit
or a handled failure. Evidence remains. A failed check or incomplete cleanup returns
nonzero, including a failed loader container even when `docker start -a` returns 0.
SIGKILL, host/Docker failure or interruption during resource creation can leave
resources. Inspect only the run's `fmcg.recovery.run` label/run_id and remove those
specific resources; never use global prune or `compose down -v` on an existing lab.

## Scenario, signals and actual recovery steps

The runner performs the following operations automatically on its own resources.
The command forms below explain the procedure; **do not substitute a live database**.

1. Start fresh PostgreSQL; run `scripts_access_setup.py`, then the existing
   `scripts_ingest.py` with `ALLOW_DEMO_REPLACE=yes` in the isolated loader.
   Start the nonroot API with a read-only filesystem, dropped capabilities and a token.
2. Establish baseline: live/ready/data/summary 200; missing/wrong token 401;
   `scripts_check_access.py` passes SELECT plus seven denied operations.
   Capture table inventory, row counts and deterministic content MD5 fingerprints
   for every table in `fmcg` and `truth` (13 nonempty tables).
3. Create a custom-format backup using `pg_dump -Fc --no-owner --no-acl`; record its
   SHA-256. Only then inject `DROP TABLE fmcg.fact_sales_daily CASCADE` in the new lab.
   Sales reporting and dependent views are unavailable; other tables remain stored.
   Expected signal: live **200**, ready **200**, authenticated data/summary **503**,
   anonymous/wrong-token summary **401**. A monitor of liveness alone misses this.
4. Restart that PostgreSQL and API. The same 503 demonstrates that service restart
   preserves the data loss; it is not a substitute for restore.
5. Restore the dump with `pg_restore --clean --if-exists --no-owner --no-acl
   --single-transaction --exit-on-error`. This replaces objects only in the disposable
   database. Any SQL error fails the restore transaction and the drill.
6. Compare all 13 table inventories/counts/fingerprints. At this point authenticated
   data is still **503**: backups explicitly omit ACLs, so identical data alone does
   not establish that the reporting login can use it.
7. Run `scripts_access_setup.py` as the dedicated lab owner to reapply API role
   restrictions and sales grants. Run `scripts_check_access.py` using the actual
   API login, then HTTP probes. Data/summary must return **200**, aggregates must
   equal baseline, and all seven denied operations must still be denied.
8. Remove only the newly created lab resources. Require cleanup success.

Success is not a PID, open port or zero-test run. It requires the expected failure
signals, successful transactional restore, identical nonempty table contents,
restored authenticated reporting, retained permission denials and successful cleanup.

## Current local evidence

Two independent local runs are retained without overwriting either output:

- [Original evidence](recovery_evidence.json): 27 October 2026,
  08:01:30–08:03:10 UTC (15:01:30–15:03:10 Bangkok).
- [Pre-PR rerun](recovery_evidence_review.json): the new run's exact UTC start/finish
  is recorded in that JSON. The validation commands and timing are reported in the PR.

Both JSON files record the base Git revision
`fb365c18bf0bde1fc809ea53471e10a6dd1376d8`, which is the checkout HEAD at execution,
**not the eventual feature commit**. The drill was an uncommitted working-tree
addition at execution. Its exact SHA-256 is
`11d668c58e7b919bb345c1684fefe21378d475597553576a64daaf218267a086`.
Each run also identifies the bundled application manifest SHA-256 and immutable
image IDs. README, runbook, tests, workflow and evidence are not covered by the
application manifest; the original run does not validate later edits to those files.
The pre-PR rerun and full 36-test suite run after the final source/documentation
edits; the new JSON is a generated result. Committing these results does not change
which source the recorded run exercised. Neither JSON claims a final commit or
remote CI execution that had not happened when it was generated.

| Stage | Live | DB readiness | Authenticated data/summary | Anonymous / wrong token |
|---|---:|---:|---:|---:|
| Baseline | 200 | 200 | 200 | 401 / 401 |
| Sales table lost | 200 | 200 | 503 | 401 / 401 |
| PostgreSQL + API restarted | 200 | 200 | 503 | 401 / 401 |
| Backup restored, grants not reapplied | 200 | 200 | 503 | 401 / 401 |
| Grants reprovisioned and permissions checked | 200 | 200 | 200 | 401 / 401 |

Before and after: 150600 sales rows, 1931506 units, 11929529809 satang,
2024-01-01 through 2026-09-30. All 13 table row counts and content fingerprints
match. The local original Compose stack is separate and was left healthy; its
existing authentication/data checks also passed after the drill.

Baseline unit suite in this round: 26 passed. With recovery tests: 36 passed.
The new tests cover content changes with unchanged counts, missing/empty tables,
raw-error suppression, cleanup continuing after failure, stale-image refusal,
no evidence overwrite, volume ownership refusal, actual job exit status, and failure exit/evidence status. The actual Docker drill
runs separately from unit tests. CI now invokes it and uploads only its sanitized
JSON; **the changed remote workflow has not been executed in this round**.

## Limits and security boundaries

- This simulates loss of a sales table in a newly generated, idle synthetic database,
  then restores in the same isolated PostgreSQL cluster. It is not a failed-disk,
  lost-volume, fresh-host, cloud-account or whole-cluster/role recovery test.
- All rows in the 13 tables are included in deterministic content fingerprints;
  MD5 here detects accidental differences, not malicious tampering. Matching
  fingerprints are not a formal byte-for-byte proof. Constraint/index/view/sequence
  definitions are restored by PostgreSQL, but are not independently exhaustively
  compared. The backup SHA-256 identifies this run's temporary archive.
- The dump is made while the generated lab is idle. This does not demonstrate
  concurrent-writer cutover, recovery of writes made after the backup, PITR/WAL
  archiving, encrypted/off-host backups, retention or disaster recovery.
- No RTO/RPO commitment or production performance measurement is established.
  Timestamps describe this run, not a service objective.
- `.env` access and Docker administration remain privileged. Bearer auth is shared
  secret access, not per-user IAM; the standalone server retains optional no-token
  compatibility. Compose and this drill require a token. The API is a demo stdlib
  server; no public HTTPS, centralized monitoring or high availability is claimed.
- JSON includes synthetic aggregate values, counts, fingerprints and safe statuses,
  never DSNs, tokens, passwords, raw database rows, Docker inspect environments or
  raw subprocess errors. Do not upload dumps, environment files or raw debug logs.

## Resume wording (personal lab)

- Built a reproducible PostgreSQL backup/restore drill for a synthetic sales pipeline,
  validating row counts and content fingerprints across 13 tables plus API results
  after simulated sales-table loss.
- Verified recovery of authenticated reporting and read-only database boundaries
  using real HTTP checks and seven permission-denial probes in isolated Docker labs.
