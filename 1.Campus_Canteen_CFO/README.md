# Campus Canteen CFO — CSV → SQL → Elasticity (Databricks)

**TL;DR:** A student‑friendly, reproducible project that turns a simple canteen CSV into **CFO‑level pricing decisions** using only SQL:
- `GROUP BY` for daily units & realized average price
- Window functions (`LAG`, percent‑of‑total)
- **Point elasticity** of demand = %ΔQ / %ΔP
- A small set of charts + an “actions” table per item

---

## 🎯 Objectives
- Teach core SQL analytics patterns with a relatable scenario.
- Show how to estimate simple price elasticity without ML.
- Produce shareable visuals for LinkedIn/GitHub.

---

## 📦 What’s in this repo
```
campus-canteen-cfo/
├─ data/
│  └─ campus_canteen_sales_large.csv          # sample dataset (3 weeks)
├─ notebooks/
│  └─ Campus_Canteen_CFO_Elasticity_Notebook.py  # Databricks notebook with %sql/%md
├─ images/                                     # (you create these from the steps below)
│  ├─ 01_csv_head.png
│  ├─ 02_price_vs_units_veg_puff.png
│  ├─ 03_elasticity_line_veg_puff.png
│  ├─ 04_category_share_stacked.png
│  └─ 05_actions_table.png
├─ sql/ (optional)
│  ├─ 01_create_sales_raw.sql
│  ├─ 02_item_day.sql
│  └─ 03_elasticity_view.sql
└─ README.md
```

> Data is small enough for Git; in production, keep data in cloud storage (DBFS/S3) and version notebooks/SQL in Git.

---

## 🧪 Dataset
**File:** `data/campus_canteen_sales_large.csv`  
**Columns:**  
`txn_id, txn_ts, student_id, item_id, item_name, category, qty, unit_price, discount_pct, payment_method`

- 6 items: Veg Puff, Samosa, Masala Sandwich, Cold Coffee, Cutting Chai, Poha
- 21 days with a few **price changes** baked in so elasticity is observable
- `qty` is integer; occasional discounts simulate promotions

---

## ⚡ Quickstart (Databricks)
1. **Create/clone** this repo via **Repos** in Databricks (or clone locally and push).  
2. **Upload** the CSV to DBFS, e.g. `/FileStore/canteen/campus_canteen_sales_large.csv`.  
3. **Import** `notebooks/Campus_Canteen_CFO_Elasticity_Notebook.py` as **Source**.  
4. **Open** the notebook, set the `csv_path` variable, and **Run All**.  
5. Create the charts in the UI (steps below) and export images into `/images` to commit.

---

## 🧠 Concepts (explained in notebook)
- **GROUP BY:** Aggregates transaction rows into business signals (units, revenue).  
- **Realized average price:** `SUM(net_amount)/SUM(qty)` after discounts.  
- **Window %:** Percent‑of‑day by category using `SUM(rev)/SUM(rev) OVER (PARTITION BY day)`.  
- **LAG():** Brings prior‑day price/units per item to compare **changes**, not levels.  
- **Point elasticity:**  
  \[ E = \frac{\%\Delta Q}{\%\Delta P} = \frac{(units - prev\_units)/prev\_units}{(avg\_price - prev\_price)/prev\_price} \]  
  - **E < −1** → elastic (small price cuts can raise revenue)  
  - **−1 ≤ E < 0** → inelastic (small increases are safer)  
  - **≈ 0** → little sensitivity  
  **Caveats:** control for footfall (weekday/weekend), exclude low‑unit days, avoid divide‑by‑zero, handle outliers.

---

## 🔧 Core SQL (preview)
```sql
-- Create typed view
CREATE OR REPLACE VIEW canteen.sales AS
SELECT
  CAST(txn_id AS STRING) AS txn_id,
  to_timestamp(txn_ts)   AS txn_ts,
  CAST(student_id AS STRING) AS student_id,
  item_id, item_name, category,
  CAST(qty AS INT) AS qty,
  CAST(unit_price AS DECIMAL(10,2)) AS unit_price,
  COALESCE(CAST(discount_pct AS DECIMAL(5,2)), 0) AS discount_pct,
  (qty * unit_price * (1 - COALESCE(discount_pct,0)/100.0)) AS net_amount,
  date_trunc('day', to_timestamp(txn_ts)) AS txn_day
FROM canteen.sales_raw
WHERE qty > 0 AND unit_price > 0;

-- Daily metrics per item
CREATE OR REPLACE TEMP VIEW item_day AS
SELECT
  item_id, item_name, txn_day,
  ROUND(SUM(net_amount)/NULLIF(SUM(qty),0), 2) AS avg_price,
  SUM(qty) AS units
FROM canteen.sales
GROUP BY item_id, item_name, txn_day;

-- Bring previous day values
CREATE OR REPLACE TEMP VIEW item_day_w AS
SELECT
  item_id, item_name, txn_day, avg_price, units,
  LAG(avg_price) OVER (PARTITION BY item_id ORDER BY txn_day) AS prev_price,
  LAG(units)     OVER (PARTITION BY item_id ORDER BY txn_day) AS prev_units
FROM item_day;

-- Elasticity
CREATE OR REPLACE VIEW canteen.item_elasticity AS
SELECT
  item_id, item_name, txn_day, avg_price, units, prev_price, prev_units,
  CASE
    WHEN prev_price IS NULL OR prev_units IS NULL OR prev_price = 0 OR prev_units = 0 OR avg_price = prev_price THEN NULL
    ELSE ((units - prev_units)/prev_units) / ((avg_price - prev_price)/prev_price)
  END AS elasticity
FROM item_day_w;
```

