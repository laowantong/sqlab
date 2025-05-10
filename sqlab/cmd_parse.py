from collections import defaultdict
import contextlib
import json
from pathlib import Path
import re
from typing import Optional
import importlib

from .text_tools import FAIL, OK, RESET, WARNING
from .text_tools import separate_label_salt_and_text, split_sql_source, separate_query_formula_and_salt

def run(config: dict):
    parser = NotebookParser(config)
    print(f"Updating the records...")
    ipynb = json.loads(config["source_path"].read_text(encoding="utf8"))
    records = parser(ipynb["cells"])
    print(f"{OK}The records are up to date.{RESET}")
    text = json.dumps(records, indent=2, ensure_ascii=False)
    Path(config["records_path"]).write_text(text, encoding="utf-8")
    return records

def dequalified(formula: str) -> str:
    """
    Transform the formula by removing the qualification of the hash fields.
    Tolerate the use of an underscore instead of a dot.
    Examples of formulas equivalent after dequalification:
    - salt_069(sum(nn(A.hash) + nn(B.hash)) OVER()) AS token
    - salt_069(sum(nn(B.hash) + nn(A.hash)) OVER()) AS token
    - salt_069(sum(nn(A_hash) + nn(B_hash)) OVER()) AS token
    """
    return re.sub(r"\b[A-Z][_\.]hash", "hash", formula)

class NoDataFieldError(Exception):
    pass

class NoTextFieldError(Exception):
    pass

class NotebookParser:
    def __init__(self, config: dict):
        self.labels_to_kinds = {"": None}
        for (k, v) in config["strings"].items():
            if k.endswith("_label"):
                self.labels_to_kinds[v.lower()] = k[:-6]
        self.activity_map_gv_path = config["activity_map_gv_path"]
        self.graph_format_path = {
            "pdf": config["activity_map_pdf_path"],
            "svg": config["activity_map_svg_path"],
        }

        
    def __call__(self, cells):

        # Create an intermediate representation of the notebook, a list of segments.
        # Each segment must contain all informations pertaining to a single exercise or episode.
        # The associations between salts and tokens will be resolved later, in a stateless way
        # (i.e. no need to store any auxiliary data at a given stage for use at a later stage).

        segments = []
        section_path = []
        salts = set()
        exercise_counter = 0
        for cell in cells:
            source = cell["source"]
            if not source:
                # Ignore empty cells.
                continue

            if cell["cell_type"] == "markdown":
                source = "".join(source)

                if m := re.match(r"(#{1,3}) (.+)", cell["source"][0]):
                    depth = len(m[1]) - 1
                    title = m[2].strip()
                    subtitle = "".join(cell["source"][1:]).strip()  # the rest of the cell may consist in a subtitle
                    section_path[depth:] = [(title, subtitle)]
                    continue

                (label, salt, text) = separate_label_salt_and_text(source)
                if not label:
                    continue
                assert salt not in salts, f"{FAIL}Salt '{salt}' already used.\n{source}.{RESET}"
                if salt:
                    salts.add(salt)

                kind = self.labels_to_kinds.get(label.lower())
                assert kind in ("statement", "annotation", "episode", "exercise"), f"Unknown label '{label}'."

                if kind == "statement":
                    assert segments, f"{FAIL}A statement must be preceded by an exercise or an episode.\n{source}.{RESET}"
                    assert not segments[-1]["statement"], f"{FAIL}{segments[-1]['kind']} [{segments[-1]['salt']}] already has a statement.\n{source}.{RESET}"
                    segments[-1]["statement"] = text
                    continue

                if kind == "annotation":
                    segments[-1]["solutions"].append(text)
                    continue

                # The cell is either an exercise or an episode.
                if kind == "exercise":
                    part_number = 0
                    exercise_counter += 1
                    task_number = exercise_counter
                else: # kind == "episode"
                    part_number = None # to be filled after the segments are completed
                    task_number = None # to be filled after the segments are completed

                segment = {}
                segment["part_number"] = part_number
                segment["kind"] = kind # "exercise" or "episode"
                segment["task_number"] = task_number
                segment["section_path"] = section_path[:]
                section_path = [(title, "") for (title, _) in section_path] # A subtitle is stored only on the first time
                if kind == "episode":
                    segment["context"] = text.strip()
                segment["statement"] = "" if kind == "episode" else text
                segment["salt"] = salt
                segment["formula"] = None  # to be filled on a later iteration
                segment["tweak"] = None  # idem
                segment["default_next_salt"] = None  # idem
                segment["default_token"] = None  # idem
                segment["solutions"] = []
                segment["hints"] = []

                segments.append(segment)
            
            elif cell["cell_type"] == "code":

                # If the cell starts by raising a EOFError, ignore everything after it.
                if source[0].startswith("raise EOFError"):
                    break

                # If the cell starts with a Python assignement of the form x = ... # ..., store
                # the instruction for replacing the (0) placeholder with the value of x.
                if m := re.match(r"x *= *.+ *# *(.+)", source[0]):
                    assert segments, f"{FAIL}A tweak must be preceded by an exercise or an episode.\n{source}.{RESET}"
                    assert not segments[-1]["tweak"], f"{FAIL}{segments[-1]['kind']} [{segments[-1]['salt']}] already has a tweak.\n{source}.{RESET}"
                    if not segments[-1]["tweak"]:
                        segments[-1]["tweak"] = m[1] # store the first tweak as the default one
                        for line in source[1:]: # add the non-natural language tweaks
                            if m := re.match(r"# (\w+): (.+)", line):
                                segments[-1][f"tweak_{m[1].lower()}"] = m[2].strip()

                # Ignore all the cells that do not start with the magic command %%sql.
                if not source[0].startswith("%%sql"):
                    continue

                # Now we have a code cell that starts with %%sql.
                source = "".join(source[1:])  # strips the magic command
                (label, text, raw_query, next_salt) = split_sql_source(source)
                kind = self.labels_to_kinds.get(label.lower(), "")
                if kind == "action": # This query is not meant to be recorded, but to bring the DB to a certain state
                    continue
                (query, formula, salt) = separate_query_formula_and_salt(raw_query)
                token = self.extract_first_token_from_output(cell)

                if salt:
                    assert salt != next_salt, f"{FAIL}Self-reference with salt {salt}.\n{source}{RESET}"

                # The query is either a solution or a hint.
                if kind == "hint":
                    assert token, f"{FAIL}Missing token for hint:{RESET}\n{source}."
                    segments[-1]["hints"].append({
                        "kind": kind,
                        "task_number": task_number,
                        "text": text,
                        "query": raw_query,  # a wrong query is never displayed, but is stored as is for debugging purposes
                        "token": token
                    })

                else: # Regard the query as a solution, whatever the label ("solution", "variant", "", etc.)
                    assert segments, f"{FAIL}A solution must be preceded by an exercise or an episode.\n{source}.{RESET}"
                    if not segments[-1]["formula"]: # We are in the first solution of the segment
                        assert formula, f"{FAIL}Missing formula for {segments[-1]['kind']} [{segments[-1]['salt']}].{RESET}\n{source}."
                        if "(0)" in formula:
                            assert segments[-1]["tweak"], f"{FAIL}Missing tweak for {segments[-1]['kind']} [{segments[-1]['salt']}].{RESET}\n{source}."
                        else:
                            assert not segments[-1]["tweak"], f"{FAIL}Missing {{{{x}}}} in the formula of a first solution.{RESET}\n{source}."
                        assert segments[-1]["statement"], f"{FAIL}Missing statement cell for {segments[-1]['kind']} [{segments[-1]['salt']}].{RESET}\n{source}."
                        # Store the first formula, next salt and token as the default ones
                        segments[-1]["formula"] = formula
                        segments[-1]["default_next_salt"] = next_salt
                        segments[-1]["default_token"] = token
                    
                    if formula: # The formula is explicitely stated
                        assert salt == segments[-1]["salt"], f"{FAIL}Salt mismatch.{RESET}\n{source}."
                        assert dequalified(formula) == dequalified(segments[-1]["formula"]), f"{FAIL}Formula mismatch.{RESET}\n{source}."

                    next_salt = next_salt or segments[-1]["default_next_salt"]
                    token = token or segments[-1]["default_token"]
                    if label:
                        text = f"{label}. {text}"
                    solution = {
                        "intro": text, # a "sticky" annotation, useful for a variant with a different token
                        "query": query,
                        "result_head": self.extract_result_head(cell),
                        "next_salt": next_salt,
                        "token": token
                    }
                    if not text:
                        solution.pop("intro")
                    segments[-1]["solutions"].append(solution)

        # The segments are now complete, we can resolve the associations between salts and tokens.

        # Convert the salts into tokens
        tokens_by_salt = defaultdict(list)
        for segment in filter(lambda s: s["kind"] == "episode", segments):
            for solution in self.actual_solutions(segment):
                if token := solution["token"]:
                    tokens_by_salt[solution["next_salt"]].append(token)

        # Clean up the segments
        for segment in segments:
            del segment["default_next_salt"] # the default next salt has been propagated
            del segment["default_token"] # the default next token has been propagated
            for solution in self.actual_solutions(segment):
                del solution["next_salt"] # the next salt has been associated with the token
            if not segment["tweak"]: # formula without tweak
                del segment["tweak"]
            if not segment["formula"]: # episode without formula (the last one)
                del segment["formula"]
        
        # Number the adventures and their episodes
        adventure_counter = 0
        episode_counter = 0
        for segment in filter(lambda s: s["kind"] == "episode", segments):
            if segment["salt"] not in tokens_by_salt: # the first episode of an adventure
                adventure_counter += 1
                episode_counter = 0
            episode_counter += 1
            segment["part_number"] = adventure_counter
            segment["task_number"] = episode_counter

        # Create the (almost) final token dictionary
        records = {}
        non_hint_tokens = set()
        hint_tokens = set()
        for segment in segments:
            salt = segment["salt"]
            main_token = salt  # the salt serves as its own token in an exercise or a first episode
            if tokens := tokens_by_salt.get(salt):
                main_token, *tokens = tokens  # an episode (after the first one) is accessed by at least one token
                for token in tokens: # the remaining tokens are variants
                    records[token] = segment  # keep a dynamic reference for future updates
                    non_hint_tokens.add(token)
            non_hint_tokens.update(solution["token"] for solution in self.actual_solutions(segment))
            records[main_token] = segment
            non_hint_tokens.add(main_token)
            # Move the hints at the top level
            for hint in segment.pop("hints"):
                token = hint.pop("token") # no need to keep the token in the value, it will be kept in the key
                hint_tokens.add(token)
                hint["task_number"] = segment["task_number"]
                hint["salt"] = salt  # used and removed during the graph generation
                assert token not in records, f"{FAIL}Two hint queries produce the same token {token}{RESET}"
                records[token] = hint # each hint is accessed by exactly one token
        collisions = non_hint_tokens & hint_tokens
        assert not collisions, f"{FAIL}Hint tokens {collisions} collide with other tokens.{RESET}"

        # Generate the graph and (side effect) pop the hint salts from records
        self.dump_graph(records)

        return records
    
    @staticmethod
    def extract_first_token_from_output(
        code_cell: dict,
        search_token= re.compile(r"<th>token</th>\n(?:.+\n)*? *<td>(\d+)</td>\s+</tr>").search,
    ) -> Optional[str]:
        for output in code_cell["outputs"]:
            if "text/html" in output.get("data", ""):
                table = "".join(output["data"]["text/html"])
                if m := search_token(table):
                    return(m[1])

    @staticmethod
    def extract_result_head(code_cell: dict) -> str:
        # Find the first output which contains a html table.
        for output in code_cell["outputs"]:
            if "data" in output:
                table = "".join(output["data"]["text/html"])
                if table.startswith("<table>"):
                    n = table.count("<tr>") - 1  # Don't rely on the number of affected rows
                                                 # displayed by MySQL or PostgreSQL, since SQLite
                                                 # displays it only for the DML statements.
                    break
        else:
            print(f"{WARNING}No table in the output.{RESET}")
            print(code_cell["outputs"])
            print()
            return ""
        # Keep only the first two rows
        count_str = f"\nTotal: {n} row{'s'[:n^1]} affected."
        return re.sub(r"(?s)(<table>\n(?:.*?<tr>.+?</tr>\n){,3}).*(</table>)", fr"\1\2{count_str}", table)
    
    @staticmethod
    def actual_solutions(segment_or_record):
        """Filter out the annotations (strings) and return the actual solutions (dictionaries)."""
        for solution in segment_or_record["solutions"]:
            if isinstance(solution, str): # An annotation
                continue
            yield solution

    def dump_graph(self, records):
        hints_by_salt = defaultdict(list)
        for (token, record) in records.items():
            if isinstance(record, str):
                continue
            if record.get("kind") == "hint":
                x = record["salt"]
                hints_by_salt[x].append(token)
        middle_hints = {hints[len(hints) // 2]: len(hints) for hints in hints_by_salt.values()}
        data = {
            "exercise_edges": [],
            "exercise_starts": set(),
            "exercise_ends": [],
            "episode_edges": [],
            "episode_starts": set(),
            "episode_ends": set(),
            "epilogues": [],
            "hint_edges": [],
            "hint_ends": [],
        }
        has_exercises = False
        seen_records = set()
        for (token, record) in records.items():
            record_hash = hash(str(record))
            if record_hash in seen_records:
                continue
            seen_records.add(record_hash)
            if isinstance(record, str):
                continue
            x = record["salt"]
            if record["kind"] == "exercise":
                has_exercises = True
                for solution in self.actual_solutions(record):
                    y = solution["token"]
                    data["exercise_starts"].add(f"{x} [xlabel={record['task_number']}]")
                    data["exercise_edges"].append(f"{x} -> {y}")
                    data["exercise_ends"].append(f'{y}')
            elif record["kind"] == "episode":
                for solution in self.actual_solutions(record):
                    x = record["salt"]
                    if record["task_number"] == 1:
                        data["episode_starts"].add(f"{x} [xlabel=1]")
                    next_record = records.get(solution["token"])
                    if not next_record:
                        continue # A query without redirection
                    if isinstance(next_record, str):
                        next_record = records[next_record] # resolve the alias
                    y = next_record["salt"]
                    data["episode_edges"].append(f"{x} -> {y}")
                    data["episode_ends"].add(f'{y} [xlabel={next_record["task_number"]}]')
                if not record["solutions"]:
                    data["epilogues"].append(record["salt"])
            elif record["kind"] == "hint":
                y = token
                data["hint_edges"].append(f"{x} -> {y}")
                hint_count = middle_hints.get(y, 0)
                if hint_count:
                    data["hint_ends"].append(f'{y} [xlabel={hint_count}]')
                else:
                    data["hint_ends"].append(y)
                del record["salt"]
        for (key, value) in data.items():
            data[key] = "\n    ".join(sorted(value))

        # Save the graph and convert it into pdf and svg if graphviz is installed
        template = """digraph G {{
            layout={engine}
            bgcolor="#FDFEFF"
            edge [color="#34262B" penwidth=0.75]
            node [
                shape=star
                fixedsize=true
                width=0.3
                height=0.3
                fillcolor="#FEE548"
                color="#34262B"
                fontcolor="#34262B"
                fontsize=18
                penwidth=1
                style=filled
                label=""
            ]
            {exercise_ends}
            node [width=1.2 height=1.2 fontname=Helvetica label="\\N"]
            {epilogues}
            node [ width=0.6 height=0.6 shape=circle fillcolor="#FFC19C"]
            {episode_ends}
            node [fillcolor="#DBDE92"]
            {exercise_starts}
            {episode_starts}
            {exercise_edges}
            {episode_edges}
            node [width=0.1 height=0.1 label="" fillcolor=none]
            {hint_ends}
            edge [arrowhead=none]
            {hint_edges}
        }}
        """
        template = re.sub(r"(?m)^ {8}", "", template)
        data["engine"] = "twopi" if has_exercises else "dot\n    rankdir=LR"
        text = template.format(**data)
        previous_text = self.activity_map_gv_path.read_text(encoding="utf8")
        if previous_text == text:
            return # the graph has not changed, no need to update the files
        self.activity_map_gv_path.write_text(text)
        print(f"Graph written to '{self.activity_map_gv_path}'.")
        with contextlib.suppress(ImportError):
            graphviz = importlib.import_module("graphviz")
            source = graphviz.Source(text)
            for format in ("pdf", "svg"):
                source.render(
                    filename=self.graph_format_path[format].stem,
                    directory=self.graph_format_path[format].parent,
                    format=format,
                    cleanup=True
                )
                print(f"Activity map converted into {format.upper()}.")

