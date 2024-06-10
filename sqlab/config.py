import getpass
import importlib
import os
import pydoc
from pathlib import Path
import configparser

# fmt: off
defaults = { # Not a JSON object because it contains comments and Python lambda functions.
    "dbms": NotImplementedError("DBMS configuration is mandatory. Possible values: 'MySQL', 'PostgreSQL' (case and spaces are ignored)."),
    "cnx_path": NotImplementedError("Connection configuration is mandatory. It must be the path of an INI file for SQLAlchemy."),
    "language": NotImplementedError("Language configuration is mandatory. Example values: 'fr', 'en'."),
    "ddl_path": NotImplementedError("DDL configuration is mandatory. It must be the path of a .sql file."),
    "dataset_dir": NotImplementedError("Dataset configuration is mandatory. It must be the path of a folder containing TSV files."),
    "source_path": NotImplementedError("Source configuration is mandatory. It must be the path of either a .ipynb or .json file."),
    "cheat_sheet_path": "./output/cheat_sheet.md",
    "sql_dump_path": "./output/dump.sql",
    "exercises_path": "./output/exercises.md",
    "graph_gv_path": "./output/graph.gv",
    "graph_pdf_path": "./output/graph.pdf",
    "graph_svg_path": "./output/graph.svg",
    "log_path": "./output/msg.log",
    "records_path": "./output/records.json",
    "report_path": "./output/report.json",
    "storyline_path": "./output/storyline.md",
    "salt_seed": 42,
    "salt_bound": 100,
    "column_width": 100, # for wrapping text in the `sqlab_msg` table
    "reformat_sql": True, # Reformat the SQL queries in the notebook
    "sqlparse_kwargs": {
        "keyword_case": "upper",  # Limitation: https://github.com/andialbrecht/sqlparse/pull/501
        "identifier_case": "lower",
        "use_space_around_operators": True,
        "reindent": True,
        "indent_width": 4,
        "comma_first": True,
    },
    "sqlparse_subs": {
        "capitalize_keywords": (r"\b(on|over|like|separator|interval|as)\b", lambda m: m[0].upper()),
        "uppercase_table_aliases": (r"\b(?<=[ \(])\w[0-9]?\b", lambda m: m[0].upper()),  # e.g. "FROM city c1, city c2" -> "FROM city C1, city C2"
        "fix_cross_join_indents": (r"\nCROSS JOIN", r","),
        "align_fields_when_comma_first": (r"(?m)( +, ) ", r"\1"),
        "space_around_union": (r"( +)UNION( ALL)? ", r"\n\1UNION\2\n\n\1"), # more space around the UNION operators
        "fix_newlines_after_over": (r"\b(OVER)\(\n +", r"\1 ("),
    },
    "strings_en": {
        "exercise_label": "Exercise",
        "statement_label": "Statement",
        "hint_label": "Hint",
        "episode_label": "Episode",
        "formula_label": "Formula",
        "solution_label": "Solution",
        "annotation_label": "Annotation",
        "action_label": "Action",
        "preamble_adventure": "Welcome!",
        "preamble_accepted": "Your query is accepted, congratulations! Please note the official correction:",
        "preamble_rejected": "You are not far from the expected result.",
        "preamble_default": "🔴 No specific message is planned for this token. Possible reasons:\n1. Copy-paste accident (double-click on the token to facilitate selection).\n2. Formula for calculating the token not updated.\n3. (0.0) still present, or replaced by the wrong value.\n4. New logical error. Congratulations on your creativity! Now read the statement carefully and, if the symptoms persist, ask your teacher.",
        "close_dialog": "If you see this window, press Esc without touching anything else.",
        "tweak_instruction": "replace (0.0) with {repl}",
        "exercise_tokens": "Full statement: {salt}. Solution: {token}.",
        "adventure_label": "Adventure",
        "exercises_label": "Exercises",
    },
    "strings_fr": {
        "exercise_label": "Exercice",
        "statement_label": "Énoncé",
        "hint_label": "Indication",
        "episode_label": "Épisode",
        "formula_label": "Formule",
        "solution_label": "Solution",
        "annotation_label": "Annotation",
        "action_label": "Action",
        "preamble_adventure": "Bienvenue !",
        "preamble_accepted": "Votre requête est acceptée, bravo ! Notez la correction officielle :",
        "preamble_rejected": "Vous n'êtes pas loin du résultat attendu.",
        "preamble_default": "🔴 Aucun message spécifique n''est prévu pour ce token.\nRaisons possibles :\n1. Accident de copier-coller (double-cliquez sur le token pour en faciliter la sélection).\n2. Formule de calcul du token non mise à jour.\n3. (0.0) toujours présent, ou remplacé par la mauvaise valeur.\n4. Erreur logique inédite. Bravo pour votre créativité ! Maintenant relisez attentivement l''énoncé et, si les symptômes persistent, consultez votre enseignant.",
        "close_dialog": "Si vous voyez cette fenêtre, appuyez sur Esc sans rien toucher d'autre.",
        "tweak_instruction": "remplacez (0.0) par {repl}",
        "exercise_tokens": "Énoncé complet : {salt}. Solution : {token}.",
        "adventure_label": "Aventure",
        "exercises_label": "Exercices",
    },
    "info": {}
}
# fmt: on


