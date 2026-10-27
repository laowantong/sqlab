## High-Level Architecture

```
config.py           -> SQLab build configuration. Contains references to cnx.ini, ddl.sql, dataset, records.json and more.
records.json        -> defines the adventure (questions, solutions, rewards)
dataset/*.tsv       -> the raw data (one TSV per table)
ddl.sql             -> the database schema
cnx.ini

         ┌─────────────────────┐
         │    cmd_create.py    │  ← builds the database
         └─────────────────────┘
                  │
         ┌────────▼────────────┐
         │  PostgreSQL DB      │
         │  ┌───────────────┐  │
         │  │ core tables   │  │  ← actor, address, film, etc. (each row has a `hash` column)
         │  │ sqlab_msg     │  │  ← encrypted messages, keyed by token
         │  │ sqlab_metadata│  │  ← metadata about the adventure
         │  │ salt_NNN()    │  │  ← 100 secret salt functions
         │  │ string_hash() │  │  ← 40-bit SHA-256 digest
         │  │ decrypt()     │  │  ← player-facing function
         │  └───────────────┘  │
         └─────────────────────┘
                  │
         ┌────────▼────────────┐
         │    cmd_shell.py     │  ← interactive SQL shell for playing
         └─────────────────────┘
```

### The `hash` Column

Every core table row has a `hash` column computed by a trigger on INSERT/UPDATE or during creation of the adventure (depending on the database). 
Some tables don't have trigger. Trigger are also useful if the adventure contains some inserts during the game.

## How the Token System Works

The player writes a SQL query that selects specific rows. The token formula is embedded as a column in the SELECT:

The sql depends on the database. This is postgresql:
```sql
SELECT first_name, last_name,
    salt_042(string_hash('secret') + sum(hash) OVER ()) AS token
FROM actor A
WHERE ...
```

for duckdb the example is:

```sql
SELECT first_name, last_name,
    salt_042(sum(nn(table.hash)) OVER ()) AS token
FROM actor A
WHERE ...
```

If the player selects the **right rows**, they get the **right token**. They pass it to `decrypt()`:

```sql
SELECT decrypt(175621843949664);
```

Which returns the next message (reward + next question).

This is the mechanism to verify the sql query was correct without parsing the provided sql query e.g. the query is correct if the result set is the same. Btw just comparing the result set with known good would be more expensive and hard (column order) and cheating is harder (e.g. limit 1 is not possible).

Python encrypt(...) Function encrypts adventure content for the database (no clear text visible). The decrypt(..) function decrypts the text if token matches exactly.

For DuckDb The encrypted text is a concatenated string of token-hash + base64(msg). The decrypt is easy e.g hash input token, and compare with first 64 chars in chiphertext.


## How to Implement an Adventure (`records.json`)

The adventure is defined as a JSON object. Each key is a **token** (the entry point for that message), and the value is a **record**.

### Special record: `db_metadata`

```json
"db_metadata": {
    "kind": "db_metadata",
    "title": "Payroll Investigation Adventure",
    "pitch": "Someone tampered with the 2023 bonuses..."
}
```

Stored in `sqlab_metadata`. Purely descriptive - title and pitch shown to the player at the start.

### Record kind: `episode`

An episode is one step in a **linear adventure**. The player must solve each episode in sequence.

```json
"042": {
    "kind": "episode",
    "activity_number": 1,
    "task_number": 1,
    "salt": "042",
    "section": "## Act I - The Scene",
    "context": "## Welcome, Detective!\n\nA whistleblower claims...",
    "statement": "List all departments with their budget, ordered by budget descending.",
    "reward": "Good start! Engineering has the fattest budget.",
    "formula": "salt_042(string_hash('secret') + sum(hash) OVER ()) as token",
    "solutions": [
        {
            "token": "175621843949664",
            "query": "SELECT ...",
            "intro": "my intro 1",
            "columns": ["dept_name", "budget", "token"]
        }
    ]
}
```

| Property | Meaning |
|---|---|
| `kind` | `"episode"` for adventure steps, `"exercise"` for standalone tasks |
| `activity_number` | Groups episodes into activities (used for table of contents) |
| `task_number` | Sequential number within the activity |
| `salt` | Three-digit string - which `salt_NNN()` function to use in the formula |
| `section` | Markdown heading injected into `cheat_sheet.md` and `storyline.md` |
| `context` | Markdown narrative shown to the player when they arrive at this episode |
| `statement` | The SQL task the player must solve |
| `reward` | Short text shown after solving - bridges to the next episode |
| `formula` | The SQL expression the player must include in their SELECT to compute the token |
| `solutions[].token` | The token produced by the correct query - this is the **key** of the next episode |
| `solutions[].query` | The reference solution (stored in `cheat_sheet.md` and `check_list.json`) |
| `solutions[].intro` | Optional annotation before the solution in the cheat sheet |
| `solutions[].columns` | Expected column names in the result (used by automated checker) |

