import argparse
import importlib
from textwrap import dedent, TextWrapper

from .config import get_config
from .version import __version__


class CustomHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _split_lines(self, text, width):
        wrapper = TextWrapper(width=width)
        lines = []
        for line in text.splitlines():
            if len(line) > width:
                lines.extend(wrapper.wrap(line))
            else:
                lines.append(line)
        return lines


def main():
    """Parse the command line arguments. NB: most of the settings are defined in the `config.py` files."""

    msg = "SQL Adventure Builder: create a standalone relational database out of a sequence of SQL exercises or adventures."
    parser = argparse.ArgumentParser(description=msg, formatter_class=CustomHelpFormatter)

    msg = "A directory containing a file named `config.py`, which defines a dictionary named `config`."
    parser.add_argument("CONFIG_DIR", help=msg)

    msg = """\
        • create: create or recreate a database and populate it using the TSV files of the subfolder "data" (if any). All data tables are extended with a column containing a hash of each row. Parse the notebook (if any). Generate the messages (if any), encrypt and insert them in the added table "sqlab_msg".
        • shell: launch a shell connected to the database. The added value is that, when a query produces a token, the corresponding message is decrypted and displayed without needing to copy-paste it into a CALL decrypt() command.
        • report: take as an input the file "logs.tsv" resulting from the students' interactions with the database, generate "report.json", and print to the standard output the unexpected queries with their corresponding tokens.
        • parse: parse the notebook containing the SQL exercises and adventures (if any). Extract the required records in a file named "records.json".
    """
    parser.add_argument("CMD", choices=["create", "shell", "report", "parse"], help=dedent(msg))

    parser.add_argument("-v", "--version", action="version", version=f"SQL Adventure Builder {__version__}")

    parser.add_argument("-p", "--password", help="MySQL password")

    args = parser.parse_args()
    module = importlib.import_module(f".cmd_{args.CMD}", package="sqlab")
    config = get_config(args)
    module.run(config)


if __name__ == "__main__":
    main()
