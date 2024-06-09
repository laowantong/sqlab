import json
import random
import re
from datetime import datetime
from pathlib import Path
from importlib import resources

from . import __version__
from .cmd_parse import run as parse_notebook
from .compose_inserts import compose_data_inserts, compose_message_inserts, compose_info_inserts
from .database import database_factory
from .generate_messages import MessageGenerator
from .text_tools import OK, RESET, WARNING
from .run_notebook import run_notebook


def run(config: dict):
    print()

    # Open and initialize the file to dump the SQL queries.
    sql_dump = Dump(config)

    # Create the database object.
    db = database_factory(config)

    # Parse the DDL of core tables into four string attributes of the database object:
    # • db_creation_queries
    # • tables_creation_queries
    # • fk_constraints_queries
    # • drop_fk_constraints_queries
    ddl_queries = Path(config["ddl_path"]).read_text()
    db.parse_ddl(ddl_queries)
    if db.fk_constraints_queries:
        ddl_queries = ddl_queries.replace(db.fk_constraints_queries, "")
    sql_dump.write(ddl_queries)

    # Drop the database if it exists, and recreate it.
    db_name = config["cnx"].pop("database")  # Don't try to connect to a non-existing database.
    db.connect()
    config["cnx"]["database"] = db_name  # Restore the database name.
    db.create_database()
    print(f"Database '{db_name}' created.")
    db.close()

    # Connect to the freshly created database and create the core tables.
    db.connect()
    db.execute_non_select(db.tables_creation_queries)
    print(f"Core tables created.")

    resource_id = f"sqlab.dbms.{config['dbms_slug']}"

    # Create the structure of the additional sqlab tables.
    sqlab_ddl_queries = resources.read_text(resource_id, "sqlab_ddl.sql")
    sql_dump.write(sqlab_ddl_queries)
    db.execute_non_select(sqlab_ddl_queries)

    # Define various SQL functions: nn, string_hash, decrypt, etc.
    functions = resources.read_text(resource_id, "udf.sql")
    functions = functions.format(**config["strings"])
    sql_dump.write(functions)
    db.execute_non_select(functions)

    # Define a few random SQL salt functions.
    random.seed(config["salt_seed"])
    salt_template = resources.read_text(resource_id, "salt.sql")
    salts = []
    for i in range(1, config["salt_bound"] + 1):
        salts.append(salt_template.format(i=i, y=random.randrange(2**48)))
    random.shuffle(salts)
    salts_queries = "".join(salts)
    sql_dump.write(salts_queries)
    db.execute_non_select(salts_queries)

    # Populate the core database from the data in the TSV files.
    # During the process, a row hash will be added as the last column of each table.
    # The presence of this column is mandatory for the token formula to work.
    trigger_template = resources.read_text(resource_id, "triggers.sql")
    data_inserts_queries = compose_data_inserts(config, db, trigger_template)
    sql_dump.write(data_inserts_queries)
    db.execute_non_select(data_inserts_queries)

    # Check that the hash columns contain unique values across all tables. An alternative would be
    # to declare each hash column as UNIQUE, but:
    # 1. The uniqueness would not be cross-table.
    # 2. In MySQL, the hash column is calculated from all other columns except the auto-incremented
    #    primary key column. In a stateful game like SQL Island, the player is instructed to insert
    #    a row in the table inhabitant. If they repeat the same insertion, the hash will be the
    #    same (although the personid will be different), raising an IntegrityError.

    seen_hashes = {}  # use a dictionary for better warning messages
    for table_name in db.get_table_names():
        query = f"SELECT * FROM {table_name};"
        (_, _, rows) = db.execute_select(query)
        for row in rows:
            if (hash := row[-1]) in seen_hashes:
                (t1, v1) = seen_hashes[hash]
                (t2, v2) = (table_name, row[:-1])
                print(f"{WARNING}Hash collision:\n    {t1}: {v1}\n    {t2}: {v2}\nhave same hash {hash}.{RESET}")
            seen_hashes[hash] = (table_name, row[:-1])

    sql_dump.write(db.fk_constraints_queries)

    # If the source is a notebook, parse it and populate the `records` list.
    # Otherwise, load the records from the `records.json` file.
    source_path = Path(config["source_path"])
    records = {"info": {}}
    if source_path.is_file():
        if source_path.suffix == ".ipynb":
            # Add temporarily the foreign key constraints to the core tables, before executing the
            # notebook, in case they are exploited by some question or exercise.
            db.execute_non_select(db.fk_constraints_queries)
            notebook_is_up_to_date = run_notebook(config)
            # In case the adventure contains queries like `INSERT INTO`, `UPDATE`, `DELETE FROM`, etc.,
            # the core tables may have been changed. Restore them. This requires the foreign key
            # constraints to be dropped (PostgreSQL does not allow SET FOREIGN_KEY_CHECKS=0).
            print("Restoring the core tables (executing the notebook may have changed them).")
            db.execute_non_select(db.drop_fk_constraints_queries)
            db.execute_non_select(data_inserts_queries)
            if notebook_is_up_to_date:
                records = parse_notebook(config)
            else:
                print(f"{WARNING}The notebook needs some work before I can convert it.{RESET}")
        elif source_path.name == "records.json":
            records = json.loads(source_path.read_text())

    # Finally, add the foreign key constraints to the core tables, now definitely populated.
    db.execute_non_select(db.fk_constraints_queries)

    message_generator = MessageGenerator(config)

    # Dump the compiled exercises to a dedicated file
    exercises = message_generator.compile_exercises(records)
    if exercises:
        config["exercises_path"].write_text(exercises, encoding="utf-8")
        print(f"Exercises compiled to '{config['exercises_path']}'.")

    # Dump the storyline to a dedicated file
    storyline = message_generator.compile_storyline(records)
    if storyline:
        config["storyline_path"].write_text(storyline, encoding="utf-8")
        print(f"Storyline compiled to '{config['storyline_path']}'.")

    # Dump the compiled cheat_sheet to a dedicated file
    cheat_sheet = message_generator.compile_cheat_sheet(records)
    if cheat_sheet:
        config["cheat_sheet_path"].write_text(cheat_sheet, encoding="utf-8")
        print(f"Cheat sheet compiled to '{config['cheat_sheet_path']}'.")

    # Populate the `sqlab_msg` table.
    rows = list(message_generator.run(records).items())
    if rows:
        message_inserts = compose_message_inserts(db, rows)
        sql_dump.write(message_inserts)
        db.execute_non_select(message_inserts)
    
    # Populate the `sqlab_info` table.
    info_inserts = compose_info_inserts(
        **config["info"],
        **records["info"],
        message_count=len(rows),
        sqlab_database_language=config["language"],
        dbms=config["dbms"],
        dbms_version=db.get_version(),
        sqlab_version=__version__,
        created_at=datetime.now().isoformat()
    )
    sql_dump.write(info_inserts)
    db.execute_non_select(info_inserts)

    sql_dump.close()

    db.close()
    print(f"""{OK}{config["dbms"]} database '{db_name}' created and populated.{RESET}\n""")


class Dump:

    def __init__(self, config: dict):
        self.path = config["sql_dump_path"]
        self.path.unlink(missing_ok=True)
        self.file = self.path.open("a", encoding="utf-8")
        self.file.write(f"-- Generated by SQL Adventure Builder. Any changes will be overwritten.\n")
        self.file.write(f"-- See at the end of the file for more information.\n\n")

    def write(self, text: str):
        text = re.sub(r"(?m)^--.*\n?", "", text)  # Remove comments
        text = re.sub(r"\n\n\n+", "\n\n", text)  # Remove empty lines
        text = text.strip() + "\n\n\n"
        self.file.write(text)
        self.file.flush()

    def close(self):
        self.file.close()
        print(f"SQL queries dumped to '{self.path}'.")
