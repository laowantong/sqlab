CREATE OR REPLACE FUNCTION before_insert_or_update_{table}()
RETURNS TRIGGER AS $$
BEGIN
    NEW.hash := string_hash(json_build_array('{table}', NEW.{columns})::TEXT); -- [...]
    RETURN NEW; -- [...]
END; -- [...]
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS before_insert_{table} ON {table};
CREATE TRIGGER before_insert_{table}
BEFORE INSERT ON {table}
FOR EACH ROW EXECUTE FUNCTION before_insert_or_update_{table}();

DROP TRIGGER IF EXISTS before_update_{table} ON {table};
CREATE TRIGGER before_update_{table}
BEFORE UPDATE ON {table}
FOR EACH ROW EXECUTE FUNCTION before_insert_or_update_{table}();
