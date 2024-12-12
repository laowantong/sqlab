from pathlib import Path
from csv import reader
from dataclasses import dataclass, fields
import re

@dataclass
class Item:
    token: int  # the token number
    adventure: int  # the adventure number, or 0 for an exercise
    counter: int  # the number of the exercise or the episode
    salt: str # three digits
    task: str  # either "exercise" or "episode" or "N/A"
    kind: str  # either "entry" for an exercise or the first episode of an adventure,
    #                   "exit" for a solution of an exercise
    #                   "answer" for a solution of an episode other than the first one
    #                   "hint" for a hint


class TokenTable:

    header = [field.name for field in fields(Item)]

    def __init__(self, records_or_path):
        if isinstance(records_or_path, Path):
            self.init_table_from_path(records_or_path)
        else:
            self.init_table_from_records(records_or_path)

    def init_table_from_path(self, path):
        with open(path) as f:
            r = reader(f, delimiter="\t")
            next(r)  # Skip the header
            self.token_table = []
            for (token, adventure, counter, salt, task, kind) in r:
                self.token_table.append(Item(
                    int(token),
                    int(adventure),
                    int(counter),
                    salt,
                    task,
                    kind))

    def init_table_from_records(self, records):
        values = []
        for token, record in records.items():
            if token == "info":
                continue
            salt = record.get("salt")
            if salt is None:
                if m := re.search(r"salt_(\d+)", record.get("query", "")):
                    salt = m.group(1)
                else:
                    salt = "N/A"  # e.g., when a hash is mistaken for a token
            kind = record["kind"]
            counter = record["counter"]
            if kind == "episode":
                adventure = record["adventure"]
            elif kind == "exercise":
                adventure = 0
                for solution in record["solutions"]:
                    if isinstance(solution, str):
                        continue
                    values.append((salt, "exit", adventure, counter, solution["token"]))
            values.append((salt, kind, adventure, counter, token))
        values.sort()
        tasks = []
        task = None
        for (salt, kind, adventure, counter, token) in values:
            if kind in ("exercise", "episode"):
                task = kind
                kind = "entry" if int(token) <= 999 else "answer"
            if salt == "N/A":
                task = "N/A"
            tasks.append((task, adventure, counter, kind, salt, int(token)))
        tasks.sort()
        self.token_table = []
        for (task, adventure, counter, kind, salt, token) in tasks:
            self.token_table.append(Item(token, adventure, counter, salt, task, kind))

    def write_as_tsv(self, path):
        with open(path, "w") as f:
            f.write("\t".join(self.header) + "\n")
            for item in self.token_table:
                f.write("\t".join(str(getattr(item, field)) for field in self.header) + "\n")

    def as_dict(self, db_name):
        return {(db_name, item.token): item.__dict__ for item in self.token_table}
