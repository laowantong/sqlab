-- Commodity function. Simple wrapper around COALESCE:
-- identity function that returns an arbitrary integer if the input is NULL.

DROP FUNCTION IF EXISTS `nn`;
CREATE FUNCTION nn(x BIGINT) RETURNS BIGINT DETERMINISTIC 
RETURN COALESCE(x, 42);
