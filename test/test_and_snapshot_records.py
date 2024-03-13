import unittest
import json
from pathlib import Path
import re

from sqlab.cmd_parse import NotebookParser
from sqlab.generate_messages import MessageGenerator

base_dir = Path("test", "snapshots")
base_dir.mkdir(parents=True, exist_ok=True)

config = {
    "records_path": Path("test/snapshots/records.json"),
    "graph_gv_path": Path("test/snapshots/graph.gv"),
    "graph_pdf_path": Path("test/snapshots/graph.pdf"),
    "graph_svg_path": Path("test/snapshots/graph.svg"),
    "strings": {
        "exercise_label": "Exercise",
        "statement_label": "Statement",
        "hint_label": "Hint",
        "episode_label": "Episode",
        "formula_label": "Formula",
        "annotation_label": "Annotation",
        "preamble_accepted": "Correct",
        "emoji_instruction": "replace 👀 by {repl}",
        "preamble_rejected": "Almost there!",
        "preamble_adventure": "Welcome!",
        "solution_label": "Solution",
    }
}

parse_nb = NotebookParser(config)
message_generator = MessageGenerator(config)

def sql(source, token):
    return {
        "cell_type": "code",
        "source": f"%%sql\n{source}".splitlines(keepends=True),
        "outputs": [{"data": {"text/html": f"<th>token</th>\n<td>{token}</td>\n    </tr>"}}],
    }


def code(source):
    return {
        "cell_type": "code",
        "source": source.splitlines(keepends=True),
    }


def markdown(source):
    return {
        "cell_type": "markdown",
        "source": source.splitlines(keepends=True),
    }

