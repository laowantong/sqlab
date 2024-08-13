-- Calculate a 40-bit SHA2 hash from a string.
--
-- Intended usages and examples:
-- 1. Create a cross-table row identifier by hashing a concatenation of the row's fields.
--      string_hash(json_build_array(1, 'Paul Backerman', 1, 'm')::TEXT)
-- 2. Check the replacement string of the tweak placeholder (0.0).
--      salt_009(string_hash('Joplette') + sum(hash) OVER ()) AS token
--
-- Algorithm: from the 64 hexadecimal characters of the SHA2 hash, take the leftmost 10 (which
-- correspond to 40 bits, since each character represents 4 bits), and convert them from base 16
-- to base 10. Since BIGINT is a 64-bit integer, we can safely store 40 bits in it and still have
-- 24 bits left for further calculations.

CREATE OR REPLACE FUNCTION jsonb_build_array_imm(VARIADIC input anyarray) RETURNS JSONB AS $$
  SELECT jsonb_agg(elem)
  FROM unnest(input) AS elem
$$
LANGUAGE SQL IMMUTABLE PARALLEL SAFE;

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
    EXECUTE 'SELECT x''' || hex_substr || '''::bigint' INTO result; -- [...] '
    
    RETURN result; -- [...]
END; -- [...]
$$ LANGUAGE plpgsql IMMUTABLE STRICT;
