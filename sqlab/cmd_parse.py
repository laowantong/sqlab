from collections import defaultdict
import contextlib
import itertools
import json
from pathlib import Path
import re
from typing import Optional
import importlib

from .text_tools import FAIL, OK, RESET, WARNING
from .text_tools import separate_label_salt_and_text, split_sql_source, separate_query_and_formula

def run(config: dict):
    parser = NotebookParser(config)
    print(f"Updating the records...")
    ipynb = json.loads(config["source_path"].read_text())
    records = parser(ipynb["cells"])
    print(f"{OK}The records are up to date.{RESET}")
    text = json.dumps(records, indent=2, ensure_ascii=False)
    Path(config["output_dir"], "records.json").write_text(text, encoding="utf-8")
    return records

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
        self.graph_path = Path(config["output_dir"], "graph.gv")

        
    def __call__(self, cells):

        # Create an intermediate representation of the notebook, a list of segments.
        # Each segment must contain all informations pertaining to a single exercise or episode.
        # The associations between salts and tokens will be resolved later, in a stateless way
        # (i.e. no need to store any auxiliary data at a given stage for use at a later stage).

        segments = []
        section_buffer = []
        salts = set()
        for cell in cells:
            source = cell["source"]
            if not source:
                # Ignore empty cells.
                continue

            if cell["cell_type"] == "markdown":
                source = "".join(source)

                if m := re.match(r"(#+ .+?) *\(\+\)", cell["source"][0]):
                    # Accumulate the section names ending by '(+)'
                    section_buffer.append(m[1])
                    continue

                (label, salt, text) = separate_label_salt_and_text(source)
                if not label:
                    continue
                assert salt not in salts, f"{FAIL}Salt '{salt}' already used.\n{source}.{RESET}"
                if salt:
                    salts.add(salt)

                kind = self.labels_to_kinds.get(label.lower())
                assert kind in ("statement", "episode", "exercise"), f"Unknown label '{label}'."

                if kind == "statement":
                    assert segments, f"{FAIL}A statement must be preceded by an exercise or an episode.\n{source}.{RESET}"
                    assert not segments[-1]["statement"], f"{FAIL}{segments[-1]['kind']} [{segments[-1]['salt']}] already has a statement.\n{source}.{RESET}"
                    segments[-1]["statement"] = text
                    continue

                segment = {}
                segment["kind"] = kind
                segment["counter"] = None # to be filled after the segments are complete
                if section_buffer:
                    segment["section"] = "\n".join(section_buffer)
                    section_buffer.clear()
                if kind == "episode":
                    segment["context"] = text
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

                # If the cell starts with a Python assignement of the form x = ... # ...,
                # store the instruction for replacing the Eyes emoji with the value of x.
                if m := re.match(r"x *= *.+ *# *(.+)", source[0]):
                    assert segments, f"{FAIL}A tweak must be preceded by an exercise or an episode.\n{source}.{RESET}"
                    assert not segments[-1]["tweak"], f"{FAIL}{segments[-1]['kind']} [{segments[-1]['salt']}] already has a tweak.\n{source}.{RESET}"
                    segments[-1]["tweak"] = segments[-1]["tweak"] or m[1] # store the first tweak as the default one

                # Ignore all the cells that do not start with the magic command %%sql.
                if not source[0].startswith("%%sql"):
                    continue

                # Now we have a code cell that starts with %%sql.
                source = "".join(source[1:])  # strips the magic command
                (label, text, raw_query, next_salt) = split_sql_source(source)
                kind = self.labels_to_kinds.get(label.lower(), "")
                (query, formula, salt) = separate_query_and_formula(raw_query)
                token = self.extract_first_token_from_output(cell)

                if salt:
                    assert salt != next_salt, f"{FAIL}Self-reference with salt {salt}.\n{source}{RESET}"

                # The query is either a solution or a hint.
                if kind == "hint":
                    assert token, f"{FAIL}Missing token for hint:{RESET}\n{source}."
                    segments[-1]["hints"].append({
                        "kind": kind,
                        "counter": None,  # to be filled after the segments are complete
                        "text": text,
                        "query": raw_query,  # a wrong query is never displayed, but is stored as is for debugging purposes
                        "token": token
                    })

                else: # Regard the query as a solution, whatever the label ("solution", "variant", "", etc.)
                    if not segments[-1]["formula"]: # We are in the first solution of the segment
                        assert formula, f"{FAIL}Missing formula for {segments[-1]['kind']} [{segments[-1]['salt']}].{RESET}\n{source}."
                        if "👀" in formula:
                            assert segments[-1]["tweak"], f"{FAIL}Missing tweak for {segments[-1]['kind']} [{segments[-1]['salt']}].{RESET}\n{source}."
                        else:
                            assert not segments[-1]["tweak"], f"{FAIL}Missing {{{{x}}}} in the formula of a first solution.{RESET}\n{source}."
                        assert segments[-1]["statement"], f"{FAIL}Missing statement cell for {segments[-1]['kind']} [{segments[-1]['salt']}].{RESET}\n{source}."
                        # Store the first formula, next salt and token as the default ones
                        segments[-1]["formula"] = formula
                        segments[-1]["default_next_salt"] = next_salt
                        segments[-1]["default_token"] = token
                    
                    if formula: # The formula is explicitely stated
                        assert salt == segments[-1]["salt"], f"{FAIL}Salt mismatch for {kind} [{label}].{RESET}\n{source}."
                        assert formula == segments[-1]["formula"], f"{FAIL}Formula mismatch for {kind} [{label}].{RESET}\n{source}."

                    next_salt = next_salt or segments[-1]["default_next_salt"]
                    token = token or segments[-1]["default_token"]
                    segments[-1]["solutions"].append({
                        "text": f"{label}. {text}" if label else text,
                        "query": query,
                        "result_head": self.extract_result_head(cell),
                        "next_salt": next_salt,
                        "token": token
                    })

        # The segments are now complete, we can resolve the associations between salts and tokens.

        # Convert the salts into tokens
        tokens_by_salt = defaultdict(list)
        for segment in filter(lambda s: s["kind"] == "episode", segments):
            for solution in segment["solutions"]:
                if token := solution["token"]:
                    tokens_by_salt[solution["next_salt"]].append(token)

        # Clean up the segments
        for segment in segments:
            del segment["default_next_salt"] # the default next salt has been propagated
            del segment["default_token"] # the default next token has been propagated
            for solution in segment["solutions"]:
                del solution["next_salt"] # the next salt has been associated with the token
            if not segment["tweak"]: # formula without tweak
                del segment["tweak"]
            if not segment["formula"]: # episode without formula (the last one)
                del segment["formula"]
        
        # Number the exercises
        exercise_counter = itertools.count(1)
        for segment in filter(lambda s: s["kind"] == "exercise", segments):
            segment["counter"] = next(exercise_counter)

        # Number the episodes
        for segment in filter(lambda s: s["kind"] == "episode", segments):
            if segment["salt"] not in tokens_by_salt: # the first episode of an adventure
                episode_counter = itertools.count(1) # initialize or reset the counter
            segment["counter"] = next(episode_counter)

        # Create the (almost) final token dictionary
        records = {}
        non_hint_tokens = set()
        hint_tokens = set()
        for segment in segments:
            salt = segment["salt"]
            main_token = salt  # the salt serves as its own token in an exercise or a first episode
            if tokens := tokens_by_salt.get(salt):
                main_token = tokens.pop()  # an episode (after the first one) is accessed by at least one token
                for token in tokens: # the remaining tokens are aliases
                    records[token] = main_token
                    non_hint_tokens.add(token)
            non_hint_tokens.update(solution["token"] for solution in segment["solutions"])
            records[main_token] = segment
            non_hint_tokens.add(main_token)
            # Move the hints at the top level
            for hint in segment.pop("hints"):
                token = hint.pop("token") # no need to keep the token in the value, it will be kept in the key
                hint_tokens.add(token)
                hint["counter"] = segment["counter"]
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
                    break
        else:
            print(f"{WARNING}No table in the output.{RESET}")
            print(code_cell["outputs"])
            print()
            return ""
        # Find the first output which contains the number of rows affected.
        for output in code_cell["outputs"]:
            if "text" in output:
                count = output["text"][0]
                break
            elif "data" in output and "text/plain" in output["data"]:
                count = output["data"]["text/plain"][0]
                break
        else:
            print(f"{WARNING}No text field in the output.{RESET}")
            print(code_cell["outputs"])
            return ""
        # Keep only the first two rows
        return re.sub(r"(?s)(<table>\n(?: *<tr>.+?</tr>\n){,3}).*(</table>)", fr"\1\2\nTotal: {count}", table)

    def dump_graph(self, records):
        data = {
            "exercise_edges": [],
            "exercise_ends": [],
            "episode_edges": [],
            "episode_ends": [],
            "epilogues": [],
            "hint_edges": [],
            "hint_ends": [],
        }
        has_exercises = False
        for (token, record) in records.items():
            if isinstance(record, str):
                continue
            x = record["salt"]
            if record["kind"] == "exercise":
                has_exercises = True
                for solution in record["solutions"]:
                    y = solution["token"]
                    data["exercise_edges"].append(f"{x} -> {y}")
                    data["exercise_ends"].append(f"{y}")
            elif record["kind"] == "episode":
                for solution in record["solutions"]:
                    x = record["salt"]
                    next_record = records[solution["token"]]
                    if isinstance(next_record, str):
                        next_record = records[next_record] # resolve the alias
                    y = next_record["salt"]
                    data["episode_edges"].append(f"{x} -> {y}")
                    data["episode_ends"].append(y)
            elif record["kind"] == "hint":
                y = token
                data["hint_edges"].append(f"{x} -> {y}")
                data["hint_ends"].append(y)
                del record["salt"]
        for (key, value) in data.items():
            sep = "\n    " if key.endswith("_edges") else " "
            data[key] = sep.join(value)

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
            node [
                width=1.2
                height=1.2
                fontname=Helvetica
                label="\\N"
            ]
            {epilogues}
            node [
                width=0.6
                height=0.6
                shape=circle
                fillcolor="#FFC19C"
            ]
            {episode_ends}
            node [fillcolor="#DBDE92"]
            {exercise_edges}
            {episode_edges}
            node [style=invisible label=""]
            {hint_ends}
            edge [arrowhead=odot]
            {hint_edges}
        }}
        """
        template = re.sub(r"(?m)^ {8}", "", template)
        data["engine"] = "twopi" if has_exercises else "dot\n  rankdir=LR"
        text = template.format(**data)
        self.graph_path.write_text(text)
        print(f"Graph written to '{self.graph_path}'.")
        with contextlib.suppress(ImportError):
            graphviz = importlib.import_module("graphviz")
            source = graphviz.Source(text)
            for format in ("pdf", "svg"):
                source.render(
                    filename=self.graph_path.stem,
                    directory=self.graph_path.parent,
                    format=format,
                    cleanup=True
                )
                print(f"Graph converted into {format.upper()}.")

