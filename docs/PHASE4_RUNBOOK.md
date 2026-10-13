# Phase 4: local authentication preparation

Azure deployment is blocked pending Microsoft case 2610090030001261. This release creates no Azure resources. It is not a cloud deployment.

## Apply on Mac

Extract the Phase4 ZIP in Downloads, then copy the cloud-foundation folder contents into the existing project, excluding `.env`, `backups/`, and local generated data. Keep all existing database credentials and volumes. Do not run `docker compose down -v`.

From the existing project directory:

```bash
python3 scripts_auth_setup.py
docker compose up --build -d
python3 scripts_check.py
python3 scripts_check_auth.py
python3 scripts_check_data.py
python3 -m unittest discover -s tests -v
```

The authorization checker expects the existing synthetic snapshot to be loaded and PostgreSQL ready. It verifies live/ready 200 without a token, data 401 without a token, summary 401 with a wrong token, and both data endpoints 200 with a valid token. Exact sales aggregates must remain 150600 rows, 1931506 units, 11929529809 satang. It reads the token privately from `.env`; never paste it into screenshots or commit `.env`.

## Behavior and limits

Compose requires API_AUTH_TOKEN. The standalone Python server retains no-token local compatibility when the environment variable is absent; any future cloud deployment must explicitly require a nonempty secret. Only `/health/data` and `/analytics/sales-summary` require a Bearer token; `/health/live`, `/health/ready`, and root metadata remain public. Authorization is checked before querying data. Health readiness remains database connectivity only. Tokens are compared using constant-time comparison, duplicate Authorization headers are rejected, and headers/tokens are not logged.

This is shared-secret demo authorization, not individual identity, OAuth, Entra integration, rate limiting, or production readiness. Remote traffic must use HTTPS. The stdlib HTTP server is a demo server and needs review or replacement before production exposure.

## Azure next stage

After Microsoft confirms the restriction is lifted, retry Resource Group creation. Before creating paid services, validate current regional pricing and quota, decide API hosting and PostgreSQL networking, adapt the loader/role provisioning for managed PostgreSQL (the current lab uses a superuser), and add HTTPS, secret injection, bounded scaling, deployment validation and cleanup instructions. Do not deploy the current Compose stack directly with public PostgreSQL access. Budget alerts are not a hard spending cap.

## Evidence

User terminal evidence: API database role denial checks passed; reload aggregates matched; restored sales aggregate matched original. Restore verification covers the sales aggregate only, not full table contents or role/ACL recovery. Local automated HTTP tests use database stubs; real Docker acceptance must run on the user's Mac. Azure deployment and GitHub CI have not run for this release.
