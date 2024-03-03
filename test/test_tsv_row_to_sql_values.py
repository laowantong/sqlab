import unittest
from sqlab.compose_inserts import TsvRowToSqlValues


class TsvRowToSqlValuesStrToRepr(unittest.TestCase):
    def setUp(self):
        self.str_to_repr = TsvRowToSqlValues({}).str_to_repr

    def test_integers(self):
        self.assertEqual(self.str_to_repr("123"), "123")

    def test_floats(self):
        self.assertEqual(self.str_to_repr("123.45"), "123.45")

    def test_booleans(self):
        self.assertEqual(self.str_to_repr("True"), "True")
        self.assertEqual(self.str_to_repr("False"), "False")

    def test_strings(self):
        self.assertEqual(self.str_to_repr("some string"), "'some string'")
        self.assertEqual(
            self.str_to_repr("'already single-quoted'"),
            "'''already single-quoted'''",
        )
        self.assertEqual(self.str_to_repr('"already double-quoted"'), "'\"already double-quoted\"'")

    def test_null_cells_default(self):
        self.assertEqual(self.str_to_repr("NULL"), "NULL")
        self.assertEqual(self.str_to_repr("\\N"), "NULL")
        self.assertEqual(self.str_to_repr("None"), "NULL")

    def test_null_cells_custom(self):
        config = {"null_cells": ["NIL", "NA"]}
        str_to_repr = TsvRowToSqlValues(config).str_to_repr
        self.assertEqual(str_to_repr("NIL"), "NULL")
        self.assertEqual(str_to_repr("NA"), "NULL")
        # The default null cells are no more recognized:
        self.assertEqual(str_to_repr("None"), "'None'")

    def test_empty_cells_default(self):
        self.assertEqual(self.str_to_repr(""), "''")

    def test_empty_cells_custom(self):
        config = {"empty_cells": ["EMPTY", "''", '""']}
        str_to_repr = TsvRowToSqlValues(config).str_to_repr
        self.assertEqual(str_to_repr("EMPTY"), "''")
        self.assertEqual(str_to_repr("''"), "''")
        self.assertEqual(str_to_repr('""'), "''")
        # The actual empty cells are still recognized:
        self.assertEqual(str_to_repr(""), "''")

    def test_null_and_empty_cells_custom(self):
        config = {"null_cells": [""], "empty_cells": ["EMPTY"]}
        str_to_repr = TsvRowToSqlValues(config).str_to_repr
        self.assertEqual(str_to_repr("EMPTY"), "''")
        # The actual empty cells are now regarded as NULL:
        self.assertEqual(str_to_repr(""), "NULL")


class TestTsvRowToSqlValuesIntegration(unittest.TestCase):

    def test_various_rows(self):
        converter = TsvRowToSqlValues({})
        converter.set_wrappers(["foo", "bar", "baz", "qux"])
        test_cases = [
            ("123\tTrue\tNone\ttext", "  (123, True, NULL, 'text'),"),
            ("123.45\tFalse\t\t", "  (123.45, False, '', ''),"),
            (
                """'single-quoted'\t"double-quoted"\t''\t""",
                """  ('''single-quoted''', '"double-quoted"', '''''', ''),""",
            ),
            ("NULL\t\\N\tNone\t", "  (NULL, NULL, NULL, ''),"),
        ]
        for input_row, expected_output in test_cases:
            with self.subTest(input_row=input_row):
                self.assertEqual(converter(input_row), expected_output)
