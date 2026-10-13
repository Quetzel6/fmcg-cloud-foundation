-- Dedicated project schemas. Executed inside the loader transaction only.
CREATE SCHEMA fmcg;
CREATE SCHEMA truth;
CREATE TABLE fmcg.dim_date (
 date_key DATE PRIMARY KEY, year INTEGER NOT NULL, quarter INTEGER NOT NULL CHECK(quarter BETWEEN 1 AND 4),
 month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12), month_start DATE NOT NULL, iso_week INTEGER NOT NULL CHECK(iso_week BETWEEN 1 AND 53), day_of_week INTEGER NOT NULL CHECK(day_of_week BETWEEN 1 AND 7), is_weekend BOOLEAN NOT NULL
);
CREATE TABLE fmcg.dim_customer (customer_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, channel TEXT NOT NULL);
CREATE TABLE fmcg.dim_store (
 store_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES fmcg.dim_customer,
 store_name TEXT NOT NULL, region TEXT NOT NULL, format TEXT NOT NULL, tier TEXT NOT NULL CHECK(tier IN ('A','B','C')), size_factor NUMERIC NOT NULL CHECK(size_factor>0)
);
CREATE TABLE fmcg.dim_product (
 product_id TEXT PRIMARY KEY, product_name TEXT NOT NULL, brand TEXT NOT NULL, category TEXT NOT NULL,
 case_size BIGINT NOT NULL CHECK(case_size>0),country_of_origin TEXT NOT NULL,import_lead_days BIGINT NOT NULL CHECK(import_lead_days>=0),moq_cases BIGINT NOT NULL CHECK(moq_cases>0)
);
CREATE TABLE fmcg.dim_price (
 product_id TEXT NOT NULL REFERENCES fmcg.dim_product,effective_from DATE NOT NULL REFERENCES fmcg.dim_date(date_key),
 shelf_price_satang BIGINT NOT NULL CHECK(shelf_price_satang>=0),invoice_price_satang BIGINT NOT NULL CHECK(invoice_price_satang>=0),PRIMARY KEY(product_id,effective_from)
);
CREATE TABLE fmcg.dim_promotion (
 promo_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES fmcg.dim_customer,product_id TEXT NOT NULL REFERENCES fmcg.dim_product,
 start_date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),end_date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),discount_pct NUMERIC NOT NULL CHECK(discount_pct IN (10,15,20,25,30)),mechanic TEXT NOT NULL CHECK(mechanic='PRICE_DISCOUNT'),CHECK(end_date>=start_date)
);
CREATE TABLE fmcg.fact_sales_daily (
 date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),store_id TEXT NOT NULL REFERENCES fmcg.dim_store,product_id TEXT NOT NULL REFERENCES fmcg.dim_product,
 quantity BIGINT NOT NULL CHECK(quantity>=0),unit_price_satang BIGINT NOT NULL CHECK(unit_price_satang>=0),amount_satang BIGINT NOT NULL CHECK(amount_satang>=0),
 PRIMARY KEY(date,store_id,product_id),CHECK(amount_satang::NUMERIC=quantity::NUMERIC*unit_price_satang)
);
CREATE TABLE fmcg.fact_inventory_daily (
 date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),store_id TEXT NOT NULL REFERENCES fmcg.dim_store,product_id TEXT NOT NULL REFERENCES fmcg.dim_product,
 opening_qty BIGINT NOT NULL CHECK(opening_qty>=0),receipt_qty BIGINT NOT NULL CHECK(receipt_qty>=0),sold_qty BIGINT NOT NULL CHECK(sold_qty>=0),adjustment_qty BIGINT NOT NULL,closing_qty BIGINT NOT NULL CHECK(closing_qty>=0),
 PRIMARY KEY(date,store_id,product_id),CHECK(closing_qty::NUMERIC=opening_qty::NUMERIC+receipt_qty-sold_qty+adjustment_qty)
);
CREATE TABLE fmcg.fact_order_line (
 order_id TEXT NOT NULL,line_id TEXT NOT NULL,store_id TEXT NOT NULL REFERENCES fmcg.dim_store,product_id TEXT NOT NULL REFERENCES fmcg.dim_product,
 order_date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),promised_date DATE NOT NULL,delivered_date DATE REFERENCES fmcg.dim_date(date_key),
 ordered_qty BIGINT NOT NULL CHECK(ordered_qty>0),delivered_qty BIGINT NOT NULL CHECK(delivered_qty>=0 AND delivered_qty<=ordered_qty),unit_price_satang BIGINT NOT NULL CHECK(unit_price_satang>=0),amount_satang BIGINT NOT NULL CHECK(amount_satang>=0),
 PRIMARY KEY(order_id,line_id),UNIQUE(order_id,product_id),CHECK(promised_date>=order_date),CHECK(delivered_date>=order_date),CHECK((delivered_date IS NULL)=(delivered_qty=0)),CHECK(amount_satang::NUMERIC=delivered_qty::NUMERIC*unit_price_satang)
);
CREATE TABLE fmcg.fact_target_monthly (
 month_start DATE NOT NULL CHECK(EXTRACT(DAY FROM month_start)=1),customer_id TEXT NOT NULL REFERENCES fmcg.dim_customer,category TEXT NOT NULL,target_amount_satang BIGINT NOT NULL CHECK(target_amount_satang>=0),PRIMARY KEY(month_start,customer_id,category)
);
CREATE TABLE truth.truth_demand_daily (
 date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),store_id TEXT NOT NULL REFERENCES fmcg.dim_store,product_id TEXT NOT NULL REFERENCES fmcg.dim_product,
 baseline_demand_qty BIGINT NOT NULL CHECK(baseline_demand_qty>=0),latent_demand_qty BIGINT NOT NULL CHECK(latent_demand_qty>=0),lost_qty BIGINT NOT NULL CHECK(lost_qty>=0),PRIMARY KEY(date,store_id,product_id)
);
CREATE TABLE truth.truth_promo_effect (promo_id TEXT PRIMARY KEY REFERENCES fmcg.dim_promotion,true_uplift_pct NUMERIC NOT NULL,true_post_dip_pct NUMERIC NOT NULL);
CREATE TABLE truth.truth_supply_disruption (
 event_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES fmcg.dim_customer,product_id TEXT NOT NULL REFERENCES fmcg.dim_product,
 start_date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),end_date DATE NOT NULL REFERENCES fmcg.dim_date(date_key),extra_delay_days BIGINT NOT NULL CHECK(extra_delay_days>=0),fill_factor NUMERIC NOT NULL CHECK(fill_factor BETWEEN 0 AND 1),CHECK(end_date>=start_date)
);
CREATE INDEX sales_customer_join ON fmcg.fact_sales_daily(store_id,product_id,date);
CREATE INDEX orders_delivered ON fmcg.fact_order_line(delivered_date,store_id,product_id);
CREATE INDEX inventory_store_product ON fmcg.fact_inventory_daily(store_id,product_id,date);
REVOKE ALL ON SCHEMA truth FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA truth FROM PUBLIC;
