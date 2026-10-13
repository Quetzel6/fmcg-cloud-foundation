# Verified project content for a CGP application

This is project wording, not a completed resume. Name/contact, education wording and expected graduation, employment dates/responsibilities, English proficiency, work eligibility and portfolio URL must be confirmed before preparing a final application. Do not infer years of employment from this lab.

## Project entry — English
FMCG Cloud Foundation | Personal Portfolio Project | October 2026
Python · SQL · PostgreSQL · Docker Compose · AWS EC2 · Linux

- Deployed a containerized Python API and PostgreSQL demo on AWS EC2, with private database networking and remote access through an SSH tunnel.
- Implemented Bearer-token data endpoints and a read-only PostgreSQL API role; verified denial of data modification, restricted truth-table access, schema/temp creation and admin-role assumption.
- Loaded and reconciled 150,600 synthetic sales records and verified matching sales aggregates after database restoration; confirmed an off-host backup with SHA-256.
- Documented deployment and recovery procedures and verified data persistence, API authentication and database permissions after service recovery.

Use these claims only with the supporting evidence and limitations in README. Do not claim production operations, measured business improvement, enterprise IAM, Terraform or executed CI without further implementation.

## 60–90 second explanation
“I built this project to practise deploying and operating a small analytics service in the cloud. The business scenario is a synthetic FMCG sales platform. I deployed a Python API and PostgreSQL using Docker Compose on AWS EC2. The API reads through a restricted database role, and its data endpoints require a Bearer token. I kept the API on localhost and used an SSH tunnel for remote access. I verified 150,600 sales records, tested denied database operations, restored a backup into a separate database, and compared the sales totals. I also copied the backup to my Mac and verified its SHA-256. After restarting the environment, I checked data persistence and authentication again. This is a portfolio lab on a single server; the next improvements would be managed secrets, monitoring, infrastructure as code and a production deployment design.”

## Interview preparation
Why one EC2 host? It kept the demo scope and operations simple; shared API/database failure domain is a tradeoff, not a production recommendation.
Why an SSH tunnel? Encrypted controlled remote access without exposing the demo HTTP service publicly.
Readiness versus data health? Ready checks database connectivity; data health checks the expected loaded snapshot.
What does backup verification prove? The copy is byte-identical; the restored sales aggregates match. It does not prove every restored row/table or ACL is identical.
What happens when the Mac disconnects? EC2 remains running; foreground commands may be interrupted, but saved EBS data persists.
What remains for production? Workload requirements, identity and secrets, TLS, availability, monitoring, automated provisioning, recovery objectives and performance evaluation.

## CGP alignment
Demonstrated: Linux, containers, basic cloud deployment, networking isolation, database access, troubleshooting and operational documentation. Still to establish: customer-facing solution discovery, practical depth across cloud services, professional English communication and an appropriate deployment identity. This project does not guarantee hiring eligibility or salary.
