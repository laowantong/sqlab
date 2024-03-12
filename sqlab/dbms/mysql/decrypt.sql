-- This function encapsulates the decryption of a message of the sqlab_msg table.
-- Being given a token, it will attempt to decrypt all the messages in the table
-- and return the first NOT NULL decrypted message, if any. If the token is invalid,
-- the function will return a fallback message.


DROP FUNCTION IF EXISTS decrypt;

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
            MAX(CONVERT(AES_DECRYPT(msg, token) USING utf8mb4)),
            CONVERT("{preamble_default}" USING utf8mb4) -- fallback message
        ) INTO message
    FROM sqlab_msg;

    RETURN message;
END;
$$

DELIMITER ;
