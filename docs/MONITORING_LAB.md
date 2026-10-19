# Bounded monitoring and outage investigation lab

Status: monitoring code has five local automated tests (including a temporary real HTTP server). **No claim of new Docker/EC2 drill completion yet.** Existing Docker/EC2 evidence in README remains separate.

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