---

## 📈 Charts to reproduce (and save into `/images`)

> In Databricks SQL, run the query, click **Visualization**, configure as below, **Save**, then **Export as image**.

1) **CSV head** (sanity check) → `01_csv_head.png`  
   - Run: `SELECT * FROM canteen.sales_raw LIMIT 8;`  
   - Screenshot the table head (crop tightly).  
   - **Alt text:** “Head of canteen sales CSV with columns txn_ts, item_name, qty, unit_price.”

2) **Price vs Units (Veg Puff)** → `02_price_vs_units_veg_puff.png`  
   - Query:
     ```sql
     SELECT item_name, avg_price, units
     FROM item_day
     WHERE item_name = 'Veg Puff'
     ORDER BY avg_price;
     ```
   - Visualization: **Scatter**; X=`avg_price`, Y=`units`.  
   - **Alt text:** “Scatter of Veg Puff average price vs units showing a negative slope.”

3) **Elasticity over time (Veg Puff)** → `03_elasticity_line_veg_puff.png`  
   - Query:
     ```sql
     SELECT txn_day, item_name, elasticity
     FROM canteen.item_elasticity
     WHERE item_name = 'Veg Puff'
     ORDER BY txn_day;
     ```
   - Visualization: **Line**; X=`txn_day`, Y=`elasticity`.  
   - **Alt text:** “Line plot of Veg Puff elasticity by day with spikes around price changes.”

4) **Category share of day (100% stacked)** → `04_category_share_stacked.png`  
   - Query:
     ```sql
     WITH cat AS (
       SELECT txn_day, category, SUM(qty*unit_price*(1-discount_pct/100.0)) AS rev
       FROM canteen.sales
       GROUP BY txn_day, category
     )
     SELECT txn_day, category, rev,
            ROUND(100.0 * rev / SUM(rev) OVER (PARTITION BY txn_day), 2) AS pct_of_day
     FROM cat
     ORDER BY txn_day, rev DESC;
     ```
   - Visualization: **Stacked bar (100%)**; X=`txn_day`; Series=`category`; Value=`pct_of_day`.  
   - **Alt text:** “100% stacked bars of each day’s revenue share by category.”

5) **Actions table (median elasticity per item)** → `05_actions_table.png`  
   - Query:
     ```sql
     SELECT item_name,
            PERCENTILE_APPROX(elasticity, 0.5) AS med_E,
            COUNT(elasticity) AS observations,
            CASE
              WHEN PERCENTILE_APPROX(elasticity, 0.5) <= -1 THEN 'Lower price (elastic)'
              WHEN PERCENTILE_APPROX(elasticity, 0.5) BETWEEN -1 AND -0.2 THEN 'Bundle / careful lower'
              WHEN PERCENTILE_APPROX(elasticity, 0.5) > -0.2 THEN 'Test small increase'
              ELSE 'Insufficient data'
            END AS recommendation
     FROM canteen.item_elasticity
     GROUP BY item_name
     ORDER BY med_E ASC;
     ```
   - Visualization: **Table** (with data labels on).  
   - **Alt text:** “Median elasticity per item with a recommended action.”

> **LinkedIn:** Use 1080×1080 images (square) for carousels.  
> **GitHub:** Use 1400–1600px width for clarity; include alt text in Markdown.

---

## 📝 Suggested LinkedIn post
- **Hook:** “Campus Canteen CFO: I priced Veg Puff wrong. SQL fixed it. 🍽️📊”  
- **Concepts:** GROUP BY → window → elasticity (%ΔQ/%ΔP).  
- **Findings:** Veg Puff elastic → lower price; Chai inelastic → test small increase.  
- **CTA:** Comment **CFO** for dataset + notebook (link in comments).  
- Attach images: 02, 03, and 05 (or all 5 as a carousel).

---

## 🔗 How to cite & license
- License: MIT (replace if you prefer).  
- Citation: “Campus Canteen CFO — CSV→SQL→Elasticity by <your name>”.

---

## 🙋 Troubleshooting
- **No elasticity values?** Ensure there’s a price change for that item and enough days with units > 0.  
- **Weird spikes?** Exclude days with `units < 10`; smooth with medians.  
- **Different DBFS path?** Update `csv_path` at the top of the notebook.
