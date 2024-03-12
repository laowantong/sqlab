-- This function encapsulates the decryption of a message of the sqlab_msg table.
-- Being given a token, it will attempt to decrypt all the messages in the table
-- and return the first NOT NULL decrypted message, if any. If the token is invalid,
-- the function will return a fallback message.

CREATE OR REPLACE FUNCTION pgp_sym_decrypt_null_on_err(msg bytea, token text) RETURNS text AS $$
BEGIN
  RETURN pgp_sym_decrypt(msg, token, 'cipher-algo=aes256'); -- non-splitting semicolon
EXCEPTION
  WHEN external_routine_invocation_exception THEN
    RETURN NULL; -- non-splitting semicolon
END; -- non-splitting semicolon
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
    ); -- non-splitting semicolon
END; -- non-splitting semicolon
$$ LANGUAGE plpgsql IMMUTABLE;
