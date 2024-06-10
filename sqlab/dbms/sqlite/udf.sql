-- Drop all the functions previously defined, if any.

select undefine(name) from sqlean_define;

-- Simple wrapper around COALESCE (commodity function): identity function that returns an
-- arbitrary integer if the input is NULL.
-- Note that the function takes one positional argument, denoted by ?1 in the body.

SELECT define('nn', 'coalesce(?1, 42)');

-- Calculate a 40-bit hash from a string.
--
-- Intended usages and examples:
-- 1. Create a cross-table row identifier by hashing a concatenation of the row's fields.
--      select string_hash(concat_ws(',', 1, 'Paul Backerman', 1, 'm'))
-- 2. Check the replacement string of the tweak placeholder (0.0).
--      select salt_009(string_hash('Joplette') + sum(hash) OVER ()) AS token
--
-- Algorithm: this function first computes the SHA-256 hash of the input, encodes it as a
-- hexadecimal string, keeps only the decimal digits, and finally casts the result to an
-- integer. The hexadecimal string being 64 characters long, the decimal string has an
-- average of 64 * 10 / 16 = 40 decimal digits. Of those, the first 12 are kept: since
-- log2(10**12 - 1) = 39.86, the resulting number is at most 40 bits long.
---
-- Rationale: as of 2024, SQLite has no built-in function to convert between hexadecimal
-- strings and integers. Workarounds are possible, but require either a recursive CTE [1]
-- or a loadable function [2]. Fortunately, we are not interested in an exact conversion,
-- and just want a big, stable, reasonably unique integer.
--
-- Dependencies: SQLite extensions to be installed with [3]:
--   sqlpkg install nalgeon/crypto
--   sqlpkg install nalgeon/define
--   sqlpkg install nalgeon/regexp
--   sqlpkg install nyurik/compressions
--
-- [1] https://stackoverflow.com/a/75592771/173003
-- [2] https://stackoverflow.com/a/72394578/173003
-- [3] https://github.com/nalgeon/sqlpkg-cli

SELECT define(
    'string_hash',
    'cast(
        substr(
            regexp_replace(
                encode(
                    sha256(?1),
                    ''hex''),
                ''[a-f]'',
                ''''),
            1,
            12)
        as integer)'
    );

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
