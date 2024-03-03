import sys

from cmd2 import Cmd, Settable, Statement
from cmd2.table_creator import Column, HorizontalAlignment, SimpleTable

from .database import database_factory
from .text_tools import OK, RESET, WARNING, FAIL


class Shell(Cmd):
    """
    An SQL shell specialized for an SQL Adventure Builder database.
    Added value: when a query returns a table having a column 'token', the corresponding
    message is automatically displayed (no need to call decrypt()).
    """

    def __init__(self, db):
        # Empty the remaining args before passing them to the shell.
        sys.argv[1:] = []
        self.db = db
        multiline_commands = ["select", "insert", "update", "delete", "alter", "create", "drop"]
        multiline_commands.extend(cmd.upper() for cmd in multiline_commands[:])
        super().__init__(multiline_commands=multiline_commands)
        self.intro = "Welcome to the SQL Adventure Builder shell. Type '?' to list the commands."
        self.prompt = ">>> "
        self.continuation_prompt = "... "
        self.max_total_width = 120
        self.add_settable(
            Settable(
                "width",
                int,
                "Maximum total width of a table",
                self,  # The object to which the attribute belongs.
                settable_attrib_name="max_total_width",
            )
        )
        self.debug = True
        self.do_exit = self.do_quit
        self.do_SELECT = self.do_select

    def do_select(self, statement: Statement):
        """Run the given query, print the resulting table and the decrypted message, if any."""
        (headers, datatypes, rows) = self.db.execute_select(statement.command_and_args)
        self.print_table(headers, datatypes, rows)
        n = len(rows)
        self.poutput(f"{n} row{'s'[:n^1]} in set\n")
        if n and "token" in headers:
            token = rows[0][headers.index("token")]
            self.decrypt(token)
    
    def default(self, statement: Statement):
        """Called when the command is not recognized as a do_* method."""
        n = self.db.execute_non_select(statement.command_and_args)
        self.poutput(f"\n{n} row{'s'[:n^1]} affected")
    
    def do_decrypt(self, statement: Statement):
        """
        Called when the user types 'decrypt a b c'. The `statement` object has an `args`
        attribute containing the whole list of arguments as a string (here, 'a b c').
        The first argument is the token, and the rest is ignored.
        """
        token = statement.args.partition(" ")[0]
        self.decrypt(token)

    def decrypt(self, token):
        """Execute the `decrypt` stored procedure with the given token."""
        result = self.db.call_procedure("decrypt", [token])
        self.poutput(result[0][0])

    # https://github.com/PyMySQL/PyMySQL/blob/main/pymysql/constants/FIELD_TYPE.py
    NUMERIC_TYPE_CODES = {
        0: "DECIMAL",
        1: "TINY",
        2: "SHORT",
        3: "LONG",
        4: "FLOAT",
        5: "DOUBLE",
        8: "LONGLONG",
        9: "INT24",
        16: "BIT",
        246: "NEWDECIMAL",
    }

    def align(self, datatype):
        if datatype in self.NUMERIC_TYPE_CODES:
            return HorizontalAlignment.RIGHT
        else:
            return HorizontalAlignment.LEFT

    def print_table(self, headers, datatypes, rows):
        widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        while sum(widths) > self.max_total_width:
            widths[widths.index(max(widths))] -= 1
        columns = []
        for header, datatype, width in zip(headers, datatypes, widths):
            align = self.align(datatype)
            column = Column(
                header,
                width=width,
                max_data_lines=1,
                header_horiz_align=align,
                data_horiz_align=align,
            )
            columns.append(column)
        table = SimpleTable(columns)
        self.poutput(table.generate_table(rows, row_spacing=0))
        self.poutput()


def run(config: dict):
    db = database_factory(config)
    db.connect()
    Shell(db).cmdloop()
    db.close()
