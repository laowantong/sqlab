-- Warning: the comments [...] are used to prevent the method Database.execute_non_select()
-- from splitting a function into multiple statements, which would cause an error.


-- Simple wrapper around COALESCE (commodity function):
-- identity function that returns an arbitrary integer if the input is NULL.

CREATE OR REPLACE FUNCTION nn(x BIGINT) 
RETURNS BIGINT AS $$
    SELECT COALESCE(x, 42); -- [...]
$$ LANGUAGE sql IMMUTABLE;


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

-- Create a user-defined aggregate function that calculates the bitwise XOR of a series of
-- NUMERIC values. The built-in bitwise function bit_xor() only works with integer types, which
-- causes an error with the formulas using bit_xor(sum(...)) in the SQL queries. PostgreSQL
-- allows function overloading by argument types, so defining bit_xor(NUMERIC) does not interfere
-- with the built-in bit_xor(INTEGER).

CREATE OR REPLACE FUNCTION bit_xor_accum(state BIGINT, value NUMERIC)
RETURNS BIGINT AS $$
BEGIN
    RETURN state # CAST(value AS BIGINT); -- [...]
END; -- [...]
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE AGGREGATE bit_xor(NUMERIC) (
    SFUNC = bit_xor_accum,
    STYPE = BIGINT,
    INITCOND = '0'
);