class TestRecordCreationErrors(unittest.TestCase):

    def test_hint_token_collides_with_another_token(self):
        cells = [
            markdown("**Exercise [042].** how?"),
            sql("SELECT foo, salt_042 as token", "4547"),
            sql("-- Hint. This is wrong\nSELECT bar, salt_042 as token", "4547"),
        ]
        self.assertRaisesRegex(AssertionError, r"collide", parse_nb, cells)
    
    def test_salt_mismatch_in_solutions(self):
        cells = [
            markdown("**Exercise [001].** how?"),
            sql("SELECT foo, salt_003 as token", "4547"),
        ]
        self.assertRaisesRegex(AssertionError, r"Salt mismatch", parse_nb, cells)
    
    def test_formula_mismatch_in_solutions(self):
        cells = [
            markdown("**Exercise [001].** how?"),
            sql("SELECT foo, salt_001 as token", "4547"),
            sql("SELECT foo, salt_001 over() as token", "4547"),
        ]
        self.assertRaisesRegex(AssertionError, r"Formula mismatch", parse_nb, cells)
    
    def test_exercise_or_episode_number_mismatch(self):

        cells = [
            markdown("**Exercise [001].** how?"),
            sql("SELECT foo, salt_001 as token", "4547"),
            markdown("**Episode [001].** Blah blah"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token", "4242"),
        ]
        self.assertRaisesRegex(AssertionError, r"Salt .* already used", parse_nb, cells)

        cells = [
            markdown("**Episode [001].** Blah blah"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token", "4547"),
            markdown("**Exercise [001].** how?"),
            sql("SELECT foo, salt_001 as token", "4242"),
        ]
        self.assertRaisesRegex(AssertionError, r"Salt .* already used", parse_nb, cells)
    
        cells = [
            markdown("**Episode [001].** how?"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token", "4547"),
            markdown("**Episode [001].** Blah blah"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token", "4242"),
        ]
        self.assertRaisesRegex(AssertionError, r"Salt .* already used", parse_nb, cells)

        cells = [
            markdown("**Exercise [001].** Blah blah"),
            sql("SELECT foo, salt_001 as token", "4547"),
            markdown("**Exercise [001].** how?"),
            sql("SELECT foo, salt_001 as token", "4242"),
        ]
        self.assertRaisesRegex(AssertionError, r"Salt .* already used", parse_nb, cells)
    
    def test_unexpected_tweak(self):
        cells = [code("x = 1234 # the largest value\n")]
        self.assertRaisesRegex(AssertionError, r"tweak .+ preceded", parse_nb, cells)

    def test_double_tweak(self):
        cells = [
            markdown("**Exercise [001].** First episode of one adventure"),
            code("x = 1234 # the largest value\n"),
            sql("SELECT foo, salt_001 {{x}} as token", "1002"),
            code("x = 3456 # the smallest value\n"),
        ]
        self.assertRaisesRegex(AssertionError, r"already .* tweak", parse_nb, cells)

    def test_unexpected_statement(self):
        cells = [markdown("**Statement.** how?")]
        self.assertRaisesRegex(AssertionError, r"statement .+ preceded", parse_nb, cells)

    def test_double_statement(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token\n--> Episod [002]", "1002"),
            sql("SELECT bar, salt_001 as token", "1002"),
            markdown("**Statement.** why?"),
        ]
        self.assertRaisesRegex(AssertionError, r"already .* statement", parse_nb, cells)
    
    def test_missing_statement(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            sql("SELECT foo, salt_001 as token\n--> Episod [002]", "1002"),
        ]
        self.assertRaisesRegex(AssertionError, r"Missing statement", parse_nb, cells)
    
    def test_unknown_label(self):
        cells = [markdown("**Exercice [001].** bla bla")]
        self.assertRaisesRegex(AssertionError, r"Unknown label", parse_nb, cells)
    
    def test_missing_formula(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            markdown("**Statement.** how?"),
            sql("SELECT no_token\nFROM table", "not_a_token"),
        ]
        self.assertRaisesRegex(AssertionError, r"Missing formula", parse_nb, cells)
    
    def test_missing_tweak_definition(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            sql("SELECT foo, salt_001 {{x}} as token", "1002"),
        ]
        self.assertRaisesRegex(AssertionError, r"Missing tweak", parse_nb, cells)
    
    def test_missing_tweak_placeholder(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            code(("x = 1234 # the largest value\n")),
            sql("SELECT foo, salt_001 as token", "1002"),
        ]
        self.assertRaisesRegex(AssertionError, r"Missing {{x}}", parse_nb, cells)

    def test_self_reference(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token\n--> Episod [001]", "1002"),
        ]
        self.assertRaisesRegex(AssertionError, r"Self-reference", parse_nb, cells)
    
    def test_two_hints_with_the_same_token(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token", "1002"),
            sql("-- Hint. This is wrong\nSELECT bar, salt_001 as token", "1004"),
            sql("-- Hint. This is bad\nSELECT bizz, salt_001 as token", "1004"),
        ]
        self.assertRaisesRegex(AssertionError, r"Two hint.*same token", parse_nb, cells)
    
    def test_hint_with_no_token(self):
        cells = [
            markdown("**Episode [001].** First episode of one adventure"),
            markdown("**Statement.** how?"),
            sql("SELECT foo, salt_001 as token", "1002"),
            sql("-- Hint. This is wrong\nSELECT bar, salt_001 as token", ""),
        ]
        self.assertRaisesRegex(AssertionError, r"Missing token for hint", parse_nb, cells)

def create_records():

    dumps = lambda cells: json.dumps(parse_nb(cells), indent=2, ensure_ascii=False) + "\n"

    path = Path(base_dir, "exercise_1_solution.json")
    cells = [
        markdown("**Exercise [042].** how?"),
        sql("SELECT foo, salt_042 as token", "4547"),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "exercise_n_solutions_same_token.json")
    cells = [
        markdown("**Exercise [042].** how?"),
        sql("SELECT foo, salt_042 as token", "4547"),
        sql("-- Variant.\nSELECT bar, salt_042 as token", "4547"),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "exercise_n_solutions_various_tokens.json")
    cells = [
        markdown("**Exercise [042].** how?"),
        sql("SELECT foo, salt_042 as token", "4547"),
        sql("SELECT bar, salt_042 as token", "3839"),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "exercise_n_solutions_with_annotations.json")
    cells = [
        markdown("**Exercise [042].** how?"),
        markdown("**Annotation.** Before all."),
        markdown("**Annotation.** Before 4547."),
        sql("-- Annotation for 4547\nSELECT foo, salt_042 as token", "4547"),
        markdown("**Annotation.** After 4547."),
        markdown("**Annotation.** Before 3839."),
        sql("-- Annotation for 3839\nSELECT bar, salt_042 as token", "3839"),
        markdown("**Annotation.** After 3839."),
        markdown("**Annotation.** After all."),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "exercise_with_useless_next_salt.json")
    cells = [
        markdown("**Exercise [042].** how?"),
        sql("SELECT foo, salt_042 as token\n--> Exercise [043]", "4547"),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "exercise_with_hints.json")
    cells = [
        markdown("**Exercise [042].** how?"),
        sql("SELECT foo, salt_042 as token", "4547"),
        sql("-- Hint. This is wrong\nSELECT bar, salt_042 as token", "3839"),
        sql("-- Hint. This is bad\nSELECT bizz, salt_042 as token", "8968"),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "exercises_with_tweak.json")
    cells = [
        markdown("**Exercise [042].** how?"),
        code(("x = 1234 # the largest value\n")),
        sql("SELECT foo, salt_042 {{x}} as token", "4547"),
        sql("SELECT bar, salt_042 {{x}} as token", "4547"), # a variant with the same tweak
        markdown("**Exercise [043].** how?"), # tweak is reset
        sql("SELECT bizz, salt_043 as token", "1278"),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "exercises_with_sectionning_and_eof.json")
    cells = [
        markdown("# 1. Keep this (+)\n"),
        markdown("# 1.1. Keep this (+)\n"),
        markdown("**Exercise [042].** how?"),
        sql("SELECT foo, salt_042 as token", "5664"),
        markdown("# 1.2. Keep this (+)\n"),
        markdown("**Exercise [043].** how?"),
        sql("SELECT foo, salt_043 as token", "6877"),
        markdown("# 1.3. Don't keep this\n"),
        markdown("**Exercise [044].** how?"),
        sql("SELECT foo, salt_044 as token", "9112"),
        code("raise EOFError"), # Ignore everything after this
        markdown("**Exercise [045].** This should not be kept."),
        sql("SELECT foo, salt_045 as token", "4547"),
    ]
    path.write_text(dumps(cells))

    path = Path(base_dir, "complex_graph.json")
    cells = [
        #         ________     ___________________
        #       /   2002   \ /     2004            \
        #  --> 001 ≡≡≡≡≡≡≡> 002 ======> 003 ------> 004
        #       \   1002         1003  / \   1004
        #        \____________________/   \____________.
        #                  2003            \  0102
        #                                   \____________.
        #                                       0202
        markdown("**Episode [001].** First episode of one adventure"),    #               --> 001
        markdown("**Statement.** how 001?"),
        sql("SELECT r1002a, salt_001 as token\n--> Episod [002]", "1002"),   # 001 --- 1002 ---> 002 (r1002a)
        sql("SELECT r1002b, salt_001 as token", "1002"),                     # 001 --- 1002 ---> 002 (r1002b)
        sql("SELECT r2002, salt_001 as token", "2002"),                      # 001 --- 2002 ---> 002 (r2002)
        sql("SELECT r2003, salt_001 as token\n--> Episode [003]", "2003"),   # 001 --- 2003 ---> 003 (r2003)
        sql("SELECT r1002c", "a variant without token"),                     # 001 ------------> 002 (no token)

        markdown("**Episode [002].** blah blah"),
        markdown("**Statement.** how 002?"),
        sql("SELECT r1003a, salt_002 as token\n--> Episode [003]", "1003"),  # 002 --- 1003 ---> 003 (r1003a)
        sql("SELECT r2004, salt_002 as token\n--> Episode [004]", "2004"),   # 002 --- 2004 ---> 004 (r2004)
        sql("SELECT r1003b, salt_002 as token", "1003"),                     # 002 --- 1003 ---> 003 (r1003b)

        markdown("**Episode [003].** blah blah"),
        markdown("**Statement.** how 003?"),
        sql("SELECT r1004, salt_003 as token\n--> Epilog [004]", "1004"),    # 003 --- 1004 ---> 004 (r1004)
        sql("-- Hint. Wrong\nSELECT r0102, salt_003 as token", "0102"),      # 003 --- 0102
        sql("-- Hint. Bad\nSELECT r0202, salt_003 as token", "0202"),        # 003 --- 0202

        markdown("**Episode [004].** End of one adventure"),
        markdown("**Statement.** no question asked!"),

        #  --> 011 ------> 012       013
        #         \ 1012             /
        #          \________________/
        #                 1013
        markdown("**Episode [011].** First episode of another adventure"),   # --> 011
        markdown("**Statement.** how?"),
        sql("SELECT r1012, salt_011 as token\n--> Episod [012]", "1012"),    # 011 --- 1012 ---> 012 (r1012)
        sql("SELECT r1013, salt_011 as token\n--> Episod [013]", "1013"),    # 011 --- 1013 ---> 013 (r1013)
        markdown("**Episode [012].** End of another adventure"),
        markdown("**Statement.** no question asked either!"),
        markdown("**Episode [013].** Alternative end of another adventure"),
        markdown("**Statement.** no question asked either!"),
    ]
    path.write_text(dumps(cells))
    Path("test", "snapshots", "graph.pdf").unlink()


def create_messages():
    sub = re.compile(r"\n----+\n?").sub
    for path in base_dir.glob("*.json"):
        records = json.loads(path.read_text())
        messages = message_generator.run(records)
        messages = "\n".join(f"{k:4s}\t{repr(sub('--', v))}" for (k, v) in messages.items())
        Path(base_dir, f"{path.stem}.tsv").write_text(messages + "\n")


create_records()
create_messages()