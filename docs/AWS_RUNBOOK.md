# AWS demo operations runbook

Commands are intentionally separated by execution location. Replace PUBLIC_IP with the current EC2 public IPv4; replace the key path if yours differs. Private hostname ip-172-31-30-24 is not the address used from Mac.

## Resume work
In AWS Console: Singapore → EC2 → existing fmcg-cloud-dev → Start instance, if Stopped. Wait for Running and passing status checks. Read the current public IPv4. If your internet network changed, update the existing SSH inbound rule to My IP; do not open SSH to all addresses.

On Mac:
```bash
ssh -i "$HOME/Downloads/fmcg-cloud-dev-key.pem" -o IdentitiesOnly=yes ubuntu@PUBLIC_IP
```
On Ubuntu:
```bash
cd /home/ubuntu/cloud-foundation
sudo docker compose up -d --wait
python3 scripts_check.py
python3 scripts_check_data.py
python3 scripts_check_auth.py
sudo docker compose exec api python scripts_check_access.py
sudo docker compose ps
```
Expected health: 200/200/404. Data: 150600 rows, quantity 1931506, amount_satang 11929529809. Authentication and access checks pass. Do not regenerate .env or ingest data merely because the server restarted. Existing Compose has no automatic restart policy: start services manually after EC2 startup.

## Access API from Mac
Keep this Mac Terminal open:
```bash
ssh -i "$HOME/Downloads/fmcg-cloud-dev-key.pem" -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes -N -L 127.0.0.1:18080:127.0.0.1:8080 ubuntu@PUBLIC_IP
```
From another Mac Terminal:
```bash
curl --fail --show-error http://127.0.0.1:18080/health/live
curl --fail --show-error http://127.0.0.1:18080/health/ready
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:18080/analytics/sales-summary
```
Expected alive, ready, HTTP 401. Use the EC2 token privately for authenticated queries; do not paste it into chats or recorded demos. Mac's local .env has a different token.

## Pause work
On Ubuntu, wait for active load/backup work to finish:
```bash
cd /home/ubuntu/cloud-foundation
sudo docker compose stop
```
In AWS Console choose Stop instance, wait for Stopped. Do not choose Terminate: root EBS was configured Delete on termination = Yes. Closing SSH or Mac does not stop EC2. Stop retains EBS and its storage cost; it stops compute cost. A later start may assign a new public IPv4. Services are unavailable while stopped.

## Existing recovery evidence
The 13 October dump and list/source/restored companion files are on EC2 under backups and on Mac under Documents/fmcg-cloud/aws-backups. The dump SHA-256 matches between hosts. A new restore database was used instead of overwriting the application database. Keep its exact name if further checks are needed; no automatic deletion is performed here.

## Troubleshooting
SSH timeout: check instance state, current public IPv4, status checks and My IP rule. Do not recreate the server or broaden SSH exposure first.
Missing project files: inspect /home/ubuntu/cloud-foundation, then resend source excluding .env and backups if transfer was incomplete.
Containers not running: docker compose ps -a, then up -d --wait. Preserve volumes; do not run down -v.
Ready 503: investigate database connectivity privately. Data 503 with ready 200: inspect schema/data state before loading. Never post expanded Compose configuration or database URLs containing credentials.
Console MFA uses the current authenticator code, not yesterday's code. The EC2 name is not an IAM username.
