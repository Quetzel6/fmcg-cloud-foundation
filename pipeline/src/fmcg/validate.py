"""DQ-01..17 validation; this module alone may inspect truth for QA."""
import argparse
import csv
import datetime as dt
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from .contracts import COLUMNS,KEYS,INT_FIELDS,FLOAT_FIELDS,DATE_FIELDS,csv_path
from .generate import ROOT,config_read,dates,sha256,discount_price

class Findings:
    def __init__(self): self.items={}
    def add(self,code,message,severity='ERROR'):
        row=self.items.setdefault(code,dict(id=code,severity=severity,count=0,examples=[])); row['count']+=1
        if len(row['examples'])<5: row['examples'].append(message)
    def report(self,metrics):
        rules=[self.items.get(f'DQ-{i:02d}',dict(id=f'DQ-{i:02d}',severity='WARN' if i==17 else 'ERROR',count=0,examples=[])) for i in range(1,18)]
        return dict(status='failed' if any(r['count'] and r['severity']=='ERROR' for r in rules) else 'passed',rules=rules,scenario_metrics=metrics)

def read_dataset(root,findings):
    tables={}
    for table,fields in COLUMNS.items():
        path=csv_path(root,table); rows=[]; seen=set()
        if not path.exists(): findings.add('DQ-01',f'Missing {path.name}'); tables[table]=[]; continue
        with path.open(encoding='utf-8',newline='') as stream:
            reader=csv.DictReader(stream)
            if reader.fieldnames!=fields: findings.add('DQ-01',f'{table}: header differs from contract'); tables[table]=[]; continue
            for number,row in enumerate(reader,2):
                try:
                    for field in fields:
                        value=row[field]
                        if value in (None,''):
                            if field=='delivered_date': row[field]=None; continue
                            raise ValueError(f'null {field}')
                        if field in INT_FIELDS: row[field]=int(value)
                        elif field in FLOAT_FIELDS:
                            row[field]=float(value)
                            if not math.isfinite(row[field]): raise ValueError('nonfinite number')
                        elif field in DATE_FIELDS: row[field]=dt.date.fromisoformat(value)
                        elif field=='is_weekend':
                            if value not in ('True','False'): raise ValueError('invalid bool')
                            row[field]=value=='True'
                    if None in row: raise ValueError('extra columns')
                    key=tuple(row[k] for k in KEYS[table])
                    if key in seen: findings.add('DQ-01',f'{table}: duplicate key {key}')
                    seen.add(key); rows.append(row)
                except (ValueError,TypeError,KeyError) as e: findings.add('DQ-01',f'{table}:{number}: {e}')
        tables[table]=rows
    return tables

