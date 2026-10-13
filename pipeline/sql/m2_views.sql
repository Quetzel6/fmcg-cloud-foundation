-- C01..C08: amounts stay NUMERIC satang. Default as-of is the loaded date dimension end.
CREATE OR REPLACE VIEW fmcg.v_m2_monthly AS
WITH calendar AS (SELECT DISTINCT year,month FROM fmcg.dim_date),
transactions AS (
 SELECT s.date,c.customer_id,s.product_id,'SO'::TEXT sales_type,s.amount_satang::NUMERIC amount_satang,s.quantity::NUMERIC quantity
 FROM fmcg.fact_sales_daily s JOIN fmcg.dim_store c USING(store_id)
 UNION ALL
 SELECT o.delivered_date,c.customer_id,o.product_id,'SI',o.amount_satang::NUMERIC,o.delivered_qty::NUMERIC
 FROM fmcg.fact_order_line o JOIN fmcg.dim_store c USING(store_id) WHERE o.delivered_date IS NOT NULL
), sums AS (
 SELECT EXTRACT(YEAR FROM date)::INTEGER AS year,EXTRACT(MONTH FROM date)::INTEGER AS month,customer_id,product_id,sales_type,SUM(amount_satang) amount_satang,SUM(quantity) quantity
 FROM transactions GROUP BY 1,2,3,4,5
), panel AS (
 SELECT m.year,m.month,c.customer_id,c.customer_name,p.product_id,p.product_name,p.brand,p.category,k.sales_type,
 COALESCE(s.amount_satang,0::NUMERIC) amount_satang,COALESCE(s.quantity,0::NUMERIC) quantity
 FROM calendar m CROSS JOIN fmcg.dim_customer c CROSS JOIN fmcg.dim_product p CROSS JOIN (VALUES ('SI'),('SO')) k(sales_type)
 LEFT JOIN sums s ON s.year=m.year AND s.month=m.month AND s.customer_id=c.customer_id AND s.product_id=p.product_id AND s.sales_type=k.sales_type
)
SELECT p.*,p.amount_satang/NULLIF(p.quantity,0) asp_satang,
 (p.amount_satang-ly.amount_satang)/NULLIF(ly.amount_satang,0)*100 yoy_amount_pct,
 (p.quantity-ly.quantity)/NULLIF(ly.quantity,0)*100 yoy_qty_pct,
 (p.amount_satang-LAG(p.amount_satang) OVER w)/NULLIF(LAG(p.amount_satang) OVER w,0)*100 mom_amount_pct,
 (p.quantity-LAG(p.quantity) OVER w)/NULLIF(LAG(p.quantity) OVER w,0)*100 mom_qty_pct
FROM panel p LEFT JOIN panel ly ON ly.year=p.year-1 AND ly.month=p.month AND ly.customer_id=p.customer_id AND ly.product_id=p.product_id AND ly.sales_type=p.sales_type
WINDOW w AS (PARTITION BY p.customer_id,p.product_id,p.sales_type ORDER BY p.year,p.month);

CREATE OR REPLACE VIEW fmcg.v_m2_sku_ytd AS
WITH cutoff AS (SELECT MAX(date_key) as_of FROM fmcg.dim_date), y AS (
 SELECT m.customer_id,m.customer_name,m.product_id,m.product_name,m.brand,m.category,m.sales_type,
 COALESCE(SUM(amount_satang) FILTER(WHERE year=EXTRACT(YEAR FROM as_of)),0::NUMERIC) ty_amount_satang,
 COALESCE(SUM(amount_satang) FILTER(WHERE year=EXTRACT(YEAR FROM as_of)-1),0::NUMERIC) ly_amount_satang,
 COALESCE(SUM(quantity) FILTER(WHERE year=EXTRACT(YEAR FROM as_of)),0::NUMERIC) ty_qty,
 COALESCE(SUM(quantity) FILTER(WHERE year=EXTRACT(YEAR FROM as_of)-1),0::NUMERIC) ly_qty
 FROM fmcg.v_m2_monthly m CROSS JOIN cutoff WHERE month<=EXTRACT(MONTH FROM as_of) AND year BETWEEN EXTRACT(YEAR FROM as_of)-1 AND EXTRACT(YEAR FROM as_of)
 GROUP BY 1,2,3,4,5,6,7
), effects AS (
 SELECT y.*,CASE WHEN sales_type='SO' AND ly_qty>0 AND ty_qty>0 THEN (ty_qty-ly_qty)*ly_amount_satang/ly_qty END volume_effect_satang FROM y
)
SELECT e.*,(ty_amount_satang-ly_amount_satang)/NULLIF(ly_amount_satang,0)*100 yoy_amount_pct,
 (ty_qty-ly_qty)/NULLIF(ly_qty,0)*100 yoy_qty_pct,ty_amount_satang/NULLIF(ty_qty,0) ty_asp_satang,ly_amount_satang/NULLIF(ly_qty,0) ly_asp_satang,
 ty_amount_satang/NULLIF(SUM(ty_amount_satang) OVER(PARTITION BY customer_id,sales_type),0)*100 contribution_pct,
 DENSE_RANK() OVER(PARTITION BY customer_id,sales_type ORDER BY ty_amount_satang DESC) sku_rank,
 CASE WHEN volume_effect_satang IS NOT NULL THEN ty_amount_satang-ly_amount_satang-volume_effect_satang END price_effect_satang,
 CASE WHEN sales_type='SO' AND volume_effect_satang IS NULL THEN ty_amount_satang-ly_amount_satang ELSE 0 END undecomposed_delta_satang
FROM effects e;

CREATE OR REPLACE VIEW fmcg.v_m2_category_ytd AS
WITH cutoff AS (SELECT MAX(date_key) as_of FROM fmcg.dim_date), targets AS (
 SELECT customer_id,category,SUM(target_amount_satang::NUMERIC) target_satang FROM fmcg.fact_target_monthly CROSS JOIN cutoff
 WHERE EXTRACT(YEAR FROM month_start)=EXTRACT(YEAR FROM as_of) AND EXTRACT(MONTH FROM month_start)<=EXTRACT(MONTH FROM as_of) GROUP BY 1,2
), sales AS (
 SELECT customer_id,customer_name,category,sales_type,SUM(ty_amount_satang) ty_amount_satang,SUM(ly_amount_satang) ly_amount_satang,SUM(ty_qty) ty_qty,SUM(ly_qty) ly_qty
 FROM fmcg.v_m2_sku_ytd GROUP BY 1,2,3,4
)
SELECT s.*,(ty_amount_satang-ly_amount_satang)/NULLIF(ly_amount_satang,0)*100 yoy_amount_pct,(ty_qty-ly_qty)/NULLIF(ly_qty,0)*100 yoy_qty_pct,
 CASE WHEN sales_type='SI' THEN t.target_satang END ytd_target_satang,
 CASE WHEN sales_type='SI' THEN ty_amount_satang/NULLIF(t.target_satang,0)*100 END target_attainment_pct
FROM sales s LEFT JOIN targets t USING(customer_id,category);

CREATE OR REPLACE VIEW fmcg.v_m2_service AS
WITH cutoff AS (SELECT MAX(date_key) as_of FROM fmcg.dim_date), raw AS (
 SELECT c.customer_id,o.*,as_of FROM fmcg.fact_order_line o JOIN fmcg.dim_store c USING(store_id) CROSS JOIN cutoff WHERE order_date<=as_of
), expanded AS (SELECT * FROM raw UNION ALL SELECT 'ALL'::TEXT customer_id,order_id,line_id,store_id,product_id,order_date,promised_date,delivered_date,ordered_qty,delivered_qty,unit_price_satang,amount_satang,as_of FROM raw),
flags AS (SELECT *,promised_date<=as_of due,delivered_date IS NOT NULL AND delivered_date<=promised_date ontime,delivered_qty=ordered_qty infull FROM expanded),
lines AS (
 SELECT customer_id,COUNT(*) FILTER(WHERE due) due_lines,COUNT(*) FILTER(WHERE NOT due) pending_lines,
 SUM(ordered_qty::NUMERIC) FILTER(WHERE due) ordered_due_qty,SUM(delivered_qty::NUMERIC) FILTER(WHERE due) delivered_due_qty,
 COUNT(*) FILTER(WHERE due AND ontime) ontime_lines,COUNT(*) FILTER(WHERE due AND infull) infull_lines,COUNT(*) FILTER(WHERE due AND ontime AND infull) otif_lines,
 COALESCE(SUM(ordered_qty::NUMERIC) FILTER(WHERE delivered_date IS NULL),0) backlog_qty,
 COALESCE(SUM(ordered_qty::NUMERIC) FILTER(WHERE due AND delivered_date IS NULL),0) overdue_backlog_qty,
 AVG((delivered_date-order_date)::NUMERIC) FILTER(WHERE delivered_date IS NOT NULL) mean_lead_days,
 ARRAY_AGG(delivered_date-order_date ORDER BY delivered_date-order_date) FILTER(WHERE delivered_date IS NOT NULL) leads
 FROM flags GROUP BY customer_id
), orders AS (
 SELECT customer_id,order_id,BOOL_AND(ontime AND infull) otif FROM flags WHERE due GROUP BY 1,2
), order_stats AS (SELECT customer_id,COUNT(*) due_orders,COUNT(*) FILTER(WHERE otif) otif_orders FROM orders GROUP BY 1), partitions AS (SELECT customer_id FROM fmcg.dim_customer UNION ALL SELECT 'ALL')
SELECT p.customer_id,COALESCE(l.due_lines,0) due_lines,COALESCE(o.due_orders,0) due_orders,COALESCE(l.pending_lines,0) pending_lines,
 COALESCE(l.ordered_due_qty,0) ordered_due_qty,COALESCE(l.delivered_due_qty,0) delivered_due_qty,
 delivered_due_qty/NULLIF(ordered_due_qty,0)*100 fill_rate_pct,
 ontime_lines::NUMERIC/NULLIF(due_lines,0)*100 on_time_rate_pct,infull_lines::NUMERIC/NULLIF(due_lines,0)*100 in_full_rate_pct,
 otif_lines::NUMERIC/NULLIF(due_lines,0)*100 line_otif_pct,o.otif_orders::NUMERIC/NULLIF(o.due_orders,0)*100 order_otif_pct,
 COALESCE(l.backlog_qty,0) backlog_qty,COALESCE(l.overdue_backlog_qty,0) overdue_backlog_qty,l.mean_lead_days,
 CASE WHEN CARDINALITY(leads)>0 THEN leads[FLOOR((CARDINALITY(leads)-1)*0.9)::INTEGER+1]::NUMERIC+
 (leads[CEIL((CARDINALITY(leads)-1)*0.9)::INTEGER+1]-leads[FLOOR((CARDINALITY(leads)-1)*0.9)::INTEGER+1])*(((CARDINALITY(leads)-1)*0.9)-FLOOR((CARDINALITY(leads)-1)*0.9)) END p90_lead_days
FROM partitions p LEFT JOIN lines l USING(customer_id) LEFT JOIN order_stats o USING(customer_id);
