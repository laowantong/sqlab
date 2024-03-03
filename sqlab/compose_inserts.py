import unicodedata
from ast import literal_eval
from pathlib import Path

from .text_tools import WARNING, RESET, OK
from .text_tools import repr_single

def compose_message_inserts(db, rows: list[str]) -> str:
    """
    Given a sequence of rows (token, plain message), return a string of SQL commands to
    insert their encrypted version in the `sqlab_msg` table. No actual insertion is
    performed. The db argument is only required to use the encrypt() method.
    """
    commands = ["\nDELETE FROM sqlab_msg;"]
    commands.append("\nINSERT INTO sqlab_msg (msg) VALUES")
    round_trip_errors = 0
    for (token, plain) in rows:
        plain = plain.replace("\u00A0", " ") # Replace non-breaking spaces with normal spaces.
        encrypted = db.encrypt(plain, token)
        commands.append(f"  ({encrypted}),")
        # Check the round trip
        decrypted = db.decrypt(encrypted, token)
        if decrypted != plain:
            if decrypted is None:
                print(f"{WARNING}Unable to decrypt the message for token {token}\n{RESET}")
            else:
                print(f"{WARNING}Unable to round-trip the message for token {token}\n{RESET}")
            print(plain)
            round_trip_errors += 1
    if round_trip_errors:
        print(f"{WARNING}Round-trip errors have been detected (see above).")
        print(f"The origin of the problem is currently unknown, but it usually disappears")
        print(f"by picking another salt function.{RESET}")

    commands[-1] = commands[-1].rstrip(",")
    commands.append(";")
    return "\n".join(commands)


def compose_data_inserts(config: dict, db, trigger_template) -> str:
    """ Return a string of SQL commands to insert the data from the TSV files into the database.
    No actual insertion is performed. The db argument is only used to retrieve the colum names
    of the database just created from the `ddl.sql` file. """
    data_dir = Path(config["data_dir"])
    tsv_row_to_sql_values = TsvRowToSqlValues(config)
    result = []
    for tsv_path in data_dir.glob("*.tsv"):
        table = unicodedata.normalize('NFC', tsv_path.stem) # On macOS, the filenames use NFD, while MySQL is expecting NFC.
        headers = db.get_headers(table) # Columns to be hashed.
        triggers = trigger_template.format(table=table, columns=', NEW.'.join(headers))
        headers = db.get_headers(table, keep_auto_increment=False) # Columns to be inserted.
        tsv_row_to_sql_values.set_wrappers(headers)
        insertions = [f"INSERT INTO {table} ({', '.join(headers)}) VALUES"]
        for row in tsv_path.read_text().splitlines():
            if not row:
                continue
            insertions.append(tsv_row_to_sql_values(row))
        insertions[-1] = insertions[-1].rstrip(",")
        insertions.append(";")
        result.append(triggers)
        result.append(db.reset_table_statement(table))
        result.append("\n".join(insertions))
    if not result:
        print(f"{WARNING}Missing directory '{data_dir}' or no '*.tsv' files in it.{RESET}")
    return "\n".join(result)


class TsvRowToSqlValues:
    """
    Since the tables are given as TSV files, all values are strings. This class converts them
    to the appropriate SQL representation. Some converted values are unquoted: NULL, integers,
    floats, booleans. Strings are always single-quoted, and the inner single quotes are doubled.
    See the tests for more edge cases.
    """

    def __init__(self, config: dict):
        self.empty_cells = config.get("empty_cells") or [""]
        self.null_cells = config.get("null_cells") or ["NULL", "\\N", "None"]
        self.field_subs = config.get("field_subs") or {}

    def __call__(self, row: str) -> str:
        """Convert a TSV row to its SQL representation."""
        values = []
        for (wrapper, field) in zip(self.wrappers, row.split("\t")):
            values.append(wrapper(field))
        return f'  ({", ".join(values)}),'

    def set_wrappers(self, headers: list[str]):
        """
        Set the functions to be applied to the fields of the TSV row. By default, each field is
        transformed by self.str_to_repr(). But some transformations may instead be specified in
        the configuration file. For instance, a number of days may be stored as an integer in
        MySQL, but as an INTERVAL in PostgreSQL. In the latter case, the field_subs dictionary
        would contain a mapping from the header to the transformation.
        """
        self.wrappers = [self.field_subs.get(header, self.str_to_repr) for header in headers]

    def str_to_repr(self, cell: str) -> str:
        """Convert a string to its SQL representation."""
        if cell in self.null_cells:
            return "NULL"
        if cell in self.empty_cells:
            return "''"
        try:
            value = literal_eval(cell)
            if isinstance(value, str):
                return "'" + cell.replace("'", "''") + "'"
            elif value is None: # and "None" is not in null_cells
                return "'None'"
            else: # int, float, bool
                return repr(value)
        except (ValueError, SyntaxError):
            return "'" + cell.replace("'", "''") + "'"

