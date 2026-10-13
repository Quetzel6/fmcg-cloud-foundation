# Project specification and evidence plan

## Customer problem
A hypothetical FMCG analyst needs a repeatable way to operate a synthetic analytics pipeline and identify database connectivity failures. The consultant must document requirements, deployment, security boundaries, troubleshooting and cost trade-offs.

## Phase 1 — current local foundation
Client on localhost -> HTTP API container -> PostgreSQL 16 on the internal Compose network -> persistent Docker volume. No business data routes. No externally reachable service. Structured status/duration logs omit request URLs and credentials. Liveness and readiness are separate.

Acceptance: build and start using README; ready returns 200; stopped database produces 503 without failing liveness; restart recovers; unknown route returns 404; no host database port. Automated CI checks the real database drill. Local unit tests alone do not establish this acceptance.

## Phase 2 — FMCG integration, implementation delivered; database acceptance pending
Source file hashes are recorded in pipeline/SOURCE.json. The existing generator and transactional loader are vendored without changes. The ingest job and aggregate API are implemented. Add schema-level readiness, restricted database runtime role, idempotent loads, reconciliation, failure handling and a read-only aggregate API. Keep the existing release independently reproducible. Avoid copying internship/customer data into the project.

## Phase 3 — one real cloud provider
Provider remains pending: AWS Academy access and permitted services first; Azure for Students as fallback. Academy restrictions may prevent IAM roles, Terraform or managed services. Record actual restrictions before selecting architecture. Use a provider-specific implementation only after account eligibility is known.

Design evidence: architecture and network diagram, security/access matrix, credential rotation procedure, service pricing estimate by region and runtime hours, deployment/teardown instructions. Treat USD50–100 as total project budget until clarified. Budget alerts are notifications, not a guaranteed hard spending cap.

Acceptance: actual deployment; HTTPS; least-privilege access; operational monitoring; tested backup/restore and rollback; screenshots/logs with secrets removed; resource inventory and teardown verification. Do not claim production readiness from a successful lab.

## Interview evidence
Prepare a 5-minute demo and a 10-minute technical explanation. Explain why readiness differs from liveness, how container DNS works, why the database is not exposed, what persists after shutdown, and what a disconnected database does. Candidate must independently reproduce one failure and explain the fix.

## Schedule
Use the first implementation cycle for local acceptance, then pipeline integration. Estimate cloud work after account restrictions and chosen services are known. Eight available hours/day is capacity, not a guaranteed completion date.

## Phase 3 permission separation
Implemented dedicated fmcg_api LOGIN, restricted SELECT, loader tools profile, repeat-load grant callback and real-login permission probes. Unit tests run locally; real PostgreSQL permission acceptance pending user execution. Cloud deployment remains pending.
