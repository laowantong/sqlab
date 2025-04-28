import re
import textwrap

import sqlparse

# ANSI color codes
OK = "\033[92m"
WARNING = "\033[1m\033[38;5;166m"
FAIL = "\033[1m\033[91m"
RESET = "\033[0m"

sub_mono = re.compile(r"`([^`\n]+)`").sub
sub_italic = re.compile(r"(?<!\w)_(.+?)_(?!\w)").sub
sub_bold = re.compile(r"\*\*(.+?)\*\*").sub
sub_code_block = re.compile(r'(?sm)^```(\w+?)\n(.*?)```\n').sub
sub_list = re.compile(r"(?m)((?:^- .*\n)+)").sub
sub_item = re.compile(r"(?m)^- (.+)").sub
sub_br = re.compile(r"<br>\n?").sub

def improved_html(s: str) -> str:
    s = s.strip()
    s = s.replace("\u00A0", "&nbsp;")
    s = sub_mono(r"<code>\1</code>", s)
    s = sub_italic(r"<em>\1</em>", s)
    s = sub_bold(r"<strong>\1</strong>", s)
    s = sub_code_block(r"<pre><code class='\1'>\2</code></pre>\n", s)
    s = sub_list(r"<ul>\1</ul>", s)
    s = sub_item(r"  <li>\1</li>", s)
    return s

def map_chars(sub: callable, chars: str) -> callable:
    """
    Creates a character mapping transformer that works with a substitution function.
    
    This function builds a translation mapping between ASCII characters and a provided
    character set, then returns a new function that applies this mapping to text
    matches found by the substitution function.
    
    Parameters:
    -----------
    sub : callable
        A substitution function (like re.sub) that finds and replaces patterns in text.
        Expected to accept a replacement function and input text as arguments.
    
    chars : str
        A string of characters that will replace standard ASCII characters.
        Should be the same length as the ASCII character set used for mapping.
    
    Returns:
    --------
    callable
        A function that takes text as input and returns text with the character
        mapping applied to any matches found by the substitution function.
    """
    ascii_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    translation_table = str.maketrans(ascii_chars, chars)
    translation_function = lambda m: m[1].translate(translation_table)
    return lambda text: sub(translation_function, text)

map_mono = map_chars(sub_mono, "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿")
map_italic = map_chars(sub_italic, "𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫")
map_bold = map_chars(sub_bold, "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵")

def improved_text(s: str) -> str:
    s = sub_code_block(r"\2", s)
    s = map_mono(s)
    s = map_italic(s)
    s = map_bold(s)
    s = sub_item("— ", s)
    s = sub_br("\n", s)
    return s


class TextWrapper:
    def __init__(self, config: dict):
        self.column_width = config.get("column_width") or 100
        self.prefix = config.get("prefix") or ""

    def __call__(self, text: str, prefix: str = "") -> str:
        """Wraps the given text to the column width."""
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


def separate_query_formula_and_salt(
    query: str,
    match_formula=re.compile(r"(?si)(.+?)\s*,?\s*(salt_(\d+).+?as +token)(.*)").match,
) -> tuple[str, str, str]:
    if m := match_formula(query):
        return (m[1] + m[4], m[2].replace("{{x}}", "(0)"), m[3])
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