def validate(root,config_path,strict_sanity=False):
    cfg,start,end=config_read(config_path); f=Findings(); tables=read_dataset(root,f)
    try: manifest=json.loads((root/'manifest.json').read_text())
    except (OSError,ValueError): manifest={}; f.add('DQ-16','Manifest missing or unreadable')
    if manifest.get('generator_sha256')!=sha256(ROOT/'src/fmcg/generate.py'): f.add('DQ-16','Generator code hash mismatch')
    if manifest.get('config_sha256')!=sha256(config_path): f.add('DQ-16','Config hash mismatch')
    if manifest.get('seed')!=cfg['scenario']['seed'] or manifest.get('as_of_date')!=end.isoformat() or manifest.get('start_date')!=start.isoformat() or manifest.get('numpy_version')!=cfg['scenario']['required_numpy_version']: f.add('DQ-16','Manifest scenario metadata mismatch')
    for table in COLUMNS:
        entry=manifest.get('files',{}).get(table,{})
        if entry.get('rows')!=len(tables[table]): f.add('DQ-16',f'{table}: manifest count mismatch')
        path=csv_path(root,table)
        if path.exists() and entry.get('sha256')!=sha256(path): f.add('DQ-16',f'{table}: checksum mismatch')
        if entry.get('path')!=path.relative_to(root).as_posix(): f.add('DQ-16',f'{table}: manifest path mismatch')
    if 'DQ-01' in f.items: return f.report({}),tables
    customers={r['customer_id']:r for r in tables['dim_customer']}; products={r['product_id']:r for r in tables['dim_product']}; stores={r['store_id']:r for r in tables['dim_store']}; calendar={r['date_key']:r for r in tables['dim_date']}; categories={r['category'] for r in products.values()}
    for r in stores.values():
        if r['customer_id'] not in customers: f.add('DQ-02',f'Store customer: {r["store_id"]}')
    for table in COLUMNS:
        for r in tables[table]:
            for field,pool in [('store_id',stores),('product_id',products),('customer_id',customers)]:
                if field in r and r[field] not in pool: f.add('DQ-02',f'{table}: unknown {field}')
            for field,value in r.items():
                if field.endswith(('_qty','_satang')) or field in ('quantity','case_size','import_lead_days','moq_cases'):
                    if field!='adjustment_qty' and value<0: f.add('DQ-03',f'{table}: negative {field}')
            for field in ('date','date_key','order_date','delivered_date','effective_from','start_date','end_date'):
                if r.get(field) is not None and not start<=r[field]<=end: f.add('DQ-04',f'{table}: {field} outside observed period')
            for field in ('date','order_date','delivered_date'):
                if r.get(field) is not None and r[field] not in calendar: f.add('DQ-02',f'{table}: date missing from calendar')
    if 'DQ-02' in f.items: return f.report({}),tables
    if set(calendar)!=set(dates(start,end)): f.add('DQ-05','Date dimension incomplete')
    for d,r in calendar.items():
        if (r['year'],r['quarter'],r['month'],r['month_start'],r['iso_week'],r['day_of_week'],r['is_weekend'])!=(d.year,(d.month-1)//3+1,d.month,d.replace(day=1),d.isocalendar().week,d.isoweekday(),d.weekday()>=5): f.add('DQ-04','Calendar attributes inconsistent')
    expected={(d,s,p) for d in dates(start,end) for s in stores for p in products}
    sales={(r['date'],r['store_id'],r['product_id']):r for r in tables['fact_sales_daily']}; inventory={(r['date'],r['store_id'],r['product_id']):r for r in tables['fact_inventory_daily']}; truth={(r['date'],r['store_id'],r['product_id']):r for r in tables['truth_demand_daily']}
    for name,panel in [('sales',sales),('inventory',inventory),('truth',truth)]:
        if set(panel)!=expected: f.add('DQ-05',f'{name}: missing {len(expected-set(panel))}, extra {len(set(panel)-expected)} keys')
    price_lists=defaultdict(list)
    for r in tables['dim_price']: price_lists[r['product_id']].append(r)
    price_lookup={}
    for pid in products:
        versions=sorted(price_lists[pid],key=lambda r:r['effective_from'])
        if [r['effective_from'] for r in versions]!=[dt.date(y,1,1) for y in range(start.year,end.year+1)]: f.add('DQ-14',f'{pid}: expected exactly one annual price version')
        for day in dates(start,end):
            eligible=[v for v in versions if v['effective_from']<=day]
            if not eligible: f.add('DQ-14',f'{pid} {day}: no effective price'); continue
            price_lookup[day,pid]=eligible[-1]
    promos={}; active={}; by_pair=defaultdict(list)
    for r in tables['dim_promotion']:
        promos[r['promo_id']]=r; by_pair[r['customer_id'],r['product_id']].append(r)
        if r['start_date']>r['end_date'] or r['mechanic']!='PRICE_DISCOUNT' or r['discount_pct'] not in cfg['promotion']['discounts']: f.add('DQ-13',f'Invalid promo {r["promo_id"]}')
        for day in dates(r['start_date'],r['end_date']):
            key=day,r['customer_id'],r['product_id']
            if key in active: f.add('DQ-13',f'Overlapping promo {key}')
            active[key]=r['discount_pct']
    for pair,rows in by_pair.items():
        rows.sort(key=lambda r:r['start_date'])
        if any((b['start_date']-a['end_date']).days<cfg['promotion']['min_gap_days'] for a,b in zip(rows,rows[1:])): f.add('DQ-13',f'Unclean promo spacing {pair}')
    for r in tables['truth_promo_effect']:
        if r['promo_id'] not in promos: f.add('DQ-02','Orphan truth promo')
    if {r['promo_id'] for r in tables['truth_promo_effect']}!=set(promos): f.add('DQ-02','Truth promo coverage incomplete')
    receipts=defaultdict(int); order_headers={}; order_skus=set()
    for r in tables['fact_order_line']:
        delivered=r['delivered_date']; qty=r['delivered_qty']; ordered=r['ordered_qty']; header=(r['store_id'],r['order_date'])
        if r['order_id'] in order_headers and order_headers[r['order_id']]!=header: f.add('DQ-12','Order ID spans stores/dates')
        order_headers[r['order_id']]=header
        key=r['order_id'],r['product_id']
        if key in order_skus: f.add('DQ-12','Duplicate SKU in order')
        order_skus.add(key)
        if ordered<=0 or ordered%products[r['product_id']]['case_size'] or qty>ordered or r['order_date']>r['promised_date'] or (delivered is None)!=(qty==0) or (delivered is not None and not r['order_date']<=delivered<=end): f.add('DQ-12',f'Order invalid {r["order_id"]}/{r["line_id"]}')
        if r['amount_satang']!=qty*r['unit_price_satang']: f.add('DQ-06','Order amount identity')
        price=price_lookup.get((delivered or r['order_date'],r['product_id']))
        if price and r['unit_price_satang']!=price['invoice_price_satang']: f.add('DQ-07','Order invoice price mismatch')
        if delivered: receipts[delivered,r['store_id'],r['product_id']]+=qty
    for key,r in sales.items():
        if r['amount_satang']!=r['quantity']*r['unit_price_satang']: f.add('DQ-06',f'Sales amount {key}')
        date,sid,pid=key; price=price_lookup.get((date,pid))
        if price and r['unit_price_satang']!=discount_price(price['shelf_price_satang'],active.get((date,stores[sid]['customer_id'],pid),0)): f.add('DQ-07',f'Sales realised price {key}')
    for key,r in inventory.items():
        if r['closing_qty']!=r['opening_qty']+r['receipt_qty']-r['sold_qty']+r['adjustment_qty'] or r['closing_qty']<0: f.add('DQ-08',f'Ledger {key}')
        day,sid,pid=key; prior=inventory.get((day-dt.timedelta(days=1),sid,pid))
        if prior and r['opening_qty']!=prior['closing_qty']: f.add('DQ-09',f'Opening continuity {key}')
        if key in sales and r['sold_qty']!=sales[key]['quantity']: f.add('DQ-10',f'Inventory/SO {key}')
        if r['receipt_qty']!=receipts[key]: f.add('DQ-11',f'Receipts/order {key}')
        if key in truth:
            t=truth[key]
            if t['lost_qty']!=t['latent_demand_qty']-r['sold_qty'] or r['sold_qty']!=min(t['latent_demand_qty'],r['opening_qty']+r['receipt_qty']): f.add('DQ-10',f'Truth constrained-demand identity {key}')
    # All lines for a store/day are one order; quantities are whole case orders.
    header_ids=defaultdict(set)
    for order_id,header in order_headers.items(): header_ids[header].add(order_id)
    if any(len(ids)>1 for ids in header_ids.values()): f.add('DQ-12','Multiple orders for same store/day')
    target_expected={(dt.date(y,m,1),c,cat) for y in cfg['target']['years'] for m in range(1,13) for c in customers for cat in categories}
    target_actual={(r['month_start'],r['customer_id'],r['category']) for r in tables['fact_target_monthly']}
    if target_actual!=target_expected: f.add('DQ-15','Target month/customer/category coverage mismatch')
    for table in ('fact_sales_daily','fact_order_line'):
        if sum(r['amount_satang'] for r in tables[table])!=manifest.get('amount_totals_satang',{}).get(table): f.add('DQ-16',f'{table}: amount total differs from manifest')
    metrics=scenario_metrics(tables,end,products)
    severity='ERROR' if strict_sanity else 'WARN'; bounds=cfg['sanity']
    if not bounds['stockout_min']<=metrics['true_stockout_day_rate']<=bounds['stockout_max']: f.add('DQ-17','True stockout rate outside bounds',severity)
    if not bounds['otif_min']<=metrics['line_otif_rate']<=bounds['otif_max']: f.add('DQ-17','Line OTIF outside bounds',severity)
    if metrics['disruption_events']<bounds['min_disruptions']: f.add('DQ-17','Not enough disruptions',severity)
    if set(metrics['stockout_categories'])!=categories: f.add('DQ-17','Missing stockouts in a category',severity)
    if any(r['true_uplift_pct']<=0 for r in tables['truth_promo_effect']): f.add('DQ-17','Nonpositive planted uplift',severity)
    if not 150<=len(promos)<=250: f.add('DQ-17','Promotion count outside scenario scope',severity)
    for cat in cfg['categories']:
        if cat['seasonality'][11]<=sum(cat['seasonality'][:3])/3: f.add('DQ-17','December seasonality does not exceed Q1',severity)
    return f.report(metrics),tables

def scenario_metrics(tables,as_of,products):
    # QA measurements, not published business KPIs (M2/M5 are not implemented).
    demand=tables['truth_demand_daily']; due=[r for r in tables['fact_order_line'] if r['promised_date']<=as_of]
    otif=sum(r['delivered_date'] is not None and r['delivered_date']<=r['promised_date'] and r['delivered_qty']==r['ordered_qty'] for r in due)
    return dict(true_stockout_day_rate=sum(r['lost_qty']>0 for r in demand)/len(demand) if demand else 0,line_otif_rate=otif/len(due) if due else 0,disruption_events=len(tables['truth_supply_disruption']),promotion_count=len(tables['dim_promotion']),stockout_categories=sorted({products[r['product_id']]['category'] for r in demand if r['lost_qty']>0}))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--config',type=Path,default=ROOT/'config/scenario.toml'); p.add_argument('--data',type=Path,default=ROOT/'data'); p.add_argument('--strict-sanity',action='store_true'); p.add_argument('--report',type=Path,default=ROOT/'output/data_quality.json'); a=p.parse_args(); report,_=validate(a.data,a.config,a.strict_sanity); a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2)); raise SystemExit(1 if report['status']=='failed' else 0)
