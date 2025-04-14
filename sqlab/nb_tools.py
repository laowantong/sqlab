from pathlib import Path
import getpass
import pydoc
import sqlalchemy

from .text_tools import OK, RESET, WARNING

def may_create_connection_file():
    cnx_path = Path("cnx.ini")
    cnx_name = f"{cnx_path.resolve().parent.name}/{cnx_path.name}"
    if cnx_path.exists():
        print(f"{OK}Using the existing connection file '{cnx_name}'.{RESET}")
        return
    print(f"{WARNING}Creating a connection file.{RESET}")
    # Use an undocumented feature simulating an import from anywhere,
    # cf. https://stackoverflow.com/a/68361215/173003.
    config = pydoc.importfile("config.py").config
    drivername = config["drivername"]
    database = Path(config["source_path"]).stem
    username = config["username"]
    host = config["host"]
    port = config["port"]
    parameters = {
        "drivername": drivername,
        "database": input(f"Database [{database}]: ") or database,
        "username": input(f"Username [{username}]: ") or username,
        "password": getpass.getpass("Password: "),
        "host": input(f"Host [{host}]: ") or host,
        "port": input(f"Port [{port}]: ") or port,
    }
    with open(cnx_path, "w") as file:
        file.write("[cnx]\n")
        for key, value in parameters.items():
            file.write(f"{key} = {value}\n")
    print(f"{OK}The connection file '{cnx_name}' has been created.{RESET}")

def get_engine():
    cnx_path = Path("cnx.ini")
    parameters = {}
    for line in cnx_path.read_text(encoding="utf8").splitlines():
        (k, _, v) = line.partition(" = ")
        parameters[k] = v
    url = "{drivername}://{username}:{password}@{host}:{port}/{database}".format(**parameters)
    return sqlalchemy.create_engine(url)

def show_tables(engine=None):
    if engine is None:
        engine = get_engine()
    metadata = sqlalchemy.MetaData()
    metadata.reflect(engine)
    results = []
    for table in metadata.tables.values():
        results.append([table.name, ", ".join([c.name for c in table.c])])
    table_width = max(len(row[0]) for row in results) + 2
    columns_width = max(len(row[1]) for row in results) + 2
    print(f"{'Table':<{table_width}} {'Columns':<{columns_width}}")
    print("-" * (table_width + columns_width + 1))
    for row in results:
        print(f"{row[0]:<{table_width}} {row[1]:<{columns_width}}")