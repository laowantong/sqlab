import importlib


def database_factory(config: dict):
    """Return a Database object according to the vendor specified in the configuration."""
    vendor = config["vendor"].lower()
    db = importlib.import_module(".database", package=f"sqlab.dbms.{vendor}").Database
    return db(config)


class AbstractDatabase:
    """
    To be inherited by the vendor-specific database classes.
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

    def get_headers(self, table: str, keep_auto_increment=True) -> list[str]:
        """
        Retrieve the column names of the given table. Always exclude the hash column.
        On demand, exclude the auto_increment columns (for insertion and, in MySQL,
        for insertion and hash calculation).
        """
        raise NotImplementedError

    def encrypt(self, plain: str, token: int) -> str:
        """Return the encrypted version of the given plain text."""
        raise NotImplementedError

    def execute_non_select(self, query: str) -> int:
        """Execute the given query and return the number of affected rows."""
        raise NotImplementedError

    def execute_select(self, query: str) -> tuple[list[str], list[str], list[tuple]]:
        """Execute the given query and return the headers, datatypes and rows of the result."""
        raise NotImplementedError

    def call_procedure(self, name: str, args: list[str]):
        """Call the given procedure with the given arguments."""
        raise NotImplementedError

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

    @staticmethod
    def reset_table_statement(table: str) -> str:
        """Return a query suppressing all rows and resetting the auto increment."""
        raise NotImplementedError

    def close(self):
        self.cnx.close()
