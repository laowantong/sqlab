-- Calculate a 40-bit SHA2 hash from a string.
--
-- Intended usages and examples:
-- 1. Create a cross-table row identifier by hashing a concatenation of the row's fields.
--      string_hash(CAST(JSON_ARRAY(1, 'Paul Backerman', 1, 'm') AS CHAR))
-- 2. Check the replacement string of the tweak placeholder (0.0).
--      salt_009(string_hash('Joplette') + sum(hash) OVER ()) AS token
--
-- Algorithm: from the 64 hexadecimal characters of the SHA2 hash, take the leftmost 10 (which
-- correspond to 40 bits, since each character represents 4 bits), and convert them from base 16
-- to base 10. Since BIGINT is a 64-bit integer, we can safely store 40 bits in it and still have
-- 24 bits left for further calculations.

CREATE FUNCTION string_hash(string LONGTEXT)
RETURNS BIGINT DETERMINISTIC
RETURN CONV(LEFT(SHA2(string, 256), 10), 16, 10);
