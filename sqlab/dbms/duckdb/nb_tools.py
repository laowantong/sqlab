from ...nb_tools import *
import sqlalchemy


def get_engine(config: dict = None, database: str = ":memory:"):
    """
    Return a SQLAlchemy engine connected to DuckDB.
    Requires: pip install duckdb-engine
    DuckDB is file-based: no host, port, username or password.
    """
    if config is not None:
        database = config["cnx"].get("database", ":memory:")
    return sqlalchemy.create_engine(f"duckdb:///{database}")