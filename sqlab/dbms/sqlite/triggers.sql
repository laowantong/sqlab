DROP TRIGGER IF EXISTS after_insert_{table};
CREATE TRIGGER after_insert_{table}
AFTER INSERT ON {table}
FOR EACH ROW
BEGIN
    UPDATE {table}
    SET hash = string_hash(json_array('{table}', {new_columns}))
    WHERE rowid = NEW.rowid; -- [...]
END;

DROP TRIGGER IF EXISTS after_update_{table};
CREATE TRIGGER after_update_{table}
AFTER UPDATE OF {columns} ON {table}
FOR EACH ROW
WHEN (OLD.hash <> string_hash(json_array('{table}', {new_columns})))
BEGIN
    UPDATE {table}
    SET hash = string_hash(json_array({new_columns}))
    WHERE rowid = NEW.rowid AND (OLD.hash <> string_hash(json_array('{table}', {new_columns}))); -- [...]
END;
