"""Run in the API container using its actual login; probes are rolled back."""
import os
import json
import psycopg

def verify(connection):
    role=connection.execute("SELECT current_user, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
    assert role[0]=='fmcg_api' and not any(role[1:]), "Unexpected API role capabilities"
    connection.execute("SELECT COUNT(*) FROM fmcg.fact_sales_daily").fetchone()
    checks={
        "update_denied":"UPDATE fmcg.fact_sales_daily SET quantity=quantity WHERE FALSE",
        "delete_denied":"DELETE FROM fmcg.fact_sales_daily WHERE FALSE",
        "insert_denied":"INSERT INTO fmcg.fact_sales_daily SELECT * FROM fmcg.fact_sales_daily WHERE FALSE",
        "truth_denied":"SELECT * FROM truth.truth_demand_daily LIMIT 0",
        "create_schema_denied":"CREATE SCHEMA api_permission_probe",
        "create_temp_denied":"CREATE TEMP TABLE api_permission_probe(value INTEGER)",
        "admin_role_denied":"SET ROLE fmcg_cloud",
    }
    results={"api_role":"fmcg_api","sales_select":"passed"}
    for name,statement in checks.items():
        try:
            with connection.transaction():
                connection.execute(statement)
                raise AssertionError(name+" unexpectedly allowed")
        except psycopg.errors.InsufficientPrivilege:
            results[name]="passed"
    return results

if __name__=='__main__':
    try:
        with psycopg.connect(os.environ['DATABASE_URL'],connect_timeout=5) as connection:
            result=verify(connection)
            connection.rollback()
        print(json.dumps(result))
    except Exception as error:
        raise SystemExit("Access verification failed: "+type(error).__name__) from None
