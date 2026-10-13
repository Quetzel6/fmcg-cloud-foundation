"""Fixed, read-only aggregate query. No user-provided SQL or filters."""
import os

def sales_summary():
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        row = connection.execute("SELECT COUNT(*), COALESCE(SUM(quantity::numeric),0), COALESCE(SUM(amount_satang::numeric),0), MIN(date), MAX(date) FROM fmcg.fact_sales_daily").fetchone()
        if not row[0]:
            raise ValueError("No sales snapshot")
        return {"data_class":"100% SYNTHETIC", "sales_type":"SO", "row_count":row[0], "quantity":str(row[1]), "amount_satang":str(row[2]), "start_date":row[3].isoformat(), "as_of_date":row[4].isoformat()}
