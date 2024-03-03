import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from importlib import resources

from .cmd_parse import run as parse_notebook
from .compose_inserts import compose_data_inserts, compose_message_inserts
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
    # • create_db_queries
    # • create_tables_queries
    # • add_fk_constraints_queries
    # • drop_fk_constraints_queries
    ddl_queries = Path(config["ddl_path"]).read_text()
    db.parse_ddl(ddl_queries)
    sql_dump.write(ddl_queries.replace(db.add_fk_constraints_queries, ""))

    # Drop the database if it exists, and recreate it.
    db_name = config["cnx"].pop("database")  # Don't try to connect to a non-existing database.
    db.connect()
    db.execute_non_select(db.create_db_queries)
    print(f"Database '{db_name}' created.")
    db.close()

    # Connect to the freshly created database and create the core tables.
    config["cnx"]["database"] = db_name  # Restore the database name.
    db.connect()
    db.execute_non_select(db.create_tables_queries)
    print(f"Core tables created.")

    resource_id = f"sqlab.dbms.{config['vendor'].lower()}"

    # Add the structure of the `sqlab_msg` table.
    msg_ddl_queries = resources.read_text(resource_id, "msg_ddl.sql")
    sql_dump.write(msg_ddl_queries)
    db.execute_non_select(msg_ddl_queries)

    # Add the `string_hash` function.
    string_hash_queries = resources.read_text(resource_id, "string_hash.sql")
    sql_dump.write(string_hash_queries)
    db.execute_non_select(string_hash_queries)

    # Add the `decrypt` function.
    decrypt_queries = resources.read_text(resource_id, "decrypt.sql")
    decrypt_queries = decrypt_queries.format(**config["strings"])
    sql_dump.write(decrypt_queries)
    db.execute_non_select(decrypt_queries)

    # Execute other queries (commodity functions, ...).
    other_queries = resources.read_text(resource_id, "goodies.sql")
    sql_dump.write(other_queries)
    db.execute_non_select(other_queries)

    # Add a few random salt functions to the database.
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

    # If the source is a notebook, parse it and populate the `records` list.
    # Otherwise, load the records from the `records.json` file.
    source_path = Path(config["source_path"])
    records = {}
    if source_path.is_file():
        if source_path.suffix == ".ipynb":
            # Add temporarily the foreign key constraints to the core tables, before executing the
            # notebook, in case they are exploited by some question or exercise.
            db.execute_non_select(db.add_fk_constraints_queries)
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
    sql_dump.write(db.add_fk_constraints_queries)
    db.execute_non_select(db.add_fk_constraints_queries)

    message_generator = MessageGenerator(config)

    # Dump the compiled exercises to a dedicated file
    exercises = message_generator.compile_exercises(records)
    if exercises:
        Path(config["output_dir"], "exercises.md").write_text(exercises, encoding="utf-8")
        print(f"Exercises compiled to '{config['output_dir'] / 'exercises.md'}'.")

    # Dump the plot to a dedicated file
    plot = message_generator.compile_plot(records)
    if plot:
        Path(config["output_dir"], "plot.md").write_text(plot, encoding="utf-8")
        print(f"Plot compiled to '{config['output_dir'] / 'plot.md'}'.")

    # Dump the compiled cheat_sheet to a dedicated file
    cheat_sheet = message_generator.compile_cheat_sheet(records)
    if cheat_sheet:
        Path(config["output_dir"], "cheat_sheet.md").write_text(cheat_sheet, encoding="utf-8")
        print(f"Cheat sheet written to '{config['output_dir'] / 'cheat_sheet.md'}'.")

    # Populate the `sqlab_msg` table.
    rows = list(message_generator.run(records).items())
    if rows:
        message_inserts = compose_message_inserts(db, rows)
        sql_dump.write(message_inserts)
        db.execute_non_select(message_inserts)

    sql_dump.close()

    db.close()
    print(f"""{OK}{config["vendor"]} database '{db_name}' created and populated.{RESET}\n""")


class Dump:

    def __init__(self, config: dict):
        self.path = Path(config["output_dir"], f"{config['cnx']['database']}.sql")
        self.path.unlink(missing_ok=True)
        self.file = self.path.open("a", encoding="utf-8")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.file.write(f"-- Generated by SQL Adventure Builder on {timestamp}\n")
        self.file.write(f"-- Any changes will be overwritten.\n\n")

    def write(self, text: str):
        text = re.sub(r"(?m)^--.*\n?", "", text)  # Remove comments
        text = re.sub(r"\n\n\n+", "\n\n", text)  # Remove empty lines
        text = text.strip() + "\n\n\n"
        self.file.write(text)

    def close(self):
        self.file.close()
        print(f"SQL queries dumped to '{self.path}'.")
