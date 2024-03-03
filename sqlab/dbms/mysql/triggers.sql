DROP TRIGGER IF EXISTS before_insert_{table};
CREATE TRIGGER before_insert_{table}
BEFORE INSERT ON {table}
FOR EACH ROW
SET NEW.hash = string_hash(CAST(JSON_ARRAY("{table}", NEW.{columns}) AS CHAR));

DROP TRIGGER IF EXISTS before_update_{table};
CREATE TRIGGER before_update_{table}
BEFORE UPDATE ON {table}
FOR EACH ROW
SET NEW.hash = string_hash(CAST(JSON_ARRAY("{table}", NEW.{columns}) AS CHAR));
