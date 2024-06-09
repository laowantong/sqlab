import re
import sqlite3
from pathlib import Path

from ...database import AbstractDatabase
from ...text_tools import FAIL, OK, RESET, WARNING

class Database(AbstractDatabase):

    def connect(self):
        self.dbms_version = sqlite3.sqlite_version
        self.cnx = sqlite3.connect(":memory:")
        print(f"{OK}Connected to SQLite {self.dbms_version} with in-memory database.{RESET}")
        if "database" in self.config["cnx"]:
            self.cnx.enable_load_extension(True)
            print(f"Loading SQLite extensions...")
            for path in self.config["extensions"]:
                path = str(Path(path).expanduser().resolve())
                self.cnx.load_extension(path)
                print(f"  {path}")
            script = self.config["sql_dump_path"].read_text()
            self.cnx.executescript(script)

    def get_headers(self, table: str, keep_auto_increment_columns=True) -> list[str]:
        # Get table info
        cursor = self.cnx.cursor()
        cursor.execute(f"PRAGMA table_info({table});")
        rows = cursor.fetchall()

        headers = []
        for row in rows:
            column_name = row[1]
            data_type = row[2]
            is_primary_key = row[5]
            if not keep_auto_increment_columns and is_primary_key and data_type.upper() == "INTEGER":
                # In SQLite, a column with type INTEGER PRIMARY KEY is an alias for the ROWID
                # (except in WITHOUT ROWID tables) which is always a 64-bit signed integer.
                # On an INSERT, if the ROWID or INTEGER PRIMARY KEY column is not explicitly
                # given a value, then it will be filled automatically with an unused integer,
                # usually one more than the largest ROWID currently in use. This is true regardless
                # of whether or not the AUTOINCREMENT keyword is used.
                continue
            headers.append(column_name)
        headers = [header for header in headers if header != "hash"]
        return headers
    
    def get_table_names(self) -> list[str]:
        query = """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
                AND name NOT LIKE 'sqlab_%'
                AND name NOT IN ('sqlean_define', 'decrypt');
        """
        cursor = self.cnx.cursor()
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def encrypt(self, clear_text, token):
        query = f"SELECT encode(sha256({token}), 'hex') || encode(brotli({repr(clear_text)}), 'hex');"
        return repr(self.execute_select(query)[2][0][0])
    
    def decrypt(self, encrypted, token):
        query = f"SELECT replace(cast(brotli_decode(decode({repr(encrypted[65:-1])}, 'hex')) as text), '\\n', x'0A')"
        return self.execute_select(query)[2][0][0]
    
    def execute_non_select(self, queries):
        statements = [
            s
            for statement in re.split(r";\s*\n+", queries)  # Split on trailing semicolons
            if (s := statement.strip()) # and remove empty strings
        ]
        total_affected_rows = 0
        cursor = self.cnx.cursor()  # Directly create a cursor without 'with'
        try:
            for statement in statements:
                cursor.execute(statement)
                total_affected_rows += cursor.rowcount
        finally:
            cursor.close()  # Ensure cursor is properly closed after operations
        self.cnx.commit()  # Commit any changes made by the statements
        return total_affected_rows

    def parse_ddl(self, queries: str):
        self.db_creation_queries = ""
        self.tables_creation_queries = queries
        self.fk_constraints_queries = "PRAGMA foreign_keys = ON;"
        self.drop_fk_constraints_queries = "PRAGMA foreign_keys = OFF;"

    def create_database(self):
        pass

    @staticmethod
    def reset_table_statement(table: str) -> str:
        return f"DELETE FROM {table};\n"

    def call_function(self, function_name, *args):
        if function_name == "decrypt":
            cursor = self.cnx.cursor()
            query = f"SELECT * FROM decrypt({args[0]});"
            cursor.execute(query)
            return cursor.fetchone()
        else:
            return super().call_function(function_name, *args)
