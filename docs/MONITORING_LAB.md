# Bounded monitoring and outage investigation lab

Status: five monitor tests passed locally; GitHub acceptance run 39231105225 passed for monitor code commit 478de9afb42d0263fb913854f49edc2aa2ea160e. The author completed a Mac Docker baseline and explicit PostgreSQL stop/start drill on 19 October 2026, summarized below. No new EC2 monitoring drill is claimed.

## What is checked

- `/health/live` must return 200: process reachable.
- `/health/ready` must return 200: existing application readiness is database connectivity only, not dataset completeness.
- `/analytics/sales-summary` WITHOUT a token must return 401: access guard still rejects anonymous data access.

401 is expected, not an outage. This monitor does not inspect authenticated data, database permissions, disk space or backup validity; use the existing scripts_check_auth.py and scripts_check_data.py separately. It is local active probing, not CloudWatch, external uptime monitoring, paging or high availability. Latencies are observed request times, not a performance benchmark. The state `alert` is printed/written locally; no notification is sent.

Two consecutive failed samples produce `alert`; one failed sample produces `watch`; a healthy sample resets to `healthy`. Exit status is 1 if ANY sample failed, even when recovery occurred later, and 0 only if the entire observation window passed. HTTP redirects are not followed and proxy environment variables are bypassed. No tokens, headers or response bodies are printed.

## Baseline on Mac

In the existing fmcg-cloud-foundation checkout with the existing .env and retained volumes:

```bash
python3 -m unittest discover -s tests -p 'test_monitor.py' -v
docker compose ps
python3 scripts_monitor.py
```

For a recording, use a NEW filename each time (existing files are rejected):

```bash
python3 scripts_monitor.py --samples 12 --interval 5 --output /tmp/fmcg-monitor-baseline-01.jsonl
```

The bounded session lasts approximately 55 seconds plus request times. Ctrl+C stops it; it makes no changes to application services.

For an EXISTING working EC2 SSH tunnel on Mac port 18080:

```bash
python3 scripts_monitor.py --base-url http://127.0.0.1:18080
```

No AWS provisioning or remote service changes are performed by the monitor. If EC2 is stopped or the tunnel is absent, connection failures are expected, not proof of an application defect. Confirm tunnel and instance state before investigating the database.

## Optional disposable-lab database outage drill

Run only against your own lab stack during an agreed interruption window, with no other work depending on it. Do not run docker compose down -v or remove volumes. This drill causes temporary unavailability; it does NOT test restoring data from backup.

Terminal A, recording a NEW file:

```bash
python3 scripts_monitor.py --samples 24 --interval 2 --output /tmp/fmcg-monitor-db-drill-01.jsonl
```

Terminal B, same repository and Compose project:

```bash
docker compose stop postgres
```

Watch Terminal A for readiness failure and local watch/alert state. **Always start the database again**, including if the monitor exits or you interrupt it:

```bash
docker compose start postgres
docker compose ps
python3 scripts_monitor.py
python3 scripts_check_auth.py
python3 scripts_check_data.py
```

Wait for database health and repeat the final checks if startup is still in progress. The monitor does not force a required liveness result during outage; depending on the single-thread demo server and database connection timeout, other requests may also be delayed. Record actual observations rather than assuming live always stays 200. If sampling ends before recovery, start a new recording; do not edit incident lines to make it look successful.

## Explain the incident

1. Establish baseline and note UTC timestamps.
2. Check process reachability, readiness and auth guard separately.
3. Compare DB container status/logs and host/tunnel state. Logs can contain private connection details; review locally before publishing.
4. Start the stopped DB and recheck authenticated data through existing tools.
5. Report what failed, what was restored, which checks passed and what remains untested.

Do not report sample intervals as actual RTO/RPO. Polling only bounds observed detection/recovery and this drill has no controlled loss of writes. Auth 401 alone is not proof of full authorization correctness.

## Portfolio acceptance

Before adding a monitoring deployment claim: run baseline and drill, provide sanitized status/timestamp evidence, confirm recovered data/auth checks and link the exact commit/CI run. Local tests are not EC2 evidence. Continue to describe this as a single-host personal lab.

## Author-provided Mac Docker evidence — 19 October 2026

The author ran the pinned monitor from commit `478de9afb42d0263fb913854f49edc2aa2ea160e` against the existing Compose stack. Terminal transcripts were supplied in the project conversation; no secrets or raw desktop screenshots are committed.

| Phase | Observed result (UTC) |
|---|---|
| Baseline | 12/12 healthy, 10:12:31 through 10:13:26; live 200, ready 200, anonymous summary 401 |
| First timed attempt | 30/30 healthy; did not capture an outage, so not counted as outage-detection evidence |
| Explicit DB stop | `docker compose stop postgres`; subsequent Compose listing showed only API running |
| First failed sample | 10:28:26.078157: live 200, ready 503, anonymous summary 401; watch |
| Second failed sample | 10:28:28.099194: same statuses; alert after two failures |
| Third failed sample | 10:28:30.117689: same statuses; alert |
| Restart and independent recovery probe | `docker compose start postgres`; at 10:29:11.189893 live 200, ready 200, anonymous summary 401; healthy |
| Post-recovery auth | All six existing auth probes passed, including valid-token data access |
| Post-recovery data | 150600 rows; quantity 1931506; amount_satang 11929529809; dates 2024-01-01 through 2026-09-30 |

Recovery was observed in a separate monitor invocation, so this transcript does not prove a continuous in-process alert-to-healthy transition. That reset behavior is covered by automated tests. Stop/start timestamps were not instrumented: no RTO, RPO or guaranteed detection time is inferred. Data checks reconcile summary aggregates, not every row or database object. This was restart on the existing volume, not backup restoration.

The accompanying Docker Desktop screenshot showed a different container (`fmcg-postgres`, postgres:latest), so it is not used as evidence for the Compose postgres:16 drill. The terminal transcript identifies the tested Compose service. GitHub CI runs on a disposable runner and does not attest EC2 health.
