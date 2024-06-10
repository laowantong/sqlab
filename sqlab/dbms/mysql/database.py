import re
import mysql.connector

from ...database import AbstractDatabase
from ...text_tools import FAIL, OK, RESET, WARNING

class Database(AbstractDatabase):

    def connect(self):
        self.cnx = mysql.connector.connect(**self.config["cnx"])
        if self.cnx.is_connected():
            self.dbms_version = self.cnx.get_server_info()
            print(f"{OK}Connected to MySQL {self.dbms_version} with database {repr(self.cnx.database)}.{RESET}")
        else:
            raise mysql.connector.Error.ConnectionError(f"{FAIL}Could not connect to MySQL.{RESET}")

    def get_headers(self, table: str, keep_auto_increment_columns=False) -> list[str]:
        # Note that in MySQL, contrarily to PostgreSQL, keep_auto_increment_columns defaults to False.
        # This will exclude the auto incremented columns from the hash  calculation, since
        # the final value of these columns cannot be used in a before_insert trigger, and an
        # after_insert trigger cannot update the just-inserted row. It would work as intended
        # in a before_update trigger, but maintaining consistency seems to be preferable.
        query = f"""
            SELECT column_name
            FROM information_schema.columns 
            WHERE table_schema = "{self.cnx.database}"
                AND table_name = "{table}"
                AND column_name != "hash"
                AND extra NOT LIKE "%auto_increment%" -- Exclude auto_increment columns
            ORDER BY ordinal_position
        """
        if keep_auto_increment_columns:
            query = re.sub(r"(?m)^.* -- Exclude auto_increment columns\n", "", query)
        headers = []
        with self.cnx.cursor() as cursor:
            cursor.execute(query)
            headers = [row[0] for row in cursor]
        return headers
    
    def get_table_names(self) -> list[str]:
        query = f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = "{self.cnx.database}"
                AND table_name NOT LIKE 'sqlab_%';
        """
        with self.cnx.cursor() as cursor:
            cursor.execute(query)
            return [row[0] for row in cursor]
    
    def encrypt(self, clear_text, token):
        """In MySQL, the function aes_encrypt() takes a numeric key."""
        with self.cnx.cursor() as cursor:
            cursor.execute(f"SELECT HEX(AES_ENCRYPT(COMPRESS({repr(clear_text)}), {token}))")
            return "0x" + next(cursor)[0].lower()
    
    def decrypt(self, encrypted, token):
        query = f"SELECT CONVERT(UNCOMPRESS(AES_DECRYPT({encrypted}, {token})) USING utf8mb4)"
        return self.execute_select(query)[2][0][0]
    
    def execute_non_select(self, text):
        text = re.sub(r"(?m)^DELIMITER (\$\$|;).*", "", text)  # Remove delimiter directives
        text = re.sub(r"(?m)^\$\$.*", "", text)  # Remove // delimiter
        total_affected_rows = 0
        with self.cnx.cursor() as cursor:
            for _ in cursor.execute(text, multi=True):
                total_affected_rows += cursor.rowcount
            self.cnx.commit()
        return total_affected_rows
    
    def parse_ddl(self, queries):
        triple = re.split(r"(?mi)^(?:USE .+|-- FK\b.*)", queries, 2)
        self.db_creation_queries = triple[0]
        self.tables_creation_queries = triple[1]
        try:
            self.fk_constraints_queries = triple[2]
        except IndexError:
            print(f"{FAIL}The foreign key constraints definitions must be separated from the previous parts with a -- FK comment.{RESET}")
        self.drop_fk_constraints_queries = re.sub(
            r"(?s)\bADD CONSTRAINT\s+(.+?)\s+FOREIGN KEY\b.+?([,;]\n)",
            r"DROP FOREIGN KEY \1\2",
            self.fk_constraints_queries,
        )
    
    def create_database(self):
        self.execute_non_select(self.db_creation_queries)

    @staticmethod
    def reset_table_statement(table: str) -> str:
        return f"TRUNCATE TABLE {table};\n"
