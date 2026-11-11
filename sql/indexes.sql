-- =====================================================================
-- indexes.sql : speeds up GROUP BY / JOIN / duplicate checks.
-- Created AFTER the bulk load (building an index once is much faster
-- than updating it on every insert).
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_raw_complaint_id  ON complaints_raw (complaint_id);
CREATE INDEX IF NOT EXISTS idx_raw_company       ON complaints_raw (company);
CREATE INDEX IF NOT EXISTS idx_raw_product       ON complaints_raw (product);
CREATE INDEX IF NOT EXISTS idx_raw_state         ON complaints_raw (state);
CREATE INDEX IF NOT EXISTS idx_raw_date_received ON complaints_raw (date_received);
