-- Commodity functions

-- The comments [...] are used to prevent the method Database.execute_non_select() from
-- splitting a function into multiple statements, which would cause an error.

-- Simple wrapper around COALESCE: identity function that returns an arbitrary integer
-- if the input is NULL.

CREATE OR REPLACE FUNCTION nn(x BIGINT) 
RETURNS BIGINT AS $$
    SELECT COALESCE(x, 42); -- [...]
$$ LANGUAGE sql IMMUTABLE;

-- A drop-in replacement for the MysQL function CRC32. Actually, it calculates the
-- first 8 characters of the MD5 hash of the input string and converts it to an integer.

CREATE OR REPLACE FUNCTION crc32(string TEXT)
RETURNS INTEGER AS $$
BEGIN
    RETURN abs(('x'||substr(md5(string), 1, 8))::bit(32)::int); -- [...]
END; -- [...]
$$ LANGUAGE plpgsql IMMUTABLE STRICT;
