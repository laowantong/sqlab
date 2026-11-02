-- nn: return 0 for NULL (additive identity, safe for SUM fingerprinting).
CREATE OR REPLACE MACRO nn(x) AS coalesce(x, 0);

-- string_hash: 40-bit integer from a string.
-- sha256() in DuckDB returns a 64-char lowercase hex VARCHAR natively.
-- regexp_replace removes hex letters [a-f], leaving only digits; take first 12.
CREATE OR REPLACE MACRO string_hash(x) AS (
    CAST(
        regexp_replace(
            sha256(CAST(x AS VARCHAR))::VARCHAR,
            '[a-f]',
            '',
            'g'
        )[:12]
    AS BIGINT)
);

CREATE OR REPLACE MACRO encrypt(msg, token) AS
  sha256(CAST(token AS VARCHAR))::VARCHAR || to_base64(encode(msg));


-- decrypt: table macro (DuckDB equivalent of SQLite's CREATE VIRTUAL TABLE).
-- Stored message format: sha256(token)[64 hex chars] || base64(plaintext).
-- from_base64(VARCHAR) -> BLOB, decode(BLOB) -> VARCHAR.
CREATE OR REPLACE MACRO decrypt(token) AS TABLE
    SELECT msg AS msg
    FROM (
        SELECT 1 AS priority,
               decode(from_base64(substr(msg, 65))) AS msg
        FROM sqlab_msg
        WHERE substr(msg, 1, 64) = sha256(CAST(token AS VARCHAR))::VARCHAR
        UNION ALL
        SELECT 2 AS priority,
               '{preamble_default}' AS msg
    ) sub
    ORDER BY priority
    LIMIT 1;

