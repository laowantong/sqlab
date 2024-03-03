-- This procedure encapsulates the decryption of a message of the sqlab_msg table.
-- Being given a token, it will attempt to decrypt all the messages in the table
-- and return the first NOT NULL decrypted message, if any. If the token is invalid,
-- the procedure will return a fallback message.


DROP PROCEDURE IF EXISTS `decrypt`;

DELIMITER $$

CREATE PROCEDURE `decrypt` (IN `token` BIGINT UNSIGNED)
    SQL SECURITY INVOKER
    COMMENT "{close_dialog}"
BEGIN
    DECLARE CONTINUE HANDLER FOR SQLWARNING
    BEGIN
        -- Just ignore the decoding warnings, since all are designed to fail (except at most one).
    END;

    SELECT
        COALESCE(
            MAX(CONVERT(AES_DECRYPT(msg, token) USING utf8mb4)),
            CONVERT("{preamble_no_hint}" USING utf8mb4) -- fallback message
        ) AS message
    FROM sqlab_msg;
END;
$$

DELIMITER ;
