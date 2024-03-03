from pathlib import Path
import getpass
import pydoc
from IPython import get_ipython
import pandas as pd
import sqlalchemy

ipython = get_ipython()

from .nb_tools import *
from .text_tools import OK, RESET, WARNING


def col(label):
    result = ipython.last_execution_result.result
    return list(result.dict()[label])


def print_assert(label):
    print(f'assert col("{label}") == {col(label)}'.replace("Decimal('", "").replace(".00')", ""))

def may_create_connection_file(**kwargs):
    cnx_path = Path("cnx.ini")
    cnx_name = f"{cnx_path.resolve().parent.name}/{cnx_path.name}"
    if cnx_path.exists():
        print(f"{OK}Using the existing connection file '{cnx_name}'.{RESET}")
        return
    print(f"{WARNING}Creating a connection file.{RESET}")
    # Use an undocumented feature simulating an import from anywhere,
    # cf. https://stackoverflow.com/a/68361215/173003.
    config = pydoc.importfile("config.py").config
    username = kwargs["username"]
    database = Path(config["source_path"]).stem
    host = kwargs["host"]
    port = kwargs["port"]
    parameters = {
        "drivername": kwargs["drivername"],
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


def show_tables():
    cnx_path = Path("cnx.ini")
    parameters = {}
    for line in cnx_path.read_text().splitlines():
        (k, _, v) = line.partition(" = ")
        parameters[k] = v
    url = "{drivername}://{username}:{password}@{host}:{port}/{database}".format(**parameters)
    engine = sqlalchemy.create_engine(url)
    metadata = sqlalchemy.MetaData()
    metadata.reflect(engine)
    results = []
    for table in metadata.tables.values():
        results.append([table.name, ", ".join([c.name for c in table.c])])
    pd.set_option("display.max_colwidth", None)
    return pd.DataFrame(results, columns=["Table", "Columns"])
