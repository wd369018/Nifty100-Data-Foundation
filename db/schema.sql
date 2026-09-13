PRAGMA foreign_keys = ON;

-- ============================================================
-- NIFTY 100 FINANCIAL INTELLIGENCE PLATFORM
-- SQLite Database Schema
-- Sprint 1 - Day 04
-- ============================================================


-- ============================================================
-- 1. COMPANIES
-- Master company reference table
-- ============================================================

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    company_logo TEXT,
    company_name TEXT NOT NULL,
    chart_link TEXT,
    about_company TEXT,
    website TEXT,
    nse_profile TEXT,
    bse_profile TEXT,
    face_value NUMERIC NOT NULL,
    book_value NUMERIC,
    roce_percentage NUMERIC,
    roe_percentage NUMERIC
);


-- ============================================================
-- 2. PROFIT AND LOSS
-- Annual P&L statements
-- ============================================================

CREATE TABLE IF NOT EXISTS profitandloss (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    sales NUMERIC NOT NULL,
    expenses NUMERIC NOT NULL,
    operating_profit NUMERIC NOT NULL,
    opm_percentage NUMERIC NOT NULL,
    other_income NUMERIC,
    interest NUMERIC,
    depreciation NUMERIC,
    profit_before_tax NUMERIC,
    tax_percentage NUMERIC,
    net_profit NUMERIC,
    eps NUMERIC,
    dividend_payout NUMERIC,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, year)
);


-- ============================================================
-- 3. BALANCE SHEET
-- Annual balance sheet
-- ============================================================

CREATE TABLE IF NOT EXISTS balancesheet (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    equity_capital NUMERIC NOT NULL,
    reserves NUMERIC,
    borrowings NUMERIC,
    other_liabilities NUMERIC,
    total_liabilities NUMERIC NOT NULL,
    fixed_assets NUMERIC,
    cwip NUMERIC,
    investments NUMERIC,
    other_asset NUMERIC,
    total_assets NUMERIC NOT NULL,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, year)
);


-- ============================================================
-- 4. CASH FLOW
-- Annual cash flow statements
-- ============================================================

CREATE TABLE IF NOT EXISTS cashflow (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    operating_activity NUMERIC,
    investing_activity NUMERIC,
    financing_activity NUMERIC,
    net_cash_flow NUMERIC,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, year)
);


-- ============================================================
-- 5. ANALYSIS
-- Pre-computed growth metrics
-- Partial company coverage
-- ============================================================

CREATE TABLE IF NOT EXISTS analysis (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    compounded_sales_growth TEXT,
    compounded_profit_growth TEXT,
    stock_price_cagr TEXT,
    roe TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- ============================================================
-- 6. DOCUMENTS
-- Annual report repository
-- ============================================================

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    annual_report TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, year)
);


-- ============================================================
-- 7. PROS AND CONS
-- Qualitative investment insights
-- ============================================================

CREATE TABLE IF NOT EXISTS prosandcons (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    pros TEXT,
    cons TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- ============================================================
-- 8. SECTORS
-- Company sector mapping
-- One row per company
-- ============================================================

CREATE TABLE IF NOT EXISTS sectors (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    broad_sector TEXT,
    sub_sector TEXT,
    index_weight_pct NUMERIC,
    market_cap_category TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id)
);


-- ============================================================
-- 9. MARKET CAP
-- Annual valuation multiples
-- ============================================================

CREATE TABLE IF NOT EXISTS market_cap (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    market_cap_crore NUMERIC,
    enterprise_value_crore NUMERIC,
    pe_ratio NUMERIC,
    pb_ratio NUMERIC,
    ev_ebitda NUMERIC,
    dividend_yield_pct NUMERIC,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, year)
);


-- ============================================================
-- 10. STOCK PRICES
-- Monthly OHLCV price history
-- ============================================================

CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    date TEXT NOT NULL,
    open_price NUMERIC,
    high_price NUMERIC,
    low_price NUMERIC,
    close_price NUMERIC,
    volume INTEGER,
    adjusted_close NUMERIC,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, date)
);


-- ============================================================
-- 11. FINANCIAL RATIOS
-- Derived financial metrics
-- ============================================================

CREATE TABLE IF NOT EXISTS financial_ratios (
    id INTEGER PRIMARY KEY,
    company_id TEXT NOT NULL,
    year TEXT NOT NULL,
    net_profit_margin_pct NUMERIC,
    operating_profit_margin_pct NUMERIC,
    return_on_equity_pct NUMERIC,
    return_on_assets_pct NUMERIC,
    debt_to_equity NUMERIC,
    interest_coverage NUMERIC,
    asset_turnover NUMERIC,
    free_cash_flow_cr NUMERIC,
    capex_cr NUMERIC,
    earnings_per_share NUMERIC,
    book_value_per_share NUMERIC,
    dividend_payout_ratio_pct NUMERIC,
    total_debt_cr NUMERIC,
    cash_from_operations_cr NUMERIC,
    revenue_cagr_5yr NUMERIC,
    pat_cagr_5yr NUMERIC,
    eps_cagr_5yr NUMERIC,
    composite_quality_score NUMERIC,
    high_leverage_flag TEXT,
    icr_label TEXT,
    icr_warning_flag TEXT,
    revenue_cagr_5yr_flag TEXT,
    pat_cagr_5yr_flag TEXT,
    eps_cagr_5yr_flag TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, year)
);


-- ============================================================
-- 12. PEER GROUPS
-- Peer group company mapping
-- ============================================================

CREATE TABLE IF NOT EXISTS peer_groups (
    id INTEGER PRIMARY KEY,
    peer_group_name TEXT NOT NULL,
    company_id TEXT NOT NULL,
    is_benchmark TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);


-- ============================================================
-- INDEXES
-- Improve FK and common query performance
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_profitandloss_company_year
    ON profitandloss(company_id, year);

CREATE INDEX IF NOT EXISTS idx_balancesheet_company_year
    ON balancesheet(company_id, year);

CREATE INDEX IF NOT EXISTS idx_cashflow_company_year
    ON cashflow(company_id, year);

CREATE INDEX IF NOT EXISTS idx_analysis_company
    ON analysis(company_id);

CREATE INDEX IF NOT EXISTS idx_documents_company_year
    ON documents(company_id, year);

CREATE INDEX IF NOT EXISTS idx_prosandcons_company
    ON prosandcons(company_id);

CREATE INDEX IF NOT EXISTS idx_sectors_company
    ON sectors(company_id);

CREATE INDEX IF NOT EXISTS idx_market_cap_company_year
    ON market_cap(company_id, year);

CREATE INDEX IF NOT EXISTS idx_stock_prices_company_date
    ON stock_prices(company_id, date);

CREATE INDEX IF NOT EXISTS idx_financial_ratios_company_year
    ON financial_ratios(company_id, year);

CREATE INDEX IF NOT EXISTS idx_peer_groups_company
    ON peer_groups(company_id);


-- ============================================================
-- 13. PEER PERCENTILES
-- Percentile ranks within peer groups (Sprint 3)
-- ============================================================

CREATE TABLE IF NOT EXISTS peer_percentiles (
    id              INTEGER PRIMARY KEY,
    company_id      TEXT NOT NULL,
    peer_group_name TEXT NOT NULL,
    metric          TEXT NOT NULL,
    value           NUMERIC,
    percentile_rank NUMERIC,
    year            TEXT,

    FOREIGN KEY (company_id)
        REFERENCES companies(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    UNIQUE (company_id, peer_group_name, metric)
);

CREATE INDEX IF NOT EXISTS idx_peer_percentiles_group_metric
    ON peer_percentiles(peer_group_name, metric);