"""Access setup for the disposable lab database; fixed role and table names."""
import os
import re

ROLE = "fmcg_api"

def grant_sales_read(connection):
    if connection.execute("SELECT to_regclass('fmcg.fact_sales_daily')").fetchone()[0] is not None:
        connection.execute("GRANT USAGE ON SCHEMA fmcg TO fmcg_api")
        connection.execute("GRANT SELECT ON fmcg.fact_sales_daily TO fmcg_api")

def provision(connection, password):
    if not re.fullmatch(r"[A-Za-z0-9]{32,128}", password or ""):
        raise ValueError("API password must be 32-128 alphanumeric characters")
    from psycopg import sql
    if connection.execute("SELECT 1 FROM pg_roles WHERE rolname = 'fmcg_api'").fetchone() is None:
        connection.execute("CREATE ROLE fmcg_api LOGIN")
    # Only a fixed dedicated lab role is modified. The password is never printed.
    connection.execute(sql.SQL("ALTER ROLE fmcg_api WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Literal(password)))
    memberships=connection.execute("SELECT parent.rolname FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member WHERE child.rolname='fmcg_api'").fetchall()
    for (parent,) in memberships:
        connection.execute(sql.SQL("REVOKE {} FROM fmcg_api").format(sql.Identifier(parent)))
    connection.execute("REVOKE CREATE, TEMPORARY ON DATABASE fmcg_cloud FROM PUBLIC")
    connection.execute("REVOKE ALL ON DATABASE fmcg_cloud FROM fmcg_api")
    connection.execute("GRANT CONNECT ON DATABASE fmcg_cloud TO fmcg_api")
    connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    for schema in ("fmcg", "truth"):
        if connection.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone():
            connection.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM fmcg_api").format(sql.Identifier(schema)))
            connection.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM fmcg_api").format(sql.Identifier(schema)))
    grant_sales_read(connection)
