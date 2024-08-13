-- Drop all the functions previously defined, if any.

select undefine(name) from sqlean_define;

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
