-- ============================================================================
-- NIFTY100 DATA FOUNDATION - DAY 07 EXPLORATORY QUERIES
-- Dataset: Nifty100 Data Foundation (Bluestock Fintech)
-- Database: db/nifty100.db
--
-- These 10 queries demonstrate that the loaded data is usable for
-- analysis and answer common business questions about the Nifty100.
-- ============================================================================


-- Q1. Data coverage: how many distinct companies and fiscal years in
--     each financial statement table?
SELECT 'profitandloss' AS table_name, COUNT(DISTINCT company_id) AS companies,
       COUNT(DISTINCT year) AS fiscal_years, COUNT(*) AS rows
  FROM profitandloss
UNION ALL
SELECT 'balancesheet', COUNT(DISTINCT company_id), COUNT(DISTINCT year), COUNT(*)
  FROM balancesheet
UNION ALL
SELECT 'cashflow', COUNT(DISTINCT company_id), COUNT(DISTINCT year), COUNT(*)
  FROM cashflow
UNION ALL
SELECT 'financial_ratios', COUNT(DISTINCT company_id), COUNT(DISTINCT year), COUNT(*)
  FROM financial_ratios;


-- Q2. Top 10 Nifty100 companies by latest revenue (FY2024).
SELECT c.company_name,
       p.sales AS revenue_crore,
       p.net_profit AS net_profit_crore,
       s.sub_sector
  FROM profitandloss p
  JOIN companies c ON c.id = p.company_id
  LEFT JOIN sectors s ON s.company_id = c.id
 WHERE p.year = (SELECT MAX(year) FROM profitandloss WHERE company_id = p.company_id)
 ORDER BY p.sales DESC
 LIMIT 10;


-- Q3. Sector distribution of the Nifty100 constituents.
SELECT broad_sector,
       COUNT(DISTINCT company_id) AS company_count,
       ROUND(SUM(index_weight_pct), 2) AS total_index_weight_pct
  FROM sectors
 GROUP BY broad_sector
 ORDER BY company_count DESC, total_index_weight_pct DESC;


-- Q4. Top gainers over the trailing 12 months of stock-price history.
WITH bounds AS (
    SELECT MAX(date) AS max_date,
           date(MAX(date), '-1 year') AS start_date
      FROM stock_prices
),
priced AS (
    SELECT company_id, date, close_price,
           ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY date ASC)  AS rn_asc,
           ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY date DESC) AS rn_desc
      FROM stock_prices
     WHERE date >= (SELECT start_date FROM bounds)
)
SELECT c.company_name,
       ROUND(f.close_price, 2) AS close_12m_ago,
       ROUND(l.close_price, 2) AS latest_close,
       ROUND((l.close_price - f.close_price) * 100.0 / f.close_price, 2) AS return_pct
  FROM (SELECT company_id, close_price FROM priced WHERE rn_desc = 1) l
  JOIN (SELECT company_id, close_price FROM priced WHERE rn_asc = 1) f
    ON f.company_id = l.company_id
  JOIN companies c ON c.id = l.company_id
 WHERE f.close_price > 0
 ORDER BY return_pct DESC
 LIMIT 10;


-- Q5. Most profitable companies by net profit margin (latest year).
WITH latest AS (
    SELECT company_id, year, net_profit, sales
      FROM profitandloss
     WHERE (company_id, year) IN (
           SELECT company_id, MAX(year)
             FROM profitandloss
            GROUP BY company_id
     )
)
SELECT c.company_name,
       ROUND(l.net_profit, 2) AS net_profit_crore,
       ROUND(l.net_profit * 100.0 / NULLIF(l.sales, 0), 2) AS net_profit_margin_pct
  FROM latest l
  JOIN companies c ON c.id = l.company_id
 WHERE l.sales > 0
 ORDER BY net_profit_margin_pct DESC
 LIMIT 10;


-- Q6. Highest dividend yield in the latest available market-cap data.
WITH latest AS (
    SELECT company_id, year, pe_ratio, pb_ratio, dividend_yield_pct
      FROM market_cap
     WHERE (company_id, year) IN (
           SELECT company_id, MAX(year)
             FROM market_cap
            GROUP BY company_id
     )
)
SELECT c.company_name,
       l.year                AS market_cap_year,
       ROUND(l.pe_ratio, 2)  AS pe_ratio,
       ROUND(l.pb_ratio, 2)  AS pb_ratio,
       ROUND(l.dividend_yield_pct, 2) AS dividend_yield_pct
  FROM latest l
  JOIN companies c ON c.id = l.company_id
 WHERE l.dividend_yield_pct IS NOT NULL
 ORDER BY dividend_yield_pct DESC
 LIMIT 10;


-- Q7. five-year revenue CAGR per company (2019 -> 2024).
--     Missing either boundary year -> NULL (excluded from ranking).
WITH base AS (
    SELECT company_id,
           MAX(CASE WHEN year = '2019-03' THEN sales END) AS sales_2019,
           MAX(CASE WHEN year = '2024-03' THEN sales END) AS sales_2024
      FROM profitandloss
     GROUP BY company_id
     HAVING sales_2019 IS NOT NULL AND sales_2024 IS NOT NULL AND sales_2019 > 0
)
SELECT c.company_name,
       ROUND(b.sales_2019, 0) AS revenue_fy19_crore,
       ROUND(b.sales_2024, 0) AS revenue_fy24_crore,
       ROUND(POWER(b.sales_2024 * 1.0 / b.sales_2019, 1.0 / 5) * 100 - 100, 2) AS revenue_cagr_pct
  FROM base b
  JOIN companies c ON c.id = b.company_id
 ORDER BY revenue_cagr_pct DESC
 LIMIT 10;


-- Q8. Companies with the highest debt-to-equity ratio (latest year) and
--     whether they are in a leveraged sector.
WITH latest AS (
    SELECT company_id, year, debt_to_equity
      FROM financial_ratios
     WHERE (company_id, year) IN (
           SELECT company_id, MAX(year)
             FROM financial_ratios
            GROUP BY company_id
     )
)
SELECT c.company_name,
       s.broad_sector,
       ROUND(l.debt_to_equity, 2) AS debt_to_equity,
       l.year
  FROM latest l
  JOIN companies c ON c.id = l.company_id
  LEFT JOIN sectors s ON s.company_id = c.id
 WHERE l.debt_to_equity IS NOT NULL
 ORDER BY debt_to_equity DESC
 LIMIT 10;


-- Q9. Free cash flow health check: companies with positive operating cash
--     flow but heavy capex (latest year).
WITH latest AS (
    SELECT company_id, year, cash_from_operations_cr, capex_cr
      FROM financial_ratios
     WHERE (company_id, year) IN (
           SELECT company_id, MAX(year)
             FROM financial_ratios
            GROUP BY company_id
     )
     AND cash_from_operations_cr IS NOT NULL
     AND capex_cr IS NOT NULL
)
SELECT c.company_name,
       ROUND(l.cash_from_operations_cr, 2) AS op_cash_flow_cr,
       ROUND(l.capex_cr, 2)                AS capex_cr,
       ROUND(l.cash_from_operations_cr - l.capex_cr, 2) AS free_cash_flow_cr
  FROM latest l
  JOIN companies c ON c.id = l.company_id
 ORDER BY free_cash_flow_cr DESC
 LIMIT 10;


-- Q10. Peer groups: benchmark constituents among Nifty100 members.
SELECT pg.peer_group_name,
       c.company_name,
       s.broad_sector,
       s.sub_sector
  FROM peer_groups pg
  JOIN companies c ON c.id = pg.company_id
  LEFT JOIN sectors s ON s.company_id = c.id
 WHERE pg.is_benchmark = '1'
 ORDER BY pg.peer_group_name, c.company_name;