CREATE FUNCTION salt_{i:03d}(x NUMERIC) RETURNS BIGINT AS 'SELECT nn($1::BIGINT) # {y};' LANGUAGE sql;
