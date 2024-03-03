
from collections import defaultdict
from pathlib import Path
import re

from .text_tools import TextWrapper, transform_markdown, join_non_empty, WARNING, RESET, OK, FAIL


class MessageGenerator:
    def __init__(self, config):
        self.wrap_text = TextWrapper(config)
        self.strings = config["strings"]
        self.column_width = config.get("column_width") or 100
        self.hr = "-" * self.column_width
        if "output_dir" in config:
            log_path = Path(config["output_dir"], "msg.log")
            log_path.unlink(missing_ok=True)
            self.log = log_path.open("a", encoding="utf-8").write
            print(f"Logging messages to '{log_path.name}'...")
        else:
            self.log = lambda _: None
    
    def format_text(self, text):
        text = transform_markdown(text, self.column_width)
        text = self.wrap_text(text)
        return text

    def compose_formula(self, record):
        if not record.get("formula"):
            return ""
        if tweak := record.get("tweak", ""):
            tweak = f" ({self.strings['emoji_instruction'].format(repl=tweak)})"
        title = self.format_text(f"**{self.strings['formula_label']}**{tweak}.")
        return f"{title}\n{record['formula']}"
    
    def compose_solutions(self, solutions):
        if not solutions:
            return ""
        return "\n\n".join([self.hr] + solutions + [self.hr])

    def run(self, records):
        self.rows = {}
        context = ""
        solutions_by_token = defaultdict(list)
        for (entry_token, record) in records.items():

            if isinstance(record, str): # an alias, i.e. an alternative token to access the same record
                continue

            if record["kind"] == "hint":
                self.log(f"    Hint ({entry_token}): {repr(record['text'][:100])}\n")
                preamble = f"🟠 {counter}. {self.strings['preamble_hint']}"
                hint = self.format_text("➥ " + record["text"])
                self.rows[entry_token] = join_non_empty(preamble, hint)
                continue

            counter = record["counter"]
            formula = self.compose_formula(record)

            if record["kind"] == "episode":
                self.log(f"  Question {counter} ({entry_token}): {repr(record['statement'][:100])}\n")
                if counter == 1:
                    preamble = f"⚪️ {counter}. {self.strings['preamble_adventure']}"
                else:
                    preamble = f"🟢 {counter}. {self.strings['preamble_correct']}"
                for d in record.get("solutions", []):
                    solutions_by_token[d["token"]].append(self.format_text("{text}\n\n{query}".format(**d).strip()))
                solutions = self.compose_solutions(solutions_by_token[entry_token])
                context = self.format_text(record["context"])
                statement = self.format_text(f"**{self.strings['statement_label']}**. {record['statement']}")
                self.rows[entry_token] = join_non_empty(preamble, solutions, context, statement, formula)

            else:
                assert record["kind"] == "exercise", f"{FAIL}Unexpected kind: {record['kind']}.{RESET}"

                self.log(f"Exercise {counter} ({entry_token}): {repr(record['statement'][:100])}\n")
                statement = self.format_text(f"⚪️ **{self.strings['exercise_label']} {counter}**. {record['statement']}")
                self.rows[entry_token] = join_non_empty(statement, formula)
                preamble = f"🟢 {counter}. {self.strings['preamble_correct']}"
                solutions = [self.format_text("{text}\n\n{query}".format(**d)) for d in record["solutions"]]
                plain_text = join_non_empty(preamble, self.compose_solutions(solutions))
                for solution in record["solutions"]:
                    next_token = solution["token"]
                    if next_token in self.rows: # An output token already registered
                        continue
                    # A first solution or a variant with a distinct output token
                    self.rows[next_token] = plain_text

        for (alias, token) in records.items():
            if isinstance(token, str):
                self.rows[alias] = self.rows[token]

        markup = OK if self.rows else WARNING
        print(f"{markup}{len(self.rows)} messages generated.")

        return self.rows

    def compile_plot(self, records):
        result = []
        for record in records:
            if isinstance(record, str) or record["kind"] != "episode":
                continue
            result.append(f"\n{record['context']}\n")
            if solutions := record["solutions"]:
                result.append(f"<details><summary>{self.strings['statement_label']}</summary>{record['statement']}<br><br>")
                if result_head := solutions[0].get("result_head"):
                    result.append(f"\n{result_head}\n")
                result.append("</details><br>\n")
        if result:
            result.append("")
            return "\n".join(result)

    def compile_exercises(self, records):
        result = []
        for record in records:
            if isinstance(record, str) or record["kind"] != "exercise":
                continue
            if section := record.get("section"):
                result.append(f"\n{section}\n")
            statement_start = record["statement"].split("\n")[0]
            i = record["counter"]
            result.append(f"- **{self.strings['exercise_label']} {i}**. {statement_start}  ")
            result.append(f"  {self.strings['full_statement']} : `call decrypt({record['salt']})`. {self.strings['solution_label']} : `call decrypt({record['solutions'][0]['token']})`.")
        if result:
            result.append("")
            return "\n".join(result)
    
    def compile_cheat_sheet(self, records):
        result = []
        for (token, record) in records.items():
            if isinstance(record, str):
                continue
            if record["kind"] == "hint":
                continue
            counter = record["counter"]
            if counter == 1:
                if record["kind"] == "episode":
                    result.append(f"## {self.strings['adventure_label']}\n")
                    label = self.strings['episode_label']
                else:
                    result.append(f"## {self.strings['exercises_label']}\n")
                    label = self.strings['exercise_label']
            result.append(f"### {label} {counter}\n")
            if record.get("solutions"):
                solution = record["solutions"][0]
                result.append(f"**Token.** `call decrypt({token})`\n")
            result.append(record['statement'].replace("\\n", "\n"))
            if record.get("formula"):
                if tweak := record.get("tweak", ""):
                    tweak = f" ({self.strings['emoji_instruction'].format(repl=tweak)})"
                formula = record["formula"].replace("{{x}}", "👀")
                result.append(f"\n**{self.strings['formula_label']}**{tweak}. `{formula}`\n")
            for solution in record["solutions"]:
                if solution["text"]:
                    result.append(f"{solution['text']}\n")
                result.append(f"```sql\n{solution['query']}\n```\n")
        if result:
            result.insert(0, f"# Cheat sheet\n")
            result.append("")
            return "\n".join(result)

