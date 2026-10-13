"""One PCG64-driven daily simulation. Ground truth is written separately."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from collections import defaultdict, deque
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import tomllib
import numpy as np
from .contracts import COLUMNS, csv_path

ROOT=Path(__file__).resolve().parents[2]

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def money(value):
    return int(Decimal(str(value)).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def discount_price(price,discount):
    return int((Decimal(price)*(100-Decimal(discount))/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def dates(start,end):
    for i in range((end-start).days+1): yield start+dt.timedelta(days=i)

def promotion_months(cfg, customer_id, final_year):
    key = 'months_final_year' if final_year else 'months_full_year'
    return cfg['promotion'].get('customer_' + key, {}).get(customer_id, cfg['promotion'][key])

def config_read(path):
    cfg=tomllib.loads(path.read_text())
    start=dt.date.fromisoformat(cfg['scenario']['start_date']); end=dt.date.fromisoformat(cfg['scenario']['as_of_date'])
    if start!=dt.date(start.year,1,1) or end<start: raise ValueError('Period must start January 1 and end on/after start')
    if np.__version__!=cfg['scenario']['required_numpy_version']: raise ValueError('Install pinned numpy version: '+cfg['scenario']['required_numpy_version'])
    if len(cfg['customers'])!=3 or len(cfg['products'])!=10 or len(cfg['stores']['regions'])!=5: raise ValueError('Current contract requires 3 customers, 10 products and 5 stores each')
    if len({c['id'] for c in cfg['customers']})!=3 or len({p['id'] for p in cfg['products']})!=10: raise ValueError('Duplicate config IDs')
    if cfg['promotion']['mechanic']!='PRICE_DISCOUNT': raise ValueError('Only PRICE_DISCOUNT has a defined price contract')
    customer_ids = {c['id'] for c in cfg['customers']}
    for key in ('months_full_year', 'months_final_year'):
        overrides = cfg['promotion'].get('customer_' + key, {})
        if not isinstance(overrides, dict) or set(overrides) - customer_ids:
            raise ValueError('Promotion calendar override has unknown customer IDs')
        for months in [cfg['promotion'][key], *overrides.values()]:
            if not isinstance(months, list) or not months or any(type(m) is not int or not 1 <= m <= 12 for m in months) or months != sorted(set(months)):
                raise ValueError('Promotion months must be nonempty, sorted, unique integers from 1 to 12')
    if any(type(c['promo_start_day']) is not int or not 1 <= c['promo_start_day'] <= 28 for c in cfg['customers']):
        raise ValueError('Promotion start day must be an integer from 1 to 28')
    for cat in cfg['categories']:
        if len(cat['seasonality'])!=12 or min(cat['seasonality'])<=0 or cat['base_rate']<=0: raise ValueError('Invalid category demand')
    if any(p['case_size']<=0 or p['shelf_price_satang']<=0 or p['category'] not in {c['name'] for c in cfg['categories']} for p in cfg['products']): raise ValueError('Invalid product config')
    return cfg,start,end

def generate(config_path,output):
    cfg,start,end=config_read(config_path)
    rng=np.random.Generator(np.random.PCG64(cfg['scenario']['seed']))
    records={table:[] for table in COLUMNS}
    customers={c['id']:c for c in cfg['customers']}; products={p['id']:p for p in cfg['products']}; categories={c['name']:c for c in cfg['categories']}
    for day in dates(start,end):
        records['dim_date'].append(dict(date_key=day.isoformat(),year=day.year,quarter=(day.month-1)//3+1,month=day.month,month_start=day.replace(day=1).isoformat(),iso_week=day.isocalendar().week,day_of_week=day.isoweekday(),is_weekend=day.weekday()>=5))
    for cid,c in customers.items(): records['dim_customer'].append(dict(customer_id=cid,customer_name=c['name'],channel=c['channel']))
    stores={}
    for cid,c in customers.items():
        for i,region in enumerate(cfg['stores']['regions']):
            tier=cfg['stores']['tiers'][i]
            factor=float(np.clip(rng.lognormal(0,cfg['demand']['store_size_sigma'])*cfg['stores']['tier_factors'][tier],cfg['demand']['store_size_min'],cfg['demand']['store_size_max']))
            sid=f'{cid}S{i+1:02d}'
            row=dict(store_id=sid,customer_id=cid,store_name=f"{c['name']} {region}",region=region,format=c['channel'],tier=tier,size_factor=factor)
            stores[sid]=row; records['dim_store'].append(row)
    prices={}
    for pid,p in products.items():
        records['dim_product'].append(dict(product_id=pid,product_name=p['name'],brand=p['brand'],category=p['category'],case_size=p['case_size'],country_of_origin=p['country_of_origin'],import_lead_days=p['import_lead_days'],moq_cases=p['moq_cases']))
        shelf=p['shelf_price_satang']
        for year in range(start.year,end.year+1):
            if year>start.year: shelf=money(Decimal(shelf)*(1+Decimal(str(rng.uniform(cfg['pricing']['annual_growth_min'],cfg['pricing']['annual_growth_max'])))))
            invoice=money(Decimal(shelf)*Decimal(str(cfg['pricing']['invoice_ratio'])))
            prices[pid,year]=(shelf,invoice)
            records['dim_price'].append(dict(product_id=pid,effective_from=f'{year}-01-01',shelf_price_satang=shelf,invoice_price_satang=invoice))
    promo_daily={}; effects={}
    for cid,c in customers.items():
        for pid,p in products.items():
            cat=categories[p['category']]
            for year in range(start.year,end.year+1):
                months=promotion_months(cfg,cid,year==end.year)
                for month in months:
                    first=dt.date(year,month,c['promo_start_day'])
                    length=int(rng.integers(cfg['promotion']['min_days'],cfg['promotion']['max_days']+1)); last=first+dt.timedelta(days=length-1)
                    if first-dt.timedelta(days=28)<start or last+dt.timedelta(days=cfg['promotion']['post_days'])>end: continue
                    discount=int(rng.choice(cfg['promotion']['discounts'])); uplift=cat['promo_k']*discount/100*float(rng.lognormal(0,cfg['promotion']['effect_sigma']))
                    dip=min(cfg['promotion']['max_post_dip'],cfg['promotion']['post_dip_fraction']*uplift)
                    promo_id=f'PR{len(records["dim_promotion"])+1:04d}'
                    records['dim_promotion'].append(dict(promo_id=promo_id,customer_id=cid,product_id=pid,start_date=first.isoformat(),end_date=last.isoformat(),discount_pct=discount,mechanic=cfg['promotion']['mechanic']))
                    records['truth_promo_effect'].append(dict(promo_id=promo_id,true_uplift_pct=uplift*100,true_post_dip_pct=-dip*100))
                    for day in dates(first,last): promo_daily[day,cid,pid]=(1+uplift,discount)
                    for day in dates(last+dt.timedelta(days=1),last+dt.timedelta(days=cfg['promotion']['post_days'])): effects[day,cid,pid]=1-dip
    disruptions={}
    options=[(cid,pid) for cid in customers for pid in products]
    for index in range(cfg['disruption']['event_count']):
        cid,pid=options[int(rng.integers(len(options)))]; length=int(rng.integers(cfg['disruption']['min_days'],cfg['disruption']['max_days']+1))
        for attempt in range(1000):
            first=start+dt.timedelta(days=int(rng.integers(45,(end-start).days-length-15)))
            last=first+dt.timedelta(days=length-1)
            if not any((day,cid,pid) in disruptions for day in dates(first,last)): break
        else: raise ValueError('Cannot place nonoverlapping disruptions')
        extra=int(rng.integers(cfg['disruption']['extra_delay_min'],cfg['disruption']['extra_delay_max']+1)); fill=float(rng.uniform(cfg['disruption']['fill_min'],cfg['disruption']['fill_max']))
        row=dict(event_id=f'D{index+1:04d}',customer_id=cid,product_id=pid,start_date=first.isoformat(),end_date=last.isoformat(),extra_delay_days=extra,fill_factor=fill)
        records['truth_supply_disruption'].append(row)
        for day in dates(first,last): disruptions[day,cid,pid]=(extra,fill)
    # Planner noise is fixed before daily actuals are simulated. Target values use LY only.
    planner_factors={(year,month,cid,cat):Decimal(str(rng.uniform(cfg['target']['planner_noise_min'],cfg['target']['planner_noise_max']))) for year in cfg['target']['years'] for month in range(1,13) for cid in customers for cat in categories}
    histories={}; balances={}; base={}; pending=defaultdict(int); deliveries=defaultdict(list)
    for sid,store in stores.items():
        for pid,p in products.items():
            key=sid,pid; rate=categories[p['category']]['base_rate']*store['size_factor']*p['popularity']
            base[key]=rate; balances[key]=money(rate*cfg['demand']['opening_days']); histories[key]=deque(maxlen=cfg['replenishment']['history_days'])
    order_lines=[]
    for day in dates(start,end):
        receipts=defaultdict(int)
        for key,qty,ordered in deliveries.pop(day,[]): receipts[key]+=qty; pending[key]-=ordered
        for sid,store in stores.items():
            cid=store['customer_id']; customer=customers[cid]; today_orders=[]
            for pid,p in products.items():
                key=sid,pid; cat=categories[p['category']]; opening=balances[key]; receipt=receipts[key]
                trend=(1+customer['annual_growth'])**((day-start).days/365.25)
                expected=base[key]*cat['seasonality'][day.month-1]*trend*(customer['weekend_factor'] if day.weekday()>=5 else 1)
                noise=float(rng.gamma(cfg['demand']['noise_shape'],1/cfg['demand']['noise_shape']))
                promo,discount=promo_daily.get((day,cid,pid),(effects.get((day,cid,pid),1),0))
                # Poisson superposition/thinning couples potential outcomes coherently.
                baseline=int(rng.poisson(expected*noise))
                if promo>1: latent=baseline+int(rng.poisson(expected*noise*(promo-1)))
                elif promo<1: latent=int(rng.binomial(baseline,promo))
                else: latent=baseline
                sold=min(latent,opening+receipt); lost=latent-sold
                closing=opening+receipt-sold; adjustment=0
                if rng.random()<cfg['inventory']['shrink_probability']: adjustment=-min(closing,int(rng.integers(1,cfg['inventory']['shrink_max_qty']+1)))
                closing+=adjustment; balances[key]=closing
                shelf,invoice=prices[pid,day.year]; unit=discount_price(shelf,discount)
                records['fact_sales_daily'].append(dict(date=day.isoformat(),store_id=sid,product_id=pid,quantity=sold,unit_price_satang=unit,amount_satang=sold*unit))
                records['fact_inventory_daily'].append(dict(date=day.isoformat(),store_id=sid,product_id=pid,opening_qty=opening,receipt_qty=receipt,sold_qty=sold,adjustment_qty=adjustment,closing_qty=closing))
                records['truth_demand_daily'].append(dict(date=day.isoformat(),store_id=sid,product_id=pid,baseline_demand_qty=baseline,latent_demand_qty=latent,lost_qty=lost))
                histories[key].append(sold)
                # Bootstrap uses configured rate; after the first days, only observed sold history.
                history=histories[key]; estimate=float(np.mean(history)); sigma=float(np.std(history))
                if (day-start).days<cfg['replenishment']['bootstrap_days']: estimate=max(estimate,base[key])
                lead=customer['lead_days']; window=lead+cfg['replenishment']['review_days']
                rop=estimate*window+cfg['replenishment']['safety_z']*sigma*math.sqrt(window)
                position=closing+pending[key]
                if position<=rop and estimate>0:
                    level=rop+cfg['replenishment']['order_cycle_days']*estimate
                    ordered=max(p['case_size'],math.ceil((level-position)/p['case_size'])*p['case_size'])
                    promise=day+dt.timedelta(days=lead)
                    delay=int(rng.choice(cfg['delivery']['delay_days'],p=cfg['delivery']['delay_probabilities']))
                    factor=1.0 if rng.random()<cfg['delivery']['in_full_probability'] else float(rng.uniform(cfg['delivery']['short_fill_min'],cfg['delivery']['short_fill_max']))
                    if (day,cid,pid) in disruptions:
                        extra,factor=disruptions[day,cid,pid]; delay+=extra
                    scheduled=promise+dt.timedelta(days=delay)
                    qty=max(cfg['delivery']['min_observed_delivery_qty'],min(ordered,math.floor(ordered*factor)))
                    delivered=scheduled if scheduled<=end else None
                    delivered_qty=qty if delivered else 0
                    unit_si=prices[pid,delivered.year if delivered else day.year][1]
                    line=dict(order_id=f'O{day:%Y%m%d}{sid}',line_id=str(len(today_orders)+1),store_id=sid,product_id=pid,order_date=day.isoformat(),promised_date=promise.isoformat(),delivered_date=delivered.isoformat() if delivered else '',ordered_qty=ordered,delivered_qty=delivered_qty,unit_price_satang=unit_si,amount_satang=delivered_qty*unit_si)
                    today_orders.append(line); pending[key]+=ordered
                    if delivered: deliveries[delivered].append((key,delivered_qty,ordered))
            order_lines.extend(today_orders)
    records['fact_order_line']=order_lines
    si=defaultdict(int)
    for line in order_lines:
        if line['delivered_date']:
            d=dt.date.fromisoformat(line['delivered_date']); cid=stores[line['store_id']]['customer_id']; category=products[line['product_id']]['category']; si[d.year,d.month,cid,category]+=line['amount_satang']
    for year in cfg['target']['years']:
        if year-1<start.year: raise ValueError('Targets need a complete prior year')
        for month in range(1,13):
            for cid,c in customers.items():
                for cat in categories:
                    noise=planner_factors[year,month,cid,cat]
                    value=money(Decimal(si[year-1,month,cid,cat])*(1+Decimal(str(c['planned_growth'])))*noise)
                    records['fact_target_monthly'].append(dict(month_start=f'{year}-{month:02d}-01',customer_id=cid,category=cat,target_amount_satang=value))
    output.mkdir(parents=True,exist_ok=True)
    files={}
    for table,rows in records.items():
        path=csv_path(output,table); path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=COLUMNS[table],lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
        files[table]=dict(path=path.relative_to(output).as_posix(),rows=len(rows),sha256=sha256(path))
    manifest=dict(contract_version='0.2',data_class='100% SYNTHETIC',seed=cfg['scenario']['seed'],config_sha256=sha256(config_path),generator_sha256=sha256(Path(__file__)),numpy_version=np.__version__,bit_generator='PCG64',start_date=start.isoformat(),as_of_date=end.isoformat(),files=files,amount_totals_satang={t:sum(r['amount_satang'] for r in records[t]) for t in ['fact_sales_daily','fact_order_line']})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--config',type=Path,default=ROOT/'config/scenario.toml'); parser.add_argument('--output',type=Path,default=ROOT/'data'); a=parser.parse_args(); m=generate(a.config,a.output); print(json.dumps({t:v['rows'] for t,v in m['files'].items()},indent=2))
