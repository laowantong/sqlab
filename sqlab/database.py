import importlib


def database_factory(config: dict):
    """Return a Database object according to the dbms specified in the configuration."""
    db = importlib.import_module(".database", package=f"sqlab.dbms.{config['dbms_slug']}")
    return db.Database(config)


class AbstractDatabase:
    """
    To be inherited by the dbms-specific database classes.
    Just a contract to ensure that all the necessary methods are implemented.
    """

    def __init__(self, config: dict):
        """Just store the configuration. The connection will be created later."""
        self.config = config

    def connect(self):
        """
        Create a connection to the database and store it in the cnx attribute.
        Print a message with the server version and the database name.
        """
        raise NotImplementedError
    
    def get_version(self) -> str:
        return self.dbms_version

    def get_headers(self, table: str, keep_auto_increment_columns=True) -> list[str]:
        """
        Retrieve the column names of the given table. Always exclude the hash column.
        On demand, exclude the auto_increment columns (for insertion and, in MySQL,
        for insertion and hash calculation).
        """
        raise NotImplementedError

    def get_table_names(self) -> list[str]:
        """Return the names of all the tables in the DB, except the utility tables.
        These include those starting with "sqlab_", and, in SQLite, the virtual tables
        decrypt and sqlean_define."""
        raise NotImplementedError

    def encrypt(self, plain: str, token: int) -> str:
        """Return the encrypted version of the given plain text."""
        raise NotImplementedError

    def execute_non_select(self, text) -> int:
        """Execute the queries of the given text and return the number of affected rows."""
        raise NotImplementedError

    def execute_select(self, query_text: str) -> tuple[list[str], list[str], list[tuple]]:
        """Execute the given query and return the headers, datatypes and rows of the result."""
        cursor = self.cnx.cursor()
        cursor.execute(query_text)
        rows = cursor.fetchall()
        headers = [desc[0] for desc in cursor.description]
        datatypes = [desc[1] for desc in cursor.description]
        return (headers, datatypes, rows)

    def call_function(self, function_name, *args):
        """Call the given function with the given arguments and return the first row of the result."""
        cursor = self.cnx.cursor()
        placeholders = ', '.join(['%s'] * len(args))
        query = f"SELECT {function_name}({placeholders});"
        cursor.execute(query, args)
        return cursor.fetchone()

    @staticmethod
    def parse_ddl(self, queries: str):
        """
        Separate the query in three parts:
        1. Database creation
        2. Table creation
        3. Foreign key creation
        And create a query for dropping the foreign key constraints.
        """
        raise NotImplementedError
    
    def create_database(self):
        raise NotImplementedError

    @staticmethod
    def reset_table_statement(table: str) -> str:
        """Return a query suppressing all rows and resetting the auto increment."""
        raise NotImplementedError

    def close(self):
        self.cnx.close()
