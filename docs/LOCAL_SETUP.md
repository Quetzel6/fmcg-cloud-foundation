# Local setup from a fresh checkout

Requires Python 3.10+, Docker and Docker Compose. Use a new checkout and a dedicated project database. The loader below explicitly replaces this lab's synthetic snapshot; do not use it against a business database or an existing stack whose data must be retained. For existing stacks, use the [preflight guide](PREFLIGHT_LAB.md).

```bash
git clone https://github.com/Quetzel6/fmcg-cloud-foundation.git
cd fmcg-cloud-foundation
python3 -c 'import secrets; from pathlib import Path; p=Path(".env"); p.open("x").write("POSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n")'
python3 scripts_env_upgrade.py
python3 scripts_auth_setup.py
docker compose build api loader
docker compose up -d --wait postgres
docker compose run --rm --no-deps loader
docker compose up -d --wait api
python3 scripts_check.py
docker compose run --rm --no-deps -e ALLOW_DEMO_REPLACE=yes loader python scripts_ingest.py
python3 scripts_check_data.py
python3 scripts_check_auth.py
docker compose exec -T api python scripts_check_access.py
python3 -m unittest discover -s tests -v
```

The exclusive `.env` creation fails rather than overwriting existing secrets. Configuration helpers prepare the database URL and token. API access is localhost-only; the database has no published host port. Keep `.env` private.

These are the same build/load/auth/access operations exercised by the acceptance workflow. A local pass is not an AWS deployment result. The [AWS runbook](AWS_RUNBOOK.md) documents the separate deployment and its limits.

Stop a retained lab with `docker compose stop`. Retain its named volume if the data must persist. Do not use volume deletion as a routine restart procedure.
