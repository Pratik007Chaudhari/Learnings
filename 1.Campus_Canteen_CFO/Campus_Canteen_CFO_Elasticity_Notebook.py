# Databricks notebook source
# MAGIC %md
# MAGIC # Campus learning.sample CFO — CSV → SQL → Elasticity
# MAGIC **Goal:** Find price points that improve revenue without tanking demand, using only SQL.
# MAGIC
# MAGIC **You will practice:**
# MAGIC - GROUP BY for daily item metrics
# MAGIC - Window functions: percent-of-total & LAG()
# MAGIC - Simple price elasticity of demand
# MAGIC
# MAGIC **Data columns:**
# MAGIC `txn_id, txn_ts, student_id, item_id, item_name, category, qty, unit_price, discount_pct, payment_method`
# MAGIC
# MAGIC _Tip: Import this notebook as **Source** to keep magic commands._

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0) One-time setup
# MAGIC **Upload** the CSV to DBFS (e.g. `/FileStore/learning.sample/campus_learning.sample_sales_large.csv`) and set this path below.

# COMMAND ----------

csv_path = "/Volumes/learning/sample/files_info/campus_canteen_sales_large.csv"  
schema_name = "sample"

print(f"CSV Path: {csv_path}")
print(f"Schema Name: {schema_name}")

# COMMAND ----------

# MAGIC %sql
# MAGIC Use catalog learning;
# MAGIC USE schema sample;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1) Create raw table from CSV

# COMMAND ----------

df = spark.read.csv(csv_path, header=True, inferSchema=True)
df.write.mode("overwrite").saveAsTable(schema_name + ".sales_raw")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM learning.sample.sales_raw LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2) Clean/typed view with helpers
# MAGIC - Ensure numeric types
# MAGIC - Compute net_amount
# MAGIC - Derive txn_day

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE VIEW learning.sample.sales AS
# MAGIC SELECT
# MAGIC   CAST(txn_id AS STRING) AS txn_id,
# MAGIC   to_timestamp(txn_ts)   AS txn_ts,
# MAGIC   CAST(student_id AS STRING) AS student_id,
# MAGIC   item_id, item_name, category,
# MAGIC   CAST(qty AS INT) AS qty,
# MAGIC   CAST(unit_price AS DECIMAL(10,2)) AS unit_price,
# MAGIC   COALESCE(CAST(discount_pct AS DECIMAL(5,2)), 0) AS discount_pct,
# MAGIC   (qty * unit_price * (1 - COALESCE(discount_pct,0)/100.0)) AS net_amount,
# MAGIC   date_trunc('day', to_timestamp(txn_ts)) AS txn_day
# MAGIC FROM learning.sample.sales_raw
# MAGIC WHERE qty > 0 AND unit_price > 0;
# MAGIC
# MAGIC SELECT * FROM learning.sample.sales LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3) GROUP BY — daily metrics per item

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE VIEW item_day AS
# MAGIC SELECT
# MAGIC   item_id, item_name, txn_day,
# MAGIC   ROUND(SUM(net_amount)/NULLIF(SUM(qty),0), 2) AS avg_price,
# MAGIC   SUM(qty) AS units
# MAGIC FROM learning.sample.sales
# MAGIC GROUP BY item_id, item_name, txn_day;
# MAGIC
# MAGIC SELECT * FROM item_day ORDER BY item_name, txn_day LIMIT 20;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4) Window % — category share of day (bonus)

# COMMAND ----------

# MAGIC %sql
# MAGIC WITH cat AS (
# MAGIC   SELECT txn_day, category, SUM(qty*unit_price*(1-discount_pct/100.0)) AS rev
# MAGIC   FROM learning.sample.sales
# MAGIC   GROUP BY txn_day, category
# MAGIC )
# MAGIC SELECT
# MAGIC   txn_day, category, rev,
# MAGIC   ROUND(100.0 * rev / SUM(rev) OVER (PARTITION BY txn_day), 2) AS pct_of_day
# MAGIC FROM cat
# MAGIC ORDER BY txn_day, rev DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5) LAG() — bring previous day price & units

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TEMPORARY VIEW item_day_w AS
# MAGIC SELECT
# MAGIC   item_id, item_name, txn_day, avg_price, units,
# MAGIC   LAG(avg_price) OVER (PARTITION BY item_id ORDER BY txn_day) AS prev_price,
# MAGIC   LAG(units)     OVER (PARTITION BY item_id ORDER BY txn_day) AS prev_units
# MAGIC FROM item_day;
# MAGIC
# MAGIC SELECT * FROM item_day_w ORDER BY item_name, txn_day LIMIT 20;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6) Elasticity view
# MAGIC Point elasticity between adjacent days:
# MAGIC \( E = ((units - prev\_units)/prev\_units) / ((avg\_price - prev\_price)/prev\_price) \)

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TEMPORARY VIEW item_elasticity AS
# MAGIC SELECT
# MAGIC   item_id, item_name, txn_day, avg_price, units, prev_price, prev_units,
# MAGIC   CASE
# MAGIC     WHEN prev_price IS NULL OR prev_units IS NULL OR prev_price = 0 OR prev_units = 0 OR avg_price = prev_price THEN NULL
# MAGIC     ELSE ((units - prev_units)/prev_units) / ((avg_price - prev_price)/prev_price)
# MAGIC   END AS elasticity
# MAGIC FROM item_day_w;
# MAGIC
# MAGIC SELECT * FROM item_elasticity ORDER BY item_name, txn_day;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7) Visuals
# MAGIC - **Scatter:** X=avg_price, Y=units (filter item_name='Veg Puff')
# MAGIC - **Line:** elasticity over time per item
# MAGIC
# MAGIC _Create charts from results of queries below in the UI._

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Scatter for one item
# MAGIC SELECT item_name, avg_price, units
# MAGIC FROM item_day
# MAGIC WHERE item_name = 'Veg Puff'
# MAGIC ORDER BY avg_price;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Elasticity line
# MAGIC SELECT txn_day, item_name, elasticity
# MAGIC FROM item_elasticity
# MAGIC WHERE item_name = 'Veg Puff'
# MAGIC ORDER BY txn_day;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8) CFO actions — simple rule from median elasticity

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT item_name,
# MAGIC        PERCENTILE_APPROX(elasticity, 0.5) AS med_E,
# MAGIC        COUNT(elasticity) AS observations,
# MAGIC        CASE
# MAGIC          WHEN PERCENTILE_APPROX(elasticity, 0.5) <= -1 THEN 'Lower price (elastic)'
# MAGIC          WHEN PERCENTILE_APPROX(elasticity, 0.5) BETWEEN -1 AND -0.2 THEN 'Bundle / careful lower'
# MAGIC          WHEN PERCENTILE_APPROX(elasticity, 0.5) > -0.2 THEN 'Test small increase'
# MAGIC          ELSE 'Insufficient data'
# MAGIC        END AS recommendation
# MAGIC FROM item_elasticity
# MAGIC GROUP BY item_name
# MAGIC ORDER BY med_E ASC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extras
# MAGIC - Top 3 items by revenue each day (ROW_NUMBER())
# MAGIC - Remove noisy days with units < 10 and recompute medians

# COMMAND ----------

# MAGIC %sql
# MAGIC WITH d AS (
# MAGIC   SELECT txn_day, item_name, SUM(qty*unit_price*(1-discount_pct/100.0)) AS rev
# MAGIC   FROM learning.sample.sales GROUP BY txn_day, item_name
# MAGIC ),
# MAGIC r AS (
# MAGIC   SELECT *, ROW_NUMBER() OVER (PARTITION BY txn_day ORDER BY rev DESC) AS rn
# MAGIC   FROM d
# MAGIC )
# MAGIC SELECT * FROM r WHERE rn <= 3 ORDER BY txn_day, rn;
