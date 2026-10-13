# English demo outline — edit after running

"This project is a local operational foundation for a synthetic FMCG analytics platform. It has a Python HTTP service and a PostgreSQL database. It is not deployed to the cloud yet."

"Liveness tells us whether the service can respond. Readiness checks whether it can connect to the database. When I stop the database, liveness stays successful but readiness returns HTTP 503."

"The database is accessible inside the Compose network. Only the API is published, and it is limited to localhost. Credentials are excluded from the repository and request logs. The current demo database user still needs tighter permissions before a cloud deployment."

After executing the drill, explain the evidence in your own words. Do not change 'local' to 'cloud' until the deployment is verified. Be ready to explain the code and limitations rather than memorize the script.

After Phase 2 acceptance, demonstrate the synthetic SO summary and explain that amount_satang is an exact integer monetary unit. Do not claim data loading passed until the actual database run succeeds.
