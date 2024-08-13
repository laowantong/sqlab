-- Simple wrapper around COALESCE (commodity function): identity function that returns an
-- arbitrary integer if the input is NULL.
-- Note that the function takes one positional argument, denoted by ?1 in the body.

SELECT define('nn', 'coalesce(?1, 42)');


-- Unobfuscate a message of the sqlab_msg table. Being given a token, if a message's 64 first
-- characters match the SHA-256 hash of the token:
--   1. extract the remaining characters (an hexadecimal string);
--   2. decode the hexadecimal string as a binary string;
--   3. decompress the binary string as a text string (https://fr.wikipedia.org/wiki/Brotli);
--   4. replace the newline characters with the byte 0x0A (SQLite has no escape sequences);
--   5. return the result.
-- If no message header matches the token, fall back on a default message.
--
-- IMPLEMENTATION NOTES
--   1. Although UNION ALL usually **appends** its operands, there is no guarantee on the order
--      of the resulting rows. The priority column and the ORDER BY clause ensure that the message
--      to be displayed is the first one.
--   2. The syntax `select define(NAME, BODY)` doesn't support a `SELECT` statement in the body.
--      The syntax `eval('SELECT ...')` doesn't support arguments.
--      As a workaround, we define a function capable of returning a full table of values, although
--      we only need one. This function should be called with: `SELECT * FROM decrypt(token)`
--      instead of `SELECT decrypt(token)` as in MySQL or PostgreSQL.

CREATE VIRTUAL TABLE decrypt USING define((
    SELECT msg
    FROM (
        SELECT 1 AS priority
             , replace(cast(brotli_decode(decode(substr(msg, 65), 'hex')) as text), '\n', x'0A') AS msg
        FROM sqlab_msg
        WHERE substr(msg, 1, 64) = encode(sha256(?1), 'hex')
        UNION ALL
        SELECT 2 AS priority
             , '{preamble_default}' AS msg
    ) AS subquery
    ORDER BY priority
    LIMIT 1
));
