import unittest
from sqlab.text_tools import *

class TestReprSingle(unittest.TestCase):

    def test_normal_strings(self):
        self.assertEqual(repr_single("hello world"), "'hello world'")

    def test_empty_string(self):
        self.assertEqual(repr_single(""), "''")

    def test_string_with_quotes(self):
        self.assertEqual(repr_single("he said, \"hello\""), '\'he said, "hello"\'')
        self.assertEqual(repr_single("'single quotes'"), "'\\'single quotes\\''")


class TestSeparateQueryAndFormula(unittest.TestCase):

    def test_query_without_salt(self):
        query = "SELECT * FROM table"
        actual = separate_query_formula_and_salt(query)
        self.assertEqual(actual, (query, "", ""))
        query = "SELECT 1"
        actual = separate_query_formula_and_salt(query)
        self.assertEqual(actual, (query, "", ""))
    
    def test_query_with_formula(self):
        query = "SELECT *, salt_096(sum(hash) OVER ()) AS token FROM table"
        actual = separate_query_formula_and_salt(query)
        self.assertEqual(actual, ("SELECT * FROM table", "salt_096(sum(hash) OVER ()) AS token", "096"))
    
    def test_query_with_just_formula(self):
        query = "SELECT salt_096(sum(hash) OVER ()) AS token FROM table"
        actual = separate_query_formula_and_salt(query)
        self.assertEqual(actual, ("SELECT FROM table", "salt_096(sum(hash) OVER ()) AS token", "096"))
    
    def test_query_used_in_parser_testing(self):
        query = "SELECT foo, salt_042 as token"
        actual = separate_query_formula_and_salt(query)
        self.assertEqual(actual, ("SELECT foo", "salt_042 as token", "042"))
    
    def test_query_with_x_formula(self):
        query = """SELECT *, salt_025(sum(string_hash("{{x}}")) OVER ()) AS token FROM table"""
        actual = separate_query_formula_and_salt(query)
        self.assertEqual(actual, ("SELECT * FROM table", "salt_025(sum(string_hash(\"(0.0)\")) OVER ()) AS token", "025"))


class TestSplitSqlSource(unittest.TestCase):

    def test_query(self):
        query = "SELECT * FROM table"
        actual = split_sql_source(query)
        self.assertEqual(actual, ("", "", query, ""))
    
    def test_multiline_query(self):
        query = "SELECT *\nFROM table"
        actual = split_sql_source(query)
        self.assertEqual(actual, ("", "", query, ""))
    
    def test_multiline_query_with_blank_line(self):
        query = "SELECT *\n\nFROM table"
        actual = split_sql_source(query)
        self.assertEqual(actual, ("", "", query, ""))
    
    def test_query_with_single_line_comment(self):
        query = "-- foo\nSELECT * FROM table"
        actual = split_sql_source(query)
        print(actual)
        self.assertEqual(actual, ("", "foo", "SELECT * FROM table", ""))
    
    def test_query_with_labelled_empty_comment(self):
        query = "-- label.\nSELECT * FROM table"
        actual = split_sql_source(query)
        print(actual)
        self.assertEqual(actual, ("label", "", "SELECT * FROM table", ""))
    
    def test_query_with_labelled_empty_comment_and_redirection(self):
        query = "-- label.\nSELECT *\nFROM session A\n--> Épisode [002]"
        actual = split_sql_source(query)
        print(actual)
        self.assertEqual(actual, ('label', '', 'SELECT *\nFROM session A', '002'))
    
    def test_query_with_labelled_single_line_comment(self):
        query = "-- label. foobar\nSELECT * FROM table"
        actual = split_sql_source(query)
        print(actual)
        self.assertEqual(actual, ("label", "foobar", "SELECT * FROM table", ""))
    
    def test_query_with_multiline_comment(self):
        query = "-- foo\n-- bar\nSELECT * FROM table"
        actual = split_sql_source(query)
        print(actual)
        self.assertEqual(actual, ("", "foo bar", "SELECT * FROM table", ""))
    
    def test_query_with_labelled_multiline_comment(self):
        query = "-- label. foo\n-- bar\nSELECT * FROM table"
        actual = split_sql_source(query)
        print(actual)
        self.assertEqual(actual, ("label", "foo bar", "SELECT * FROM table", ""))

    def test_query_with_redirection(self):
        query = "SELECT * FROM table\n--> Episode [042]"
        actual = split_sql_source(query)
        print(actual)
        self.assertEqual(actual, ("", "", "SELECT * FROM table", "042"))

    def test_query_with_single_line_comment_and_redirection(self):
        query = "-- foo\nSELECT * FROM table\n--> [042]  "
        actual = split_sql_source(query)
        self.assertEqual(actual, ("", "foo", "SELECT * FROM table", "042"))

    def test_query_with_label_multiline_comment_and_redirection(self):
        query = "-- label. foo\n-- bar\nSELECT * FROM table\n--> [042]  "
        actual = split_sql_source(query)
        self.assertEqual(actual, ("label", "foo bar", "SELECT * FROM table", "042"))


class TestSeparateLabelSaltAndText(unittest.TestCase):

    def test_label_salt_and_no_text(self):
        source = "**Label [123].**"
        actual = separate_label_salt_and_text(source)
        self.assertEqual(actual, ("Label", "123", ""))

    def test_label_salt_and_text(self):
        source = "**Label [123].** Some text"
        actual = separate_label_salt_and_text(source)
        self.assertEqual(actual, ("Label", "123", "Some text"))

    def test_label_salt_and_multiline_text(self):
        source = "**Label [123].**\nSome text"
        actual = separate_label_salt_and_text(source)
        print(actual)
        self.assertEqual(actual, ("Label", "123", "\nSome text"))

    def test_label_salt_and_multiline_text_2(self):
        source = "**Label [123].**  \nSome text"
        actual = separate_label_salt_and_text(source)
        print(actual)
        self.assertEqual(actual, ("Label", "123", "\nSome text"))

    def test_label_and_text(self):
        source = "**Label.** Some text"
        actual = separate_label_salt_and_text(source)
        self.assertEqual(actual, ("Label", None, "Some text"))
    
    def test_only_text(self):
        source = "Some text"
        actual = separate_label_salt_and_text(source)
        print(actual)
        self.assertEqual(actual, ("", "", "Some text"))


class TestAddGeneratedHashes(unittest.TestCase):

    source = """
            CREATE TABLE item (
            item varchar(255) NOT NULL,
            owner int(11) DEFAULT NULL,
            hash bigint NULL,
            PRIMARY KEY (item)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

            CREATE TABLE village (
            villageid int(11) NOT NULL AUTO_INCREMENT,
            name varchar(255) DEFAULT NULL,
            chief int(11) DEFAULT NULL,
            hash bigint NULL,
            PRIMARY KEY (villageid)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
        """

    def test_run_with_hash_exemption(self):
        actual = list(add_generated_hashes(self.source, "auto_increment"))
        expected = """
            CREATE TABLE item (
            item varchar(255) NOT NULL,
            owner int(11) DEFAULT NULL,
            hash bigint AS (string_hash('item', item, owner)),
            PRIMARY KEY (item)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

            CREATE TABLE village (
            villageid int(11) NOT NULL AUTO_INCREMENT,
            name varchar(255) DEFAULT NULL,
            chief int(11) DEFAULT NULL,
            hash bigint AS (string_hash('village', name, chief)),
            PRIMARY KEY (villageid)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
        """
        for (a, e) in zip(actual, expected.splitlines()):
            self.assertEqual(a, e)

    def test_run_without_hash_exemption(self):
        actual = list(add_generated_hashes(self.source))
        expected = """
            CREATE TABLE item (
            item varchar(255) NOT NULL,
            owner int(11) DEFAULT NULL,
            hash bigint AS (string_hash('item', item, owner)),
            PRIMARY KEY (item)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;

            CREATE TABLE village (
            villageid int(11) NOT NULL AUTO_INCREMENT,
            name varchar(255) DEFAULT NULL,
            chief int(11) DEFAULT NULL,
            hash bigint AS (string_hash('village', villageid, name, chief)),
            PRIMARY KEY (villageid)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
        """
        for (a, e) in zip(actual, expected.splitlines()):
            self.assertEqual(a, e)