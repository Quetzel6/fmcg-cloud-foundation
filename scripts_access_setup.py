import os
import psycopg
from app.access import provision
if __name__ == "__main__":
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as connection:
            provision(connection, os.environ["API_DB_PASSWORD"])
        print('{"access_setup":"passed","api_role":"fmcg_api"}')
    except Exception as error:
        raise SystemExit("Access setup failed: " + type(error).__name__) from None
