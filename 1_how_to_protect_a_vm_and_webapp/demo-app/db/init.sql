-- Ensures the table/row exist even before Flask bootstraps (defense in depth)
CREATE TABLE IF NOT EXISTS totals (
    id  INT PRIMARY KEY,
    sum INT NOT NULL DEFAULT 0
);
INSERT INTO totals (id, sum) VALUES (1, 0) ON CONFLICT (id) DO NOTHING;
