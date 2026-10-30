def _fulltext(cell):
    if not cell:
        return "''"
    # The tsvector literal already contains single quotes; just cast it.
    escaped = cell.replace("'", "''")
    return f"'{escaped}'::tsvector"

def _special_features(cell):
    if not cell:
        return "ARRAY[]::text[]"
    # Input looks like: {"Deleted Scenes","Behind the Scenes"}
    items = [i.strip().strip('"') for i in cell.strip('{}').split(',')]
    quoted = ', '.join(f"'{item}'" for item in items)
    return f"ARRAY[{quoted}]"

def _timestamp(cell):
    return f"'{cell}'::timestamp" if cell and cell != r'\N' else 'NULL'

config = {
    "dbms": "postgresql",
    "cnx_path": "./cnx.ini",
    "language": "en",
    "ddl_path": "./ddl.sql",
    "dataset_dir": "./dataset",
    "relational_schema_dir": "./relational_schema",
    "source_path": "./records.json",
    "markdown_to": "txt",
    "metadata": {},
    "field_subs": {
        "fulltext": _fulltext,
        "special_features": _special_features,
        "rental_date": _timestamp,
        "last_update": _timestamp,
    },
}
