-- Warning: the comments [...] are used to prevent the method Database.execute_non_select()
-- from splitting a function into multiple statements, which would cause an error.


-- Simple wrapper around COALESCE (commodity function):
-- identity function that returns an arbitrary integer if the input is NULL.

CREATE OR REPLACE FUNCTION nn(x BIGINT) 
RETURNS BIGINT AS $$
    SELECT COALESCE(x, 42); -- [...]
$$ LANGUAGE sql IMMUTABLE;

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

-- Decrypt a message of the sqlab_msg table. Being given a token, attempt to decrypt all the
-- messages in the table and return the first NOT NULL decrypted message, if any. Otherwise,
-- return a fallback message.

CREATE OR REPLACE FUNCTION pgp_sym_decrypt_null_on_err(msg bytea, token text) RETURNS text AS $$
BEGIN
  RETURN pgp_sym_decrypt(msg, token, 'cipher-algo=aes256'); -- [...]
EXCEPTION
  WHEN external_routine_invocation_exception THEN
    RETURN NULL; -- [...]
END; -- [...]
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION decrypt(token BIGINT)
RETURNS TEXT AS $$
BEGIN
    RETURN (
        SELECT COALESCE(
                 MAX(pgp_sym_decrypt_null_on_err(msg::bytea, token::text)),
                 '{preamble_default}' -- fallback message
               )
        FROM sqlab_msg
    ); -- [...]
END; -- [...]
$$ LANGUAGE plpgsql IMMUTABLE;
