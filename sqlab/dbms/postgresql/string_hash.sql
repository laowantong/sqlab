-- Calculate a 40-bit SHA2 hash from a string.
-- Intended usage: to populate a column `hash` identifying rows in a cross-table manner.
--
-- Example: string_hash(JSON_ARRAY(1, "Paul Backerman", 1, "m"))
--
-- Algorithm: from the 16 hexadecimal characters of the SHA2 hash, take the leftmost 10 (which
-- correspond to 40 bits, since each character represents 4 bits), and convert them from base 16
-- to base 10. Since BIGINT is a 64-bit integer, we can safely store 40 bits in it and still have
-- 24 bits left for further calculations.

-- The comments [...] are used to prevent the method Database.execute_non_select() from
-- splitting a function into multiple statements, which would cause an error.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION string_hash(string TEXT) RETURNS BIGINT AS $$
DECLARE
    hex_substr TEXT; -- [...]
    result BIGINT; -- [...]
BEGIN
    -- Compute SHA-256 hash and get hex representation
    hex_substr := LEFT(ENCODE(DIGEST(string, 'sha256'), 'hex'), 10); -- [...]
    
    -- Convert the leftmost 10 hex characters to a BIGINT
    -- PostgreSQL does not have a direct base conversion function like MySQL's CONV(),
    -- so we manually calculate the base 16 to base 10 conversion.
    EXECUTE 'SELECT x''' || hex_substr || '''::bigint' INTO result; -- [...]
    
    RETURN result; -- [...]
END; -- [...]
$$ LANGUAGE plpgsql IMMUTABLE STRICT;