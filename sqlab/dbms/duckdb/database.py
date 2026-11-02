import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import duckdb

from ...database import AbstractDatabase
from ...text_tools import FAIL, OK, RESET, WARNING


class Database(AbstractDatabase):
    def connect(self):
        database = self.config["cnx"].get("database", ":memory:")
        if database == ":memory:":
            self.cnx = duckdb.connect(":memory:", config={'allow_unsigned_extensions': 'true'})
            display_name = ":memory:"
        else:
            db_path = Path(database)
            if not db_path.is_absolute():
                config_dir = Path(self.config["cnx_path"]).parent
                db_path = (config_dir / db_path).resolve()
            self.cnx = duckdb.connect(str(db_path), config={'allow_unsigned_extensions': 'true'})
            display_name = str(db_path)

        # Load duckpgq
        try:
            self.cnx.execute("SET custom_extension_repository = 'http://duckpgq.s3.eu-north-1.amazonaws.com'")
            self.cnx.execute("FORCE INSTALL 'duckpgq'")
            self.cnx.execute("LOAD 'duckpgq'")
            print(f"{OK}duckpgq graph extension loaded{RESET}")
        except Exception as e:
            print(f"{WARNING}duckpgq unavailable: {e}{RESET}")

        self.dbms_version = self.cnx.execute("SELECT version()").fetchone()[0]
        print(f"{OK}Connected to {self.config['dbms']} {self.dbms_version} with database {repr(display_name)}.{RESET}")

    def get_headers(self, table: str, keep_auto_increment_columns=True) -> list[str]:
        cursor = self.cnx.cursor()
        cursor.execute(f"PRAGMA table_info('{table}')")
        rows = cursor.fetchall()
        return [row[1] for row in rows]

    def get_data_headers(self, table: str) -> list[str]:
        headers = self.get_headers(table)
        return [h for h in headers if h != "hash"]

    def get_table_names(self) -> list[str]:
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_type = 'BASE TABLE'
              AND table_name NOT LIKE 'sqlab_%'
              AND table_name NOT LIKE 'duckpg%'
              AND table_name NOT LIKE '__duckpgq%'
        """
        cursor = self.cnx.cursor()
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]

    def sql_escape(self, s: str) -> str:
        """Escape string for SQL literal."""
        return s.replace("\\", "\\\\").replace("'", "''")

    def encrypt(self, plain: str, token: int) -> str:
        cleaned = self.sql_escape(plain)
        query = f"SELECT encrypt('{cleaned}', {token})"
        return repr(self.execute_select(query)[2][0][0])

    def decrypt(self, encrypted: str, token: int) -> str:
        query = f"SELECT decode(from_base64(substr({encrypted}, 65)))"
        return self.execute_select(query)[2][0][0]

    def execute_non_select(self, text: str) -> int:
        if not text.strip():
            return 0
        raw_parts = re.split(r";\s*\n+", text)
        statements = []
        for part in raw_parts:
            s = part.strip()
            if s:
                statements.append(s)

        total_affected_rows = 0
        cursor = self.cnx.cursor()
        try:
            for stmt in statements:
                cursor.execute(stmt)
                n = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
                total_affected_rows += n
                m = re.match(r"INSERT\s+INTO\s+(\w+)", stmt, re.IGNORECASE)
                if m:
                    table = m.group(1)
                    if not table.lower().startswith("sqlab_"):
                        self._update_hashes(table)
        finally:
            cursor.close()
        self.cnx.commit()
        return total_affected_rows

    def _update_hashes(self, table: str):
        data_headers = self.get_data_headers(table)
        if not data_headers:
            return
        # Create a flat string like "department|1|Engineering|500000"
        col_list = ", ".join(
            f"COALESCE(CAST({h} AS VARCHAR), 'NULL')"
            for h in data_headers
        )
        concat_expr = f"CONCAT('table:', '{table}', '|', {col_list})"
        query = f"""
            UPDATE {table}
            SET hash = string_hash({concat_expr})
            WHERE coalesce({table}.hash, 0) = 0;
        """
        cursor = self.cnx.cursor()
        try:
            cursor.execute(query)
        except Exception as e:
            print(f"{WARNING}Could not update hashes for '{table}': {e}{RESET}")
        finally:
            cursor.close()
        self.cnx.commit()

    def parse_ddl(self, queries: str):
        self.db_creation_queries = ""
        self.tables_creation_queries = queries
        self.fk_constraints_queries = ""
        self.drop_fk_constraints_queries = "" #DuckDB allows circular FK references during CREATE TABLE (lazy enforcement)

    def create_database(self):
        database = self.config["cnx"].get("database", ":memory:")
        db_path = Path(database)
        if not db_path.is_absolute():
            config_dir = Path(self.config["cnx_path"]).parent
            db_path = (config_dir / db_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
        self.cnx = duckdb.connect(str(db_path))
        self.config["cnx"]["database"] = str(db_path)
        print(f"DuckDB database '{db_path}' created.")

    @staticmethod
    def to_json(value: Any) -> str:
        s = json.dumps(value, ensure_ascii=True)
        s = s.replace("'", "''")
        return s

    @staticmethod
    def reset_table_statement(table: str) -> str:
        return f"DELETE FROM {table};\n"

    def call_function(self, function_name, *args):
        if function_name == "decrypt":
            cursor = self.cnx.cursor()
            cursor.execute(f"SELECT * FROM decrypt({','.join(str(a) for a in args)});")
            return cursor.fetchone()
        cursor = self.cnx.cursor()
        placeholders = ", ".join(["?"] * len(args))
        query = f"SELECT {function_name}({placeholders});"
        cursor.execute(query, list(args))
        return cursor.fetchone()

    def close(self):
        self.cnx.close()
