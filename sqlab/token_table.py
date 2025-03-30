from pathlib import Path
import csv
from dataclasses import dataclass, fields
import re

@dataclass
class Item:
    token: int  # the token number
    part: int  # 0 for an exercise, or a positive integer for an adventure
    source: int  # the number of the exercise or the episode which produces the token
    target: int  # the number of the exercise or the episode where the query leads
    action: str  # either "enter", "move", "hint" or "exit" a task
    salt: str # three digits

class TokenTable:

    header = [field.name for field in fields(Item)]

    def __init__(self, records_or_path):
        if isinstance(records_or_path, Path):
            self.init_table_from_path(records_or_path)
        else:
            self.init_table_from_records(records_or_path)

    def init_table_from_path(self, path):
        with open(path) as f:
            r = csv.reader(f, delimiter="\t")
            next(r)  # Skip the header
            self.token_table = []
            for (token, part, source, target, action, salt) in r:
                self.token_table.append(Item(int(token), int(part), int(source), int(target), action, salt))

    def init_table_from_records(self, records):
        values = set()  # Most variants of a solution produce the same token: keep only one
        epilogue_tokens = set()  # Tokens of the last episode of an adventure

        for (token, record) in records.items():
            if token == "info":
                continue

            kind = record["kind"]
            task_index = record["counter"]

            if kind == "episode":
                part = record["adventure"]
                if task_index == 1: # The first episode of an adventure cannot be added as a solution
                    values.add((part, 0, 1, "N/A", token))
                elif not record["solutions"]: # Store the token of the last episode of an adventure
                    epilogue_tokens.add(token)
                for solution in record["solutions"]:
                    if not isinstance(solution, str):
                        values.add((part, task_index, task_index + 1, record["salt"], solution["token"]))

            elif kind == "hint":
                part = part  # Keep the previous value, since a hint is part of an exercise
                if m := re.search(r"salt_(\d+)", record.get("query", "")):
                    salt = m.group(1)
                else:  # A hash value or an example mistaken for a token
                    salt = "N/A"
                values.add((part, task_index, task_index, salt, token))

            elif kind == "exercise":
                part = 0
                values.add((part, 0, task_index, "N/A", token))  # Each exercise is an entry point
                for solution in record["solutions"]:
                    if not isinstance(solution, str):
                        values.add((part, task_index, 0, record["salt"], solution["token"]))
            
            else:
                raise ValueError(f"Unknown kind: {kind}")

        values= sorted(values, key=lambda x: (x[0], max(x[1], x[2]), x[1], -x[2], x[3], x[4]))
        self.token_table = []
        for (part, source, target, salt, token) in values:
            if token in epilogue_tokens: # The last episode of an adventure
                target = 0  # The original value (task_index + 1) should be corrected
            if source == target: # A loop
                action = "hint"
            elif source == 0: # An entry point (for an exercise or a a first episode)
                action = "enter"
            elif target == 0: # An exit point (for an exercise or a last episode)
                action = "move"
            elif source < target: # An internal forward move
                action = "move"
            else:
                raise ValueError(f"Invalid source and target: {source} -> {target}")
            self.token_table.append(Item(token, part, source, target, action, salt))

    def write_as_tsv(self, path):
        with open(path, "w") as f:
            f.write("\t".join(self.header) + "\n")
            for item in self.token_table:
                f.write("\t".join(str(getattr(item, field)) for field in self.header) + "\n")

    def as_dict(self, db_name):
        return {(db_name, item.token): item.__dict__ for item in self.token_table}
