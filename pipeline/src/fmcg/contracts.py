"""Authored CSV columns and types; never infer SQL identifiers from CSV input."""
COLUMNS = {
 'dim_date': ['date_key','year','quarter','month','month_start','iso_week','day_of_week','is_weekend'],
 'dim_customer': ['customer_id','customer_name','channel'],
 'dim_store': ['store_id','customer_id','store_name','region','format','tier','size_factor'],
 'dim_product': ['product_id','product_name','brand','category','case_size','country_of_origin','import_lead_days','moq_cases'],
 'dim_price': ['product_id','effective_from','shelf_price_satang','invoice_price_satang'],
 'dim_promotion': ['promo_id','customer_id','product_id','start_date','end_date','discount_pct','mechanic'],
 'fact_sales_daily': ['date','store_id','product_id','quantity','unit_price_satang','amount_satang'],
 'fact_inventory_daily': ['date','store_id','product_id','opening_qty','receipt_qty','sold_qty','adjustment_qty','closing_qty'],
 'fact_order_line': ['order_id','line_id','store_id','product_id','order_date','promised_date','delivered_date','ordered_qty','delivered_qty','unit_price_satang','amount_satang'],
 'fact_target_monthly': ['month_start','customer_id','category','target_amount_satang'],
 'truth_demand_daily': ['date','store_id','product_id','baseline_demand_qty','latent_demand_qty','lost_qty'],
 'truth_promo_effect': ['promo_id','true_uplift_pct','true_post_dip_pct'],
 'truth_supply_disruption': ['event_id','customer_id','product_id','start_date','end_date','extra_delay_days','fill_factor'],
}
KEYS = {
 'dim_date':['date_key'],'dim_customer':['customer_id'],'dim_store':['store_id'],'dim_product':['product_id'],
 'dim_price':['product_id','effective_from'],'dim_promotion':['promo_id'],
 'fact_sales_daily':['date','store_id','product_id'],'fact_inventory_daily':['date','store_id','product_id'],
 'fact_order_line':['order_id','line_id'],'fact_target_monthly':['month_start','customer_id','category'],
 'truth_demand_daily':['date','store_id','product_id'],'truth_promo_effect':['promo_id'],'truth_supply_disruption':['event_id'],
}
INT_FIELDS = {'year','quarter','month','iso_week','day_of_week','case_size','import_lead_days','moq_cases','shelf_price_satang','invoice_price_satang','discount_pct','quantity','unit_price_satang','amount_satang','opening_qty','receipt_qty','sold_qty','adjustment_qty','closing_qty','ordered_qty','delivered_qty','target_amount_satang','baseline_demand_qty','latent_demand_qty','lost_qty','extra_delay_days'}
FLOAT_FIELDS={'size_factor','true_uplift_pct','true_post_dip_pct','fill_factor'}
DATE_FIELDS={'date_key','date','month_start','effective_from','start_date','end_date','order_date','promised_date','delivered_date'}

def csv_path(root, table):
    return root/('truth' if table.startswith('truth_') else 'warehouse')/(table+'.csv')