**The last episode** has an empty `solutions: []` - no formula, no next token. It is the epilogue.

### Record kind: `exercise`

Same structure as `episode`, but standalone - each exercise is an independent entry point, not part of a chain.



### Record kind: `hint`

A hint is a partial query that produces a token that loops back to the same task (source == target in the token table). The player gets a nudge without advancing.



## How to Play (using `cmd_shell.py`)

Start the shell:
```bash
python -m sqlab shell sakila-adventure/
```

The shell is an interactive SQL REPL with two special behaviors:

**1. Type just a number → calls `decrypt()`**
```
>>> 42
```
Outputs the context + statement for episode 42 (the starting token).

**2. Run a SELECT with a `token` column → auto-decrypts**
```sql
>>> SELECT first_name, last_name,
...     salt_042(string_hash('secret') + sum(hash) OVER ()) AS token
...     FROM actor A WHERE ...;
```
The shell prints the result table, then automatically calls `decrypt(token)` on the first row's token value, showing the reward and next question if the answer is correct, or the default "wrong answer" message if not.



## Output Files Produced by `cmd_create.py`

| File | Content |
|-|-|
| `output/dump.sql` | Full SQL to recreate the database from scratch |
| `output/cheat_sheet.md` | All questions + reference solutions in Markdown |
| `output/storyline.md` | Narrative only (context + collapsed statements), no solutions |
| `output/token_table.tsv` | Mapping of every token to its activity/source/target/action/salt |
| `output/check_list.json` | Machine-readable list of all queries + expected tokens (for automated testing) |
| `output/msg.log` | Log of all messages generated during build |

### `token_table.tsv` columns

| Column | Meaning |
|-|-|
| `token` | The numeric token |
| `activity` | Activity number (0 = exercise, 1+ = adventure) |
| `source` | Episode number that **produces** this token |
| `target` | Episode number this token **leads to** |
| `action` | `enter` (first episode), `move` (advance), `hint` (loop), `move` (exit on last) |
| `salt` | Which `salt_NNN` was used |

### `check_list.json` fields

Each entry represents one solution query:

| Field | Meaning |
|-|-|
| `id` | `"activity-task-counter"` e.g. `"1-2-0"` |
| `query` | Cleaned SQL (hash lines stripped) |
| `formula` | Token formula to inject |
| `columns` | Expected column names |
| `tweak` | Optional JavaScript transformation for web UI |
| `kind` | `"solution"` or `"hint"` |
| `token` | Expected output token |


## `config.py` - The Adventure Configuration

Each adventure has its own `config.py` that overrides the global defaults from `sqlab/config.py`. It is a plain Python file that exposes a `config` dict.

```python
config = {
    "dbms": "postgresql",       # which DBMS to use
    "cnx_path": "./cnx.ini",    # connection credentials (host, port, user, database)
    "language": "en",           # selects strings_en or strings_fr from global defaults
    "ddl_path": "./ddl.sql",    # schema definition
    "dataset_dir": "./dataset", # folder of *.tsv files
    "relational_schema_dir": "./relational_schema",  # optional SVG diagrams
    "source_path": "./records.json",  # the adventure definition
    "markdown_to": "txt",       # output format: "txt", "web", or "json"
    "metadata": {},             # extra key/value pairs stored in sqlab_metadata
    "field_subs": { ... },      # custom TSV cell converters (see below)
    "strings": { ... },         # override any UI strings
}
```

### `field_subs` - Custom TSV Cell Converters

TSV files store everything as strings. For columns with non-trivial SQL types, you provide a Python function that converts the raw cell string into a valid SQL literal:

```python
def _fulltext(cell):
    escaped = cell.replace("'", "''")
    return f"'{escaped}'::tsvector"   # produces: 'word1 word2'::tsvector

def _special_features(cell):
    # Input: {"Deleted Scenes","Behind the Scenes"}
    # Output: ARRAY['Deleted Scenes', 'Behind the Scenes']
    items = [i.strip().strip('"') for i in cell.strip('{}').split(',')]
    quoted = ', '.join(f"'{item}'" for item in items)
    return f"ARRAY[{quoted}]"

def _timestamp(cell):
    return f"'{cell}'::timestamp" if cell and cell != r'\N' else 'NULL'

config = {
    ...
    "field_subs": {
        "fulltext": _fulltext,           # applied to the `fulltext` column in film.tsv
        "special_features": _special_features,
        "rental_date": _timestamp,
        "last_update": _timestamp,
    },
}
```

The key is the **column name** matching the DDL. The value is a callable `(cell: str) -> str` returning a SQL literal. This is how `tsvector`, PostgreSQL arrays, and timestamps are handled without touching the generic TSV ingestion logic in `compose_inserts.py`.

### `strings` - UI Text Overrides

The global defaults define all UI strings in English and French. `config.py` can override any of them:

```python
"strings": {
    "preamble_default": "❌ Wrong answer. Re-read the task carefully and try again.",
    "preamble_accepted": "✅ Correct! Token: {token}",
    "preamble_rejected": "🟠 Not quite.",
}
```

These strings are injected into the encrypted messages stored in `sqlab_msg`, so they appear when the player calls `decrypt(token)`. The `{token}` placeholder is replaced at message-building time.


## Additional `config.py` Settings

Beyond what sakila-adventure uses, the global `sqlab/config.py` exposes these overridable settings:

| Key | Default | Meaning |
|-|-|-|
| `salt_seed` | `42` | Random seed for generating the 100 salt functions. Change it to produce a different set of secret constants - effectively a new "key" for the whole database. |
| `salt_bound` | `100` | How many `salt_NNN()` functions to generate (salt_001 … salt_100). Must be ≥ the highest salt number used in `records.json`. |
| `column_width` | `100` | Line wrap width for text stored in `sqlab_msg`. |
| `reformat_sql` | `True` | Whether to auto-format SQL queries parsed from notebooks via `sqlparse`. |
| `sqlparse_kwargs` | `{...}` | Arguments passed to `sqlparse.format()`: keyword case, indentation, etc. |
| `sqlparse_subs` | `{...}` | Regex post-processing rules applied after sqlparse formatting (e.g. fix CROSS JOIN indents, align comma-first fields). |
| `empty_cells` | `[""]` | TSV cell values treated as empty string `''` in SQL. |
| `null_cells` | `["NULL", "\\N", "None"]` | TSV cell values treated as `NULL` in SQL. |
| `metadata` | `{}` | Extra key/value pairs inserted into `sqlab_metadata` (e.g. author, version, URL). |


## Step-by-Step: Creating a New Adventure

1. **Prepare your database schema** in `ddl.sql` with a `-- FK` comment separating FK constraints from table definitions.

2. **Populate `dataset/*.tsv`** - one file per table, tab-separated, first row is data (no header), No primary keys

Why TSV needed:
* SQLab loads TSV e.g. become tables per ddl.sql schema
* Computes hash columns from row content
* Enables deterministic token verification


3. **Write `records.json`**:
   - Start with `db_metadata`
   - Add episode `"042"` as the entry point (`task_number: 1`)
   - For each episode, run the reference solution query against the database, note the token it produces, use that token as the key for the next episode
   - Leave `solutions: []` on the final episode

4. **Run `cmd_create`**:
   ```bash
   python -m sqlab create sakila-adventure/
   ```

5. **Play with `cmd_shell`**:
   ```bash
   python -m sqlab shell sakila-adventure/
   >>> 42
   ```

## DRAFT: The Jupyter Notebook Workflow

Instead of writing `records.json` by hand, you can author the adventure in a **Jupyter notebook** and let SQLab parse it automatically. This is the preferred workflow for larger adventures because:

- You can run each SQL query interactively and see its output
- The token is extracted automatically from the query output (no need to copy-paste it into `records.json`)
- SQL queries are auto-formatted via `sqlparse`
- An **activity map** (GraphViz diagram) is generated showing the adventure graph

### How it Works

When `source_path` points to a `.ipynb` file, `cmd_create` does the following:

1. Runs the notebook top-to-bottom via `nbconvert` (`run_notebook.py`)
2. Parses the executed notebook cells into `records` (`cmd_parse.py`) - equivalent to `records.json`
3. Writes the parsed records to `output/records.json` for inspection
4. Continues with the normal database creation flow

### Notebook Cell Conventions

The parser reads two types of cells:

#### Markdown cells - define structure and tasks

A markdown cell starting with `**Label [salt].** text` defines a task:

```markdown
**Episode [042].** Welcome, Detective! A whistleblower claims bonuses were unfairly withheld...
```

```markdown
**Statement.** List all departments with their budget, ordered by budget descending.
```

```markdown
**Annotation.** This solution uses a self-join to handle the hierarchy.
```

Headings (`#`, `##`, `###`) define the `section_path` - the structural hierarchy stored in the record and used to generate the TOC for the web interface.

The supported labels (in English) are:
- `Episode [NNN]` - one step in an adventure; `NNN` is the 3-digit salt number
- `Exercise [NNN]` - standalone task
- `Statement` - the task text (attached to the previous episode/exercise)
- `Hint` - partial solution that loops back (does not advance)
- `Annotation` - free-text note inserted between solutions in the cheat sheet

#### Code cells - define solutions

A code cell starting with `%%sql` is a solution query. The parser:

1. Strips the `%%sql` magic header
2. Reads an optional leading comment for the label and intro text:
   ```sql
   %%sql
   -- Solution. Using a correlated subquery instead of a join.
   SELECT first_name, last_name,
       salt_042(string_hash('secret') + sum(hash) OVER ()) AS token
   FROM actor A
   WHERE ...
   ```
3. Separates the `salt_NNN(...)  AS token` formula from the rest of the query
4. **Extracts the token from the cell output** - it looks for `<th>token</th>` in the HTML table output and reads the first value. This is how the token is discovered automatically.
5. Reads an optional `-->  [NNN]` redirect comment at the end to specify which episode the query leads to (the `next_salt`)

#### Tweak cells - for parameterized formulas

Some formulas need a **control value** from the result to disambiguate (e.g. the first value of a column). These use a Python assignment cell followed by a `{{x}}` placeholder in the formula:

```python
x = 3  # the number of rows in the first group
```

```sql
%%sql
SELECT dept, count(*),
    salt_050({{x}} + bit_xor(sum(nn(A.hash))) OVER ()) AS token
FROM ...
GROUP BY dept
```

The parser stores the tweak description (the comment after `#`) in `record["tweak"]`. In the built database, the formula shown to players contains `(0)` as a placeholder, which they must replace with the actual control value from their result.

#### Stop cell

```python
raise EOFError
```

Any cell starting with `raise EOFError` causes the parser to stop reading - everything after it is ignored. Useful for keeping work-in-progress or scratch cells at the end of the notebook.

#### Action cells

```sql
%%sql
-- Action. Reset the bonus column.
UPDATE employee SET bonus = NULL;
```

A `%%sql` cell with the label `Action` is executed (to set up DB state) but not recorded as a solution.

### The Activity Map

After parsing, `dump_graph()` generates a GraphViz `.gv` file and (if graphviz is installed) renders it to PDF and SVG. The graph shows:

- **Green nodes** - entry points (first episode of each adventure, or each exercise)
- **Orange nodes** - intermediate episodes
- **Large nodes** - epilogues (last episode, no formula)
- **Star nodes** - solution tokens (exit points)
- **Small nodes with dashed edges** - hints (loops)

### Running the Notebook Workflow

```bash
# Author in Jupyter:
jupyter notebook sakila-adventure/adventure.ipynb

# Build the database (runs + parses the notebook):
python -m sqlab create sakila-adventure/

# Play:
python -m sqlab shell sakila-adventure/
```

If `records.json` is newer than the notebook, SQLab asks whether to re-run the notebook - useful when iterating on the adventure without re-executing all queries.

### Web Mode

Running with `--web` changes the output format:

```bash
python -m sqlab create sakila-adventure/ --web
```

This produces a `dump_web.sql` where all messages in `sqlab_msg` are stored as **JSON** instead of plain text. The JSON contains structured HTML fields (`question`, `feedback`, `category`) consumed by a web frontend. The `reward` field is used here - it appears in the activity TOC as a short summary of what the player discovered. The web mode also includes the full `compile_activities()` output (table of contents, section structure, column names, formula, etc.) stored in `sqlab_metadata`.

## How to Structure a Jupyter Notebook Adventure

Here is a complete annotated example of how a notebook adventure should be structured, cell by cell:

### 1. Setup cells (not parsed)

```python
# Cell 1 - connection setup, not parsed by SQLab
from sqlab.nb_tools import may_create_connection_file, get_engine
may_create_connection_file()
engine = get_engine()

%reload_ext sql
%sql engine
```

These Python cells run normally but are ignored by the parser (no `%%sql` magic, no `**Label.**` markdown).



### 2. Top-level heading - becomes `db_metadata`

```markdown
# Payroll Investigation

Someone tampered with the 2023 bonuses. Use SQL to find the truth.
```

The `#` heading title becomes `db_metadata.title`, the subtitle becomes `db_metadata.pitch`.



### 3. Section headings - become `section_path`

```markdown
## Act I – The Scene

In which we establish the lay of the land.
```

```markdown
### The Departments
```

Headings `##` and `###` define the hierarchy stored in `section_path`. These are used in the web TOC and activity map. The subtitle (second line of the cell) is only stored the first time a section is encountered.



### 4. An episode - markdown cell

```markdown
**Episode [042].** Welcome, Detective!

A whistleblower claims bonuses were unfairly withheld in 2023.
Your job is to follow the money using SQL.
```

Format: `**Label [salt].** first line` followed by optional additional lines. Everything after the first line is part of the `context` (the narrative shown to the player). The salt `042` links this episode to `salt_042()`.



### 5. The statement - separate markdown cell

```markdown
**Statement.** List all departments with their budget, ordered by budget descending.
```

Must follow an episode or exercise cell. Becomes `record["statement"]`.



### 6. The solution - code cell

```sql
%%sql
SELECT dept_name
     , budget
     , salt_042(string_hash('secret') + sum(hash) OVER ()) AS token
FROM department A
ORDER BY budget DESC;
```

The parser:
- Strips `%%sql`
- Extracts `salt_042(... ) AS token` as the formula
- Runs the cell and reads the `token` value from the HTML output automatically
- Stores the query (minus the token formula line) as the reference solution

An optional leading comment adds an intro label:
```sql
%%sql
-- Solution. Using a window function approach.
SELECT ...
```



### 7. A variant solution (optional)

```sql
%%sql
-- Variant. Using a subquery instead.
SELECT dept_name
     , (SELECT budget FROM budget_table B WHERE B.dept_id = A.dept_id)
     , salt_042(string_hash('secret') + sum(hash) OVER ()) AS token
FROM department A
ORDER BY budget DESC;
```

Multiple `%%sql` cells after the same episode/statement are treated as variants. They all produce the same token (same correct result set) or a different token if the result differs.



### 8. Redirect to next episode - `-->` comment

If the next episode's salt cannot be inferred automatically, add a redirect:

```sql
%%sql
SELECT ...
    salt_042(...) AS token
FROM ...;
--> [017]
```

The `-->  [017]` at the end tells the parser that this solution leads to the episode with salt `017`.



### 9. A parameterized formula (tweak)

Some formulas need a control value from the player's own result. First define it in a Python cell:

```python
x = 3  # the number of departments with budget > 100k
```

The comment after `#` becomes the tweak instruction shown to the player. Then use `{{x}}` in the formula:

```sql
%%sql
SELECT dept_name, count(*) AS employees,
     , salt_050({{x}} + bit_xor(sum(nn(A.hash))) OVER ()) AS token
FROM department A
JOIN employee B ON A.dept_id = B.dept_id
GROUP BY dept_name
HAVING count(*) > 5;
```

In the built database, `{{x}}` is replaced with `(0)` - players must substitute the actual value they see in their first result column.



### 10. A hint - markdown + code pair

```markdown
**Hint.** Remember that budget is stored in thousands.
```

```sql
%%sql
-- A partial query that produces a hint token
SELECT dept_name, budget / 1000 AS budget_k
     , salt_042(string_hash('hint') + sum(hash) OVER ()) AS token
FROM department A;
```

Hints loop back to the same episode (source == target in the token table). The player gets the hint text but does not advance.



### 11. An annotation - between solutions

```markdown
**Annotation.** Both queries above are correct; the subquery variant is less efficient on large datasets.
```

Inserted between solution cells. Appears as a note in the cheat sheet.



### 12. Stop marker

```python
raise EOFError
```

Everything after this cell is ignored by the parser. Use it to keep scratch queries or WIP episodes at the bottom of the notebook.



### 13. Action cells - DB state setup

```sql
%%sql
-- Action. Insert test bonus data.
INSERT INTO bonus (emp_id, amount) VALUES (1, 5000);
```

Executed normally during notebook run but not recorded as a solution.



### Complete episode sequence summary

```
## Section heading         ← section_path
### Subsection             ← section_path

**Episode [NNN].**         ← context (narrative)
**Statement.**             ← task
%%sql (solution)           ← formula + token auto-extracted
%%sql (variant, optional)
**Annotation.** (optional)

**Episode [MMM].**         ← next episode...
```

Each adventure ends with a final episode that has **no** `%%sql` solution cell - this is the epilogue. It has no formula, no token, and its `solutions` list is empty.

## Configuration Files

The documentation is not yet complete. In the meantime, you may explore the repository of [SQLab Island](https://github.com/laowantong/sqlab_island). The provided dataset and Jupyter notebooks serve as source material for the generation of the SQLab database.