def get_config(args):

    # Initialize the configuration with the default values.
    config = defaults.copy()

    # Use an undocumented feature simulating an import from anywhere,
    # cf. https://stackoverflow.com/a/68361215/173003.
    config_dir = Path(args.CONFIG_DIR)
    user_config = pydoc.importfile(str(config_dir / "config.py")).config

    # Update the default configuration with the user configuration.
    def deep_merge(dict1, dict2):
        """Recursively merge dict2 into dict1"""
        for key in dict2:
            if key in dict1 and isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                deep_merge(dict1[key], dict2[key])
            else:
                dict1[key] = dict2[key]

    deep_merge(config, user_config)

    # Check that all mandatory parameters are present.
    def validate_config(config):
        for value in config.values():
            if isinstance(value, NotImplementedError):
                raise value  # Re-raise the NotImplementedError with its message
            elif isinstance(value, dict):  # Recurse into nested dictionaries
                validate_config(value)

    validate_config(config)

    # Create a entry "strings" with the appropriate language, defaulting to English.
    config["strings"] = config.get(f"strings_{config['language']}", config[f"strings_en"])

    # Transform paths relative to the user configuration file parent into Path objects
    # relative to the current working directory. Create the directories if needed.
    for key, value in config.items():
        if key.endswith(("_path", "_dir")):
            if isinstance(value, str) and value.startswith("."):
                config[key] = config_dir / value
            config[key] = Path(os.path.relpath(config[key], Path.cwd()))
            if key.endswith("_dir"):
                config[key].mkdir(parents=True, exist_ok=True)
            else:
                config[key].parent.mkdir(parents=True, exist_ok=True)

    # Read the cnx.ini file and update the configuration with its content.
    cnx_parser = configparser.ConfigParser()
    cnx_parser.read(config["cnx_path"])
    cnx = dict(cnx_parser["cnx"])
    cnx.pop("drivername", None)  # Remove the SQLAlchemy drivername, if present.
    cnx["user"] = cnx.pop("username", None)  # Change the SQLAlchemy username, into user.

    # Retrieve the password and, if needed, add it to the connection configuration.
    if "password" not in cnx:
        if args.password:
            password = args.password  # The password is passed as a command-line argument
        else:
            try:  # The password may be stored in a secrets.py file
                password = importlib.import_module(".secrets", package="sqlab").password
            except ModuleNotFoundError:  # If not, ask the user to type it
                prompt = f"{config['dbms']} password for user {cnx['user']}: "
                password = getpass.getpass(prompt)
        cnx["password"] = password
    
    # Complete the configuration with calculated values.
    config["cnx"] = cnx
    config["dbms_slug"] = config["dbms"].lower().replace(" ", "")

    return config
