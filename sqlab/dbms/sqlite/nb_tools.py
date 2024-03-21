from ...nb_tools import *
import sqlalchemy
from pathlib import Path


def add_connexion_listener(engine, extensions):
    def load_sqlite_extensions(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        dbapi_connection.enable_load_extension(True)
        for extension in extensions:
            path = Path(extension).expanduser().resolve()
            cursor.execute(f"SELECT load_extension('{str(path)}')")
        cursor.close()

    sqlalchemy.event.listen(engine, "connect", load_sqlite_extensions)

def get_engine():
    return sqlalchemy.create_engine("sqlite:///:memory:")
