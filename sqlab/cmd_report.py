"""
Parse the CSV file student_logs.csv.
For each call to the function `decrypt()`, check if the `token` argument is in `records.json`.
If not, print the previous query.
"""

import csv
import itertools
import json
import re
from collections import Counter, defaultdict
from hashlib import md5
from pathlib import Path

from .database import database_factory, SQLError
from .text_tools import FAIL, OK, RESET, WARNING, SQLFormatter
from .cmd_parse import run as parse_notebook

def parse_tsv(log_path: Path) -> list[tuple]:
    result = []
    with log_path.open() as file:
        reader = csv.DictReader(file)
        for row in reader:
            (timestamp, query) = tuple(row.values())
            result.append((timestamp, query))
    return result

def init_report(records: list[dict]) -> dict:
    result = {}
    exercise_counter = itertools.count(1)
    question_counter = itertools.count(1)
    for record in records:
        kind = record.get("kind")
        if "output_token" in record:
            token = record.get("output_token")
            if kind == "exercise":
                i = next(exercise_counter)
                sub_counter = itertools.count(1)
            elif kind in ("question", "adventure"):
                i = next(question_counter)
                sub_counter = itertools.count(1)
            if kind in ("exercise", "adventure"):
                result[record["entry_token"]] = {
                    "kind": f"{kind} {i}",
                    "hits": 0,
                    "produced_at": defaultdict(int),
                    "decrypted_at": defaultdict(int),
                }
            result[token] = {
                "kind": f"{kind} {i}",
                "query": record.get("query"),
                "formula": record.get("formula"),
                "hits": 0,
                "produced_at": defaultdict(int),
                "decrypted_at": defaultdict(int),
            }
        elif "entry_token" in record:
            token = record["entry_token"]
            result[token] = {
                "kind": f"{kind} {i}.{next(sub_counter)}",
                "hits": 0,
                "produced_at": defaultdict(int),
                "decrypted_at": defaultdict(int),
            }
    return result


def run(config: dict):
    db = database_factory(config)
    db.use(config["db_name"])

    log_path = Path(config["base_dir"], "logs.csv")
    format_sql = SQLFormatter(config)

    records = parse_notebook(config)
    report = init_report(records)

    ignored_tokens = set(Path(config["ignored_tokens_path"]).read_text().split())
    unknown_decrypted_tokens = set()
    timestamps_and_queries = parse_tsv(log_path)
    for (timestamp, query) in timestamps_and_queries:
        day = timestamp[:10]
        if m:= re.match(r"(?is)call decrypt.+?(\d+)\)", query):
            token = m[1]
            if token in ignored_tokens:
                continue
            if token not in report:
                report[token] = {
                    "kind": "unknown", # not produced by any query
                    "hits": 0,
                    "produced_at": defaultdict(int),
                    "decrypted_at": defaultdict(int),
                }
                unknown_decrypted_tokens.add(token)
            report[token]["decrypted_at"][day] += 1
            report[token]["hits"] += 1

    sql_errors = []
    no_token_errors = 0
    empty_result_errors = 0
    todo_count = 0
    for (timestamp, query) in timestamps_and_queries:
        day = timestamp[:10]
        if "salt_" in query:
            digest = md5(query.encode()).hexdigest()
            if digest in report:
                continue
            query = format_sql(query)
            query = query.replace("LIMIT 0, 25", "LIMIT 1")
            try:
                (headers, datatypes, rows) = db.execute_select(query)
            except Exception as e:
                sql_errors.append(re.sub(r"'\S+'", "'...'", e.__cause__.msg))
                continue
            if "token" not in headers:
                no_token_errors += 1
                continue
            if not rows:
                empty_result_errors += 1
                continue
            token = str(rows[0][headers.index("token")])
            if token in ignored_tokens:
                continue
            if token not in report:
                report[token] = {
                    "kind": "TODO",
                    "query": query,
                    "hits": 0,
                    "produced_at": defaultdict(int),
                    "decrypted_at": defaultdict(int),
                }
            if token in unknown_decrypted_tokens:
                print(f"\n{WARNING}Unknown token {token}{RESET}")
                query = query.replace("LIMIT 0, 1", "")
                query = f"%%sql\n-- Indication. TODO.\n{query}\n"
                print(query, flush=True)
                todo_count += 1
                unknown_decrypted_tokens.remove(token)
            else:
                print(f"{OK}.{RESET}", end="", flush=True)
            report[token]["produced_at"][day] += 1
            report[token]["hits"] += 1
    db.close()

    print(f"\n{todo_count} to do.")
    report["hits"] = dict(sorted(
        [(f"{token} ({v['kind']})", v['hits']) for (token, v) in report.items()],
        key=lambda x: x[1],
        reverse=True,
    ))
    report["sql_errors"] = dict(Counter(sorted(sql_errors)).most_common())
    report["no_token_errors"] = no_token_errors
    report["empty_result_errors"] = empty_result_errors
    report_path = Path(config["output_dir"], "report.json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
