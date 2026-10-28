# AWS off-host backup and fresh-host restore acceptance plan

Status: **planned, not executed**. No AWS recovery result or duration is claimed.
Historical EC2 deployment evidence and the newer local Docker recovery drill are
different experiments. This plan does not change either result.

## Smallest useful next experiment

Use a dedicated private S3 bucket for one synthetic PostgreSQL dump and restore
it onto a second disposable EC2 host with new PostgreSQL storage. Do not mount,
copy or reuse the source Docker volume. Download the dump from S3 on the target;
a local-to-local restore alone cannot pass this experiment.

Prefer this single PostgreSQL/S3 experiment before adding RDS. It extends the
existing stack without changing database platform and tests two explicit gaps:
independent backup storage and recovery after loss of the original host.

## Preconditions before creating paid resources

- Owner selects region, maximum intended spend and maximum experiment duration.
- Configure a budget alert and verify its recipient/configuration. Alerts are
  not a hard spending cap. Record settings privately, with no email/account ID
  in public evidence.
- Use temporary credentials and separate setup/runtime permissions. Runtime
  permissions cover only the chosen bucket and run prefix: PutObject/GetObject,
  and ListBucket restricted to that prefix. Cleanup permissions belong to the
  operator; no wildcard administrator runtime policy.
- Block all S3 public access, disable ACLs with Bucket owner enforced, require
  TLS, and verify encryption. Never expose PostgreSQL publicly.
- Maintain a private resource inventory and teardown procedure before launch.
  No credentials, account IDs, host addresses or unsanitized CLI logs in git.

AWS reference:
https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html

## Execution and acceptance evidence

1. Pin source commit and image identifiers. Generate synthetic data and freeze
   writes for this bounded trial. Capture all 13 nonempty table counts and
   deterministic fingerprints plus sales aggregates.
2. Create a custom-format pg_dump without owner/ACL restoration; record bytes,
   SHA-256 and completion time. Upload to the dedicated run prefix. Download
   and independently hash it on the new host; do not equate an S3 ETag to SHA-256.
3. Record the target as new compute with a new empty database volume. Record
   source isolation before restore, without destroying unrelated resources.
4. Start a monotonic timer immediately before downloading the backup on the
   target. Restore transactionally with errors treated as failure, provision
   required database roles/grants, then start the API.
5. Compare every captured table count/fingerprint and sales aggregate. Verify
   authenticated reporting 200, missing/wrong token 401 and the existing seven
   database permission-denial probes. Capture each actual result.
6. Stop the timer only when reconciliation and access checks pass. Record
   download, restore, permission setup and validation durations separately.
   Provisioning time is a separate metric. Name the combined value
   "observed recovery-drill duration", not a production RTO.
7. If any stage fails, retain a sanitized failure result; do not fill expected
   results into the evidence. A retry is a separate run with a new identifier.
8. Delete only resources listed for this run: objects (including versions and
   delete markers if enabled), unfinished multipart uploads, bucket, target
   compute, owned volumes/snapshots and temporary IAM/network resources. Verify
   absence and review billing afterward. Preserve unrelated source resources.

## Public evidence contract

Publish a reviewed, allowlisted summary containing run ID, UTC timestamps,
source commit, image identifiers, backup SHA-256/bytes, table comparisons,
HTTP/access outcomes, measured stage durations, failures and cleanup status.
Use logical source/target labels; keep the raw resource inventory private.
Do not upload a database dump, credentials, account IDs or raw terminal capture.

Acceptance requires both successful recovery checks and confirmed cleanup.
Before acceptance, update neither resume nor AWS recovery claims.

## Boundaries after a successful run

A passing run would establish one manually initiated, idle synthetic snapshot
restore from S3 onto a fresh EC2 host. It would not establish PITR, continuous
backup, automated failover, concurrent-write consistency, high availability,
production RTO/RPO, or an RDS snapshot restore. Record these limits even on success.
