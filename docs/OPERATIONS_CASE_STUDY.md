# Cloud operations case study: selecting, diagnosing and recovering a lab stack

## Problem and scope

A hypothetical analytics team needs a repeatable sales snapshot, authenticated read-only access and evidence that an operator can identify the correct database before changing services. This portfolio uses Python, PostgreSQL 16 and Docker Compose with synthetic business data.

The author deployed the service on a single AWS EC2 instance in an earlier trial. The new monitoring and preflight drills below were verified on the author's **Mac Docker lab**, not on EC2. CI uses a third environment: a disposable GitHub runner.

## What changed and why

| Observed operator problem | Implementation | Evidence |
|---|---|---|
| Running Git in a parent folder selected an unrelated repository | Keep source checkout separate from the active Compose folder; preflight checks explicit project/directory/volume identity | All 16 Mac preflight checks passed, 20 Oct |
| A live API process can coexist with an unavailable database | Probe liveness, database readiness and anonymous data rejection independently | During DB stop: 200 / 503 / 401 |
| A single transient error should be distinguished from repeated failure | First failed sample is watch; second consecutive failure becomes a local alert | watch at 10:28:26 UTC; alert at 10:28:28 UTC, 19 Oct |
| Restart success alone does not establish usable service/data | Run health, authenticated access and sales reconciliation after restart | Healthy recovery probe; six auth checks; unchanged sales aggregates |
| A successful manual demonstration can be hard to reproduce | Add tests and acceptance CI | 26 tests plus disposable-stack integration in run linked below |

## Operator workflow

1. Identify the active Compose directory and expected named database volume.
2. Run the read-only preflight against that existing directory.
3. Establish baseline health and validate actual auth/data through existing scripts.
4. For an agreed lab exercise, stop only the PostgreSQL service.
5. Observe readiness failure and local watch/alert output.
6. Start the same service on the retained volume, then recheck health, auth and data.
7. Record observations with environment and commit scope. Do not infer unmeasured recovery objectives.

The scripts do not deploy resources, send notifications, modify credentials, remove volumes or automatically restart anything.

## Environment and evidence matrix

| Environment | Verified | Not established by this evidence |
|---|---|---|
| AWS EC2, 13 Oct | API/database demo, auth, read-only access probes, synthetic snapshot; fresh-DB backup aggregate comparison and off-host checksum; author-reported stop/start recovery | New preflight/monitor drill on EC2, HA, public HTTPS, centralized monitoring, RTO/RPO |
| Mac Docker, 19 Oct | 12/12 healthy baseline; explicit DB-stop probe sequence 200/503/401 with watch/alert; separate recovery probe and auth/data checks | Continuous recorded alert-to-healthy transition, backup restoration in this drill |
| Mac Docker, 20 Oct | 16/16 preflight checks: required files/keys, matching project/directory, container state/health and expected data mount | Database contents, credential correctness, host security or EC2 verification |
| GitHub CI | Tests, disposable Docker integration, database failure/recovery | Health or configuration of the author's Mac/EC2 |

The post-recovery snapshot contained 150,600 sales rows, 1,931,506 units and 11,929,529,809 satang, spanning 2024-01-01 to 2026-09-30. Aggregate agreement is not row-by-row or complete database-object equivalence.

## Evidence links

- [Monitoring trial details](MONITORING_LAB.md): includes the first 30-sample attempt that captured no failure and was not counted as outage evidence.
- [Preflight design and Mac trial](PREFLIGHT_LAB.md).
- [Acceptance run 39356902071](https://github.com/Quetzel6/fmcg-cloud-foundation/actions/runs/39356902071): 26 tests and Docker acceptance for code commit `2fb7c90bf1a409e83a173d795931a0a162b8dd50`.
- [Monitor PR #1](https://github.com/Quetzel6/fmcg-cloud-foundation/pull/1).
- [Preflight PR #2](https://github.com/Quetzel6/fmcg-cloud-foundation/pull/2).
- [AWS runbook](AWS_RUNBOOK.md).

Tests use a temporary HTTP server for monitor behavior and simulated Docker metadata for preflight edge cases. The author additionally tested the actual existing Mac stack; these are different validation layers.

## Three-minute walkthrough

- **0:00–0:30 — requirement:** explain why the correct stateful stack must be identified before any operation.
- **0:30–1:15 — architecture:** API and database on one host, localhost binding, SSH tunnel and read-only reporting access; explain the shared failure domain.
- **1:15–2:00 — incident:** liveness stayed 200 while readiness became 503; 401 remained expected for anonymous data access. This localizes a symptom but does not by itself prove every possible root cause.
- **2:00–2:30 — recovery:** same service/volume restarted, actual auth/data checks passed. This is a restart drill, separate from backup restoration.
- **2:30–3:00 — next decision:** validate on EC2 before claiming cloud monitoring, and collect costs/requirements before choosing managed services or HA.

## Understanding checks

1. Why is HTTP 401 healthy for the anonymous protected-endpoint probe?
2. Why can preflight pass even if the application's dataset is incomplete?
3. What might a new Compose project name do to the named volume it selects?
4. Why is the approximately two-second spacing between failed samples not a measured end-to-end outage detection SLA?
5. Which tests were run by the author, which by CI, and where did AI-assisted implementation require personal review?

Answer using the evidence and limits above. Present personal lab work and AI assistance accurately; do not describe the exercise as paid consulting or production operations.
