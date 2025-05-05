import json
from collections import defaultdict

from .text_tools import WARNING, RESET, OK, FAIL


class MessageBuilder:

    def __init__(self, config):
        self.strings = config["strings"]
        if "log_path" in config:
            log_path = config["log_path"]
            log_path.unlink(missing_ok=True)
            self.log = log_path.open("a", encoding="utf-8")
            print(f"Logging messages to '{log_path}'...")
        else:
            class NullLog:
                def write(self, _): pass
                def close(self): pass
            self.log = NullLog()

    def compose_formula(self, record):
        if not record.get("formula"):
            return {}
        if tweak := record.get("tweak", ""):
            tweak = self.strings['tweak_instruction'].format(repl=tweak)
        result =  {
            "formula": {
                "label": self.strings['formula_label'],
                "tweak": tweak,
                "code": record["formula"],
            }
        }
        for (key, value) in record.items():
            if key.startswith("tweak_"):
                result["formula"][key] = value
        return result
    
    def compose_solutions(self, solutions):
        if not solutions:
            return {}
        acc = []
        for solution in solutions:
            if isinstance(solution, str):
                acc.append({
                    "annotation": solution
                })
            else:
                acc.append({
                    "solution": {
                        "intro": solution.get("intro", ""),
                        "query": solution["query"],
                    }
                })
        return {"solutions": acc}
    
    @staticmethod
    def actual_solutions(solutions):
        """Filter out the annotations from a sequence of so-called solutions."""
        for solution in solutions:
            if isinstance(solution, str): # An annotation
                continue
            yield solution # An actual solution

    @staticmethod
    def get_first_token_from_solutions(solutions):
        for solution in MessageBuilder.actual_solutions(solutions):
            return solution["token"]

    def run(self, records):
        self.rows = {}
        solutions_by_token = defaultdict(list)
        for (entry_token, record) in records.items():

            if isinstance(record, str): # an alias, i.e. an alternative token to access the same record
                continue

            if record["kind"] == "hint":
                self.log.write(f"    Hint ({entry_token}): {repr(record['text'][:100])}\n")
                self.rows[entry_token] = (
                    "hint",
                    {
                        "label": task_label,  # defined on a previous iteration
                        "task_number": counter,  # defined on a previous iteration
                        "preamble": self.strings["preamble_rejected"],
                        "text": record["text"]
                    }
                )
                continue

            counter = record["task_number"]
            formula = self.compose_formula(record)

            if record["kind"] == "episode":
                task_label = self.strings["episode_label"]
                self.log.write(f"  Question {counter} ({entry_token}): {repr(record['statement'][:100])}\n")
                current_token = self.get_first_token_from_solutions(record["solutions"])
                if current_token: # All episodes should have at least one solution, except for the last one
                    for solution in record["solutions"]:
                        if isinstance(solution, str): # an annotation
                            solutions_by_token[current_token].append(solution)
                        else:
                            current_token = solution["token"]
                            # When the same episode has several entries, avoid duplicating its solutions
                            if solution["query"] not in solutions_by_token[current_token]:
                                solutions_by_token[current_token].append(solution)
                self.rows[entry_token] = (
                    "episode",
                    {
                        "label": task_label,
                        "task_number": counter,
                        "token": entry_token,
                        **self.compose_solutions(solutions_by_token[entry_token]),
                        "context": record["context"],
                        "statement_label": self.strings["statement_label"],
                        "statement": record["statement"],
                        **formula,
                    }
                )
            
            else:
                assert record["kind"] == "exercise", f"{FAIL}Unexpected kind: {record['kind']}.{RESET}"
                task_label = self.strings["exercise_label"]

                self.log.write(f"Exercise {counter} ({entry_token}): {repr(record['statement'][:100])}\n")
                self.rows[entry_token] = (
                    "exercise_statement",
                    {
                        "label": task_label,
                        "task_number": counter,
                        "statement": record["statement"],
                        **formula,
                    }
                )

                exercise_correction = (
                    "exercise_correction",
                    {
                        "label": task_label,
                        "task_number": counter,
                        "token": entry_token,
                        **self.compose_solutions(record["solutions"]),
                    }
                )
                for solution in self.actual_solutions(record["solutions"]):
                    next_token = solution["token"]
                    if next_token in self.rows: # An output token already registered
                        continue
                    # A first solution or a variant with a distinct output token
                    self.rows[next_token] = exercise_correction

        for (alias, token) in records.items():
            if isinstance(token, str):
                self.rows[alias] = self.rows[token]
        
        for token in solutions_by_token.keys():
            assert token in self.rows, f"{FAIL}Missing output token: {token}. Check that the adventure's last episode has no query.{RESET}"

        print(f"{OK if self.rows else WARNING}{len(self.rows)} messages generated.{RESET}")
        self.log.close()
        return self.rows

    def compile_toc(self, records):
        result = {}
        for (token, record) in records.items():
            if isinstance(record, str):
                continue
            if record["kind"] in ("exercise", "episode"):
                part_number = record["part_number"]
                part = result.get(part_number, {})
                if not part:
                    result[part_number] = {
                        "kind": "exercises" if record["kind"] == "exercise" else "adventure",
                        "label": self.strings[f"{record['kind']}_collection_label"],
                        "part_number": part_number,
                        "task_count": 0,
                        "open_tasks": [],
                    }
                result[part_number]["task_count"] += 1
                if record["task_number"] == 1 or record["kind"] == "exercise":
                    result[part_number]["open_tasks"].append({
                        "entry_token": token,
                        "task_number": record["task_number"],
                    })
        return list(result.values())

    def compile_storyline(self, records):
        result = []
        previous_records_hashes = set() # Cf. compile_cheat_sheet
        for (token, record) in records.items():
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
            if isinstance(record, str) or record["kind"] != "exercise":
                continue
            if section := record.get("section"):
                result.append(f"\n{section}\n")
            statement_start = record["statement"].split("\n")[0]
            i = record["task_number"]
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
            if isinstance(record, str):
                continue
            if record["kind"] == "hint":
                continue
            record_hash = hash(json.dumps(record, sort_keys=True, ensure_ascii=False))
            if record_hash in previous_records_hashes:
                continue
            previous_records_hashes.add(record_hash)
            counter = record["task_number"]
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
                formula = record["formula"].replace("{{x}}", "(0)")
                result.append(f"\n**{self.strings['formula_label']}**{tweak}. `{formula}`\n")
            for solution in record["solutions"]:
                if isinstance(solution, str):
                    result.append(f"{solution}\n")
                else:
                    if intro := solution.get("intro"):
                        result.append(f"{intro}\n")
                    result.append(f"```sql\n{solution['query']}\n```\n")
        if result:
            result.insert(0, f"# Cheat sheet\n")
            result.append("")
            return "\n".join(result)
