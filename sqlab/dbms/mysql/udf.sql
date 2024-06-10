-- Simple wrapper around COALESCE (commodity function):
-- identity function that returns an arbitrary integer if the input is NULL.

CREATE FUNCTION nn(x BIGINT) RETURNS BIGINT DETERMINISTIC 
RETURN COALESCE(x, 42);


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


-- Decrypt a message of the sqlab_msg table. Being given a token, attempt to decrypt all the
-- messages in the table and return the first NOT NULL decrypted message, if any. Otherwise,
-- return a fallback message.

DELIMITER $$

CREATE FUNCTION decrypt(token BIGINT UNSIGNED)
RETURNS TEXT
DETERMINISTIC
BEGIN
    DECLARE message TEXT;
    DECLARE CONTINUE HANDLER FOR SQLWARNING
    BEGIN
        -- Just ignore the decoding warnings, since all are designed to fail (except at most one).
    END;

    SELECT
        COALESCE(
            MAX(CONVERT(UNCOMPRESS(AES_DECRYPT(msg, token)) USING utf8mb4)),
            CONVERT("{preamble_default}" USING utf8mb4) -- fallback message
        ) INTO message
    FROM sqlab_msg;

    RETURN message;
END;
$$

DELIMITER ;
