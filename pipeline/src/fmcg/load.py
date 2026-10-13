"""Validated snapshot load; schema replacement and post-load DQ share one transaction."""
import argparse
import json
import os
from decimal import Decimal
from pathlib import Path
from .contracts import COLUMNS,FLOAT_FIELDS
from .generate import ROOT
from .validate import validate

def qualified(table):
    return ('truth' if table.startswith('truth_') else 'fmcg',table)

def database_reconcile(conn,tables):
    """DQ-16 plus cross-table consistency executed before commit."""
    from psycopg import sql
    counts={}; amounts={}
    for table,rows in tables.items():
        schema,name=qualified(table)
        statement=sql.SQL('SELECT COUNT(*) FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(name))
        counts[table]=conn.execute(statement).fetchone()[0]
        if counts[table]!=len(rows): raise ValueError(f'DQ-16 count mismatch {table}')
        if table in ('fact_sales_daily','fact_order_line'):
            statement=sql.SQL('SELECT COALESCE(SUM(amount_satang::NUMERIC),0) FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(name))
            total=conn.execute(statement).fetchone()[0]
            if total!=sum(r['amount_satang'] for r in rows): raise ValueError(f'DQ-16 amount mismatch {table}')
            amounts[table]=str(total)
    checks={
      'DQ-08': 'SELECT count(*) FROM fmcg.fact_inventory_daily WHERE closing_qty::NUMERIC<>opening_qty::NUMERIC+receipt_qty-sold_qty+adjustment_qty',
      'DQ-09': '''SELECT count(*) FROM (SELECT opening_qty,LAG(closing_qty) OVER(PARTITION BY store_id,product_id ORDER BY date) prev FROM fmcg.fact_inventory_daily) x WHERE prev IS NOT NULL AND opening_qty<>prev''',
      'DQ-10': '''SELECT count(*) FROM fmcg.fact_inventory_daily i JOIN fmcg.fact_sales_daily s USING(date,store_id,product_id) WHERE i.sold_qty<>s.quantity''',
      'DQ-11': '''WITH receipts AS (SELECT delivered_date date,store_id,product_id,SUM(delivered_qty::NUMERIC) qty FROM fmcg.fact_order_line WHERE delivered_date IS NOT NULL GROUP BY delivered_date,store_id,product_id) SELECT count(*) FROM fmcg.fact_inventory_daily i LEFT JOIN receipts r USING(date,store_id,product_id) WHERE i.receipt_qty<>COALESCE(r.qty,0)''',
    }
    for code,statement in checks.items():
        if conn.execute(statement).fetchone()[0]: raise ValueError(f'{code} post-load reconciliation failed')
    return dict(status='passed',row_counts=counts,amount_totals_satang=amounts)

def load(data,config,connection_string=None,after_reconcile=None):
    report,tables=validate(data,config)
    if report['status']!='passed': raise ValueError('Data-quality gate failed: '+json.dumps([r for r in report['rules'] if r['count'] and r['severity']=='ERROR']))
    # Lazy import keeps local generation/QA runnable without a database client.
    import psycopg
    from psycopg import sql
    url=connection_string or os.environ.get('DATABASE_URL')
    if not url: raise ValueError('DATABASE_URL is required')
    with psycopg.connect(url,autocommit=True) as conn:
        with conn.transaction():
            conn.execute('SELECT pg_advisory_xact_lock(20261005)')
            conn.execute('DROP SCHEMA IF EXISTS truth CASCADE')
            conn.execute('DROP SCHEMA IF EXISTS fmcg CASCADE')
            conn.execute((ROOT/'sql/schema.sql').read_text())
            with conn.cursor() as cursor:
                for table,rows in tables.items():
                    schema,name=qualified(table); fields=COLUMNS[table]
                    statement=sql.SQL('COPY {}.{} ({}) FROM STDIN').format(sql.Identifier(schema),sql.Identifier(name),sql.SQL(',').join(map(sql.Identifier,fields)))
                    with cursor.copy(statement) as copy:
                        for row in rows:
                            values=[Decimal(str(row[k])) if k in FLOAT_FIELDS else row[k] for k in fields]
                            copy.write_row(values)
            conn.execute((ROOT/'sql/m2_views.sql').read_text())
            reconciliation=database_reconcile(conn,tables)
            if after_reconcile is not None:
                after_reconcile(conn)
    return dict(status='committed',data_quality=report,post_load=reconciliation)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,default=ROOT/'data'); p.add_argument('--config',type=Path,default=ROOT/'config/scenario.toml'); p.add_argument('--report',type=Path,default=ROOT/'output/load_report.json'); a=p.parse_args()
    try: report=load(a.data,a.config)
    except Exception as e:
        # Do not print connection strings or exception details containing credentials.
        a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(dict(status='failed',error_type=type(e).__name__,message='Load failed; inspect local validation report and database configuration. No successful commit reported.'),indent=2)+'\n'); raise SystemExit(f'Load failed ({type(e).__name__}); see {a.report}')
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,indent=2)+'\n'); print('COMMITTED: all manifest counts, amounts and ledger reconciliations passed')
