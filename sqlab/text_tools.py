import re
import textwrap

import sqlparse

# ANSI color codes
OK = "\033[92m"
WARNING = "\033[1m\033[38;5;166m"
FAIL = "\033[1m\033[91m"
RESET = "\033[0m"


def markdown_transformer(regex, chars):
    """Returns a function that transforms text according to the given regex and character set."""
    sub = re.compile(regex).sub
    ascii_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    trans = str.maketrans(ascii_chars, chars)

    def transform(text):
        """Transforms the given text according to the given regex and character set.
        Example for transform_bold:
        >>> transform_bold("This is **bold** text.")
        'This is 𝗯𝗼𝗹𝗱 text.'
        """
        return sub(lambda m: m[1].translate(trans), text)

    return transform


# fmt: off
transform_mono = markdown_transformer(r"`(.+?)`", "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿")
transform_italic = markdown_transformer(r"(?<!\w)_(.+?)_(?!\w)", "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫")
transform_bold = markdown_transformer(r"\*\*(.+?)\*\*", "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")
# fmt: on


def transform_markdown(text: str, column_width=100) -> str:
    """Simulate some Mardown tags with Unicode."""
    text = re.sub("(?m)^```.*", "-" * column_width, text)
    text = transform_mono(text)
    text = transform_italic(text)
    text = transform_bold(text)
    text = re.sub(r"(?m)^- ", "— ", text)
    text = re.sub(r"<br>\n?", "\n", text)
    return text


class TextWrapper:
    def __init__(self, config: dict):
        self.column_width = config.get("column_width") or 100
        self.prefix = config.get("prefix") or ""

    def __call__(self, text: str, prefix: str = "") -> str:
        """Wraps the given text to the column width."""
        text = text.replace("\\n", "\n")
        wrapped_lines = []
        for line in text.splitlines():
            wrapped_line = textwrap.wrap(
                line,
                self.column_width - len(prefix),
                break_long_words=False,
                replace_whitespace=False,
            )
            wrapped_lines.append("\n".join(wrapped_line))
        formatted_text = "\n".join(wrapped_lines)
        prefixed_text = "\n".join(f"{prefix}{line}" for line in formatted_text.splitlines())
        return prefixed_text.strip()


class SQLFormatter:
    def __init__(self, config: dict):
        self.kwargs = config.get("sqlparse_kwargs", {})
        subs = config.get("sqlparse_subs", {})
        self.subs = [(re.compile(regex), repl) for (regex, repl) in subs.values()]

    def __call__(self, sql: str) -> str:
        sql = sqlparse.format(sql, **self.kwargs)
        for regex, repl in self.subs:
            sql = regex.sub(repl, sql)
        return sql


def repr_single(s):
    """A repr() that always returns a single-quoted string: https://stackoverflow.com/a/27409739/173003"""
    return "'" + repr('"' + s)[2:]


def separate_query_and_formula(
    query: str,
    match_formula=re.compile(r"(?si)(.+?),?\s*(salt_(\d+).+?as +token)(.*)").match,
) -> tuple[str, str, str]:
    if m := match_formula(query):
        return (m[1] + m[4], m[2].replace("{{x}}", "👀"), m[3])
    return (query, "", "")


def split_sql_source(
    source: str,
    sub_comment_sections=re.compile(r"(?m)(^-- )(_.+\._)").sub,
    match_comments=re.compile(
        r"""(?xm) # Verbose, multiline
        (?:^--\s(?:(\w+)\.[ ]?)?(.*\n))?  # Capture the first line of the optional comment with its optional label
        ((?:^--\s.*\n)*)  # Capture the rest of the optional comment
        ((?:^.*\n*)+?)  # Capture the SQL query
        (?:^-->\s.*\[(\d+)\]\s*)?$  # Capture the optional redirection comment
    """
    ).match
) -> tuple[str, str, str]:
    content = sub_comment_sections(r"\1<br>\2", source)
    m = match_comments(content)
    (label, comment_1, comment_2, query, redirection) = m.groups()
    comment = (comment_1 or "") + comment_2
    comment = re.sub(r"(?m)\s*\n?^--\s*", " ", comment).strip()
    return ((label or ""), comment, query.strip(), (redirection or ""))

def separate_label_salt_and_text(
    source: str,
    match=re.compile(r"(?s)\*\*([^\*]+?)(?: \[(\d+)\])?\.\*\* *(.*)").match
) -> tuple[str, str, str]:
    if m := match(source):
        return m.groups()
    return ("", "", source)

def join_non_empty(*strings: str) -> str:
    """Joins the given strings with two newlines, skipping the empty ones."""
    return "\n\n".join(filter(None, strings))
