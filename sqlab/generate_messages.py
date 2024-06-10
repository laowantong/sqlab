import json
from collections import defaultdict

from .text_tools import TextWrapper, transform_markdown, join_non_empty, WARNING, RESET, OK, FAIL


class MessageGenerator:
    def __init__(self, config):
        self.wrap_text = TextWrapper(config)
        self.strings = config["strings"]
        self.column_width = config.get("column_width") or 100
        self.hr = "-" * self.column_width
        if "log_path" in config:
            log_path = config["log_path"]
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
            tweak = f" ({self.strings['tweak_instruction'].format(repl=tweak)})"
        title = self.format_text(f"**{self.strings['formula_label']}**{tweak}.")
        return f"{title}\n, {record['formula']}"
    
    def compose_solutions(self, solutions):
        if not solutions:
            return ""
        result = [self.hr]
        for solution in solutions:
            if isinstance(solution, str):
                result.append(self.format_text(solution))
            else:
                if solution_preamble := solution.get("solution_preamble"):
                    result.append(self.format_text(solution_preamble))
                result.append(solution["query"])
        result.append(self.hr)
        return "\n\n".join(result)
    
    @staticmethod
    def actual_solutions(solutions):
        """Filter out the annotations from a sequence of so-called solutions."""
        for solution in solutions:
            if isinstance(solution, str): # An annotation
                continue
            yield solution # An actual solution

    @staticmethod
    def get_first_token_from_solutions(solutions):
        for solution in MessageGenerator.actual_solutions(solutions):
            return solution["token"]

    def run(self, records):
        self.rows = {}
        context = ""
        solutions_by_token = defaultdict(list)
        for (entry_token, record) in records.items():

            if entry_token == "info":
                continue

            if isinstance(record, str): # an alias, i.e. an alternative token to access the same record
                continue

            if record["kind"] == "hint":
                self.log(f"    Hint ({entry_token}): {repr(record['text'][:100])}\n")
                preamble = f"🟠 {counter}. {self.strings['preamble_rejected']}"
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
                    preamble = f"🟢 {counter}. {self.strings['preamble_accepted']}"
                current_token = self.get_first_token_from_solutions(record["solutions"])
                if current_token: # All episodes should have at least one solution, except for the last one
                    for solution in record["solutions"]:
                        if isinstance(solution, str): # an annotation
                            solutions_by_token[current_token].append(self.format_text(solution))
                        else:
                            current_token = solution["token"]
                            # When the same episode has several entries, avoid duplicating its solutions
                            if solution["query"] not in solutions_by_token[current_token]:
                                solutions_by_token[current_token].append(solution["query"])
                solutions = self.compose_solutions(solutions_by_token[entry_token])
                context = self.format_text(record["context"])
                statement = self.format_text(f"**{self.strings['statement_label']}**. {record['statement']}")
                self.rows[entry_token] = join_non_empty(preamble, solutions, context, statement, formula)

            else:
                assert record["kind"] == "exercise", f"{FAIL}Unexpected kind: {record['kind']}.{RESET}"

                self.log(f"Exercise {counter} ({entry_token}): {repr(record['statement'][:100])}\n")
                statement = self.format_text(f"⚪️ **{self.strings['exercise_label']} {counter}**. {record['statement']}")
                self.rows[entry_token] = join_non_empty(statement, formula)
                preamble = f"🟢 {counter}. {self.strings['preamble_accepted']}"
                plain_text = join_non_empty(preamble, self.compose_solutions(record["solutions"]))
                for solution in self.actual_solutions(record["solutions"]):
                    next_token = solution["token"]
                    if next_token in self.rows: # An output token already registered
                        continue
                    # A first solution or a variant with a distinct output token
                    self.rows[next_token] = plain_text

        for (alias, token) in records.items():
            if isinstance(token, str):
                self.rows[alias] = self.rows[token]
        
        for token in solutions_by_token.keys():
            assert token in self.rows, f"{FAIL}Missing output token: {token}. Check that the adventure's last episode has no query.{RESET}"

        markup = OK if self.rows else WARNING
        print(f"{markup}{len(self.rows)} messages generated.{RESET}")

        return self.rows

    def compile_storyline(self, records):
        result = []
        previous_records_hashes = set() # Cf. compile_cheat_sheet
        for (token, record) in records.items():
            if token == "info":
                continue
            if isinstance(record, str) or record["kind"] != "episode":
                continue
            record_hash = hash(json.dumps(record, sort_keys=True, ensure_ascii=False))
            if record_hash in previous_records_hashes:
                continue
            previous_records_hashes.add(record_hash)
            result.append(f"\n{record['context']}\n")
            if solutions := record["solutions"]:
                result.append(f"<details><summary>{self.strings['statement_label']}</summary>{record['statement']}<br><br>")
                for solution in self.actual_solutions(solutions):
                    if result_head := solution.get("result_head"):
                        result.append(f"\n{result_head}\n")
                        break
                result.append("</details><br>\n")
        if result:
            result.append("")
            return "\n".join(result)

    def compile_exercises(self, records):
        result = []
        for (token, record) in records.items():
            if token == "info":
                continue
            if isinstance(record, str) or record["kind"] != "exercise":
                continue
            if section := record.get("section"):
                result.append(f"\n{section}\n")
            statement_start = record["statement"].split("\n")[0]
            i = record["counter"]
            result.append(f"- **{self.strings['exercise_label']} {i}**. {statement_start}  ")
            first_token = self.get_first_token_from_solutions(record["solutions"])
            result.append("  " + self.strings["exercise_tokens"].format(salt=record["salt"], token=first_token))
        if result:
            result.append("")
            return "\n".join(result)
    
    def compile_cheat_sheet(self, records):
        result = []
        previous_records_hashes = set() # When a variant produces a different token than the first
                                        # query, the next episode needs to be accessed through the
                                        # two tokens. In records.json, the episode dictionary is
                                        # duplicated and associated with these two tokens. In
                                        # cheat_sheet.md, this duplication is avoided.
        for (token, record) in records.items():
            if token == "info":
                continue
            if isinstance(record, str):
                continue
            if record["kind"] == "hint":
                continue
            record_hash = hash(json.dumps(record, sort_keys=True, ensure_ascii=False))
            if record_hash in previous_records_hashes:
                continue
            previous_records_hashes.add(record_hash)
            counter = record["counter"]
            if counter == 1:
                if record["kind"] == "episode":
                    result.append(f"## {self.strings['adventure_label']}\n")
                    label = self.strings['episode_label']
                else:
                    result.append(f"## {self.strings['exercises_label']}\n")
                    label = self.strings['exercise_label']
            result.append(f"### {label} {counter}\n")
            result.append(f"**Token.** {token}.\n")
            result.append(record['statement'].replace("\\n", "\n"))
            if record.get("formula"):
                if tweak := record.get("tweak", ""):
                    tweak = f" ({self.strings['tweak_instruction'].format(repl=tweak)})"
                formula = record["formula"].replace("{{x}}", "(0.0)")
                result.append(f"\n**{self.strings['formula_label']}**{tweak}. `{formula}`\n")
            for solution in record["solutions"]:
                if isinstance(solution, str):
                    result.append(f"{solution}\n")
                else:
                    if solution_preamble := solution.get("solution_preamble"):
                        result.append(f"{solution_preamble}\n")
                    result.append(f"```sql\n{solution['query']}\n```\n")
        if result:
            result.insert(0, f"# Cheat sheet\n")
            result.append("")
            return "\n".join(result)

