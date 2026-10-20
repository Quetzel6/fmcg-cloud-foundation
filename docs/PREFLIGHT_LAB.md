# Existing-stack preflight — no deployment mutations

This check addresses an observed author problem: running Git/Compose from the wrong folder could select an unrelated repository or a different Compose project. The check does not initialize Git, copy .env, create containers or remove volumes. It uses only `docker ps -a` and `docker inspect` with a metadata-only format, plus local file reads.

## Run on the existing Mac lab

```bash
python3 /tmp/fmcg-preflight.py --project-dir "/Users/sierra6/Documents/fmcg-cloud/cloud-foundation"
```

The script can be located in /tmp or a separate Git checkout. `--project-dir` must identify the EXISTING running stack directory, not the new source checkout. Defaults expect project `cloud-foundation` and volume `cloud-foundation_cloud_pg`, matching the author's existing lab.

Outputs only file existence, required-key presence booleans, project directory, expected volume name, and container state checks. It never prints env values, container environment, response bodies or raw Docker errors. Secret presence is a basic check for simple dotenv assignments, not full Compose interpolation or credential validation. Actual auth/data checks remain separate.

The inspector verifies both API and PostgreSQL belong to the specified project and working directory, are running/healthy, and PostgreSQL mounts the expected named volume at /var/lib/postgresql/data. A custom bind mount or different project name deliberately fails until the author verifies and supplies the correct `--expected-project` and `--expected-volume`. Do not change defaults simply to make a failing check pass.

If any check fails, exit status is 1. Do not automatically run `compose up`, remove volumes, overwrite .env or load data. Check the indicated mismatch first. A successful preflight is a point-in-time identity/state check: it does not prove database contents, backup restore, Git cleanliness, host security or EC2 status.

## Repeatable operator sequence

1. Run preflight against the old active directory.
2. Run the bounded monitor (200 live / 200 ready / 401 anonymous data expected).
3. From the existing directory run scripts_check_auth.py and scripts_check_data.py to validate actual access and snapshot totals.
4. Only then plan an agreed change with known Compose identity and a verified backup. Preflight itself authorizes no change.

## Implementation evidence

Seven local tests cover healthy metadata, missing project files, wrong volume, wrong working directory, stopped state, empty env keys and redacted Docker failures. These tests simulate Docker metadata; they do not establish a successful actual-Docker trial. Existing monitor tests continue to pass. Author Mac preflight trial and remote CI for this change are pending.

## Explain this in an interview

- Why is a running container insufficient evidence that you selected the right database?
- Why can copying compose.yaml into a newly named folder point to a different named volume?
- Why does having a nonempty token not prove authentication works?
- Why is the monitor's 401 result healthy for an anonymous protected request?

Answer using identity checks, explicit project/volume expectations and separate functional validation. Do not claim that this read-only preflight deploys infrastructure or provides automatic disaster recovery.
