CREATE FUNCTION salt_{i:03d}(x BIGINT) RETURNS BIGINT DETERMINISTIC RETURN x ^ {y};
