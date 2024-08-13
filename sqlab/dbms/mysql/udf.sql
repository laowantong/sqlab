-- Simple wrapper around COALESCE (commodity function):
-- identity function that returns an arbitrary integer if the input is NULL.

CREATE FUNCTION nn(x BIGINT) RETURNS BIGINT DETERMINISTIC 
RETURN COALESCE(x, 42);


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
