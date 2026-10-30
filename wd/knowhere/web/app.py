import json
import uuid
from pathlib import Path

import duckdb
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

DUMP_SQL = Path("/app/dump.sql").read_text()

# Map entry-token (str) -> hint text, loaded from records.json if available
_records_path = Path("/app/records.json")
HINTS: dict[str, str] = {}
if _records_path.exists():
    for key, val in json.loads(_records_path.read_text()).items():
        if isinstance(val, dict) and "hint" in val:
            HINTS[str(key)] = val["hint"]

# session_id -> duckdb.DuckDBPyConnection
sessions: dict[str, duckdb.DuckDBPyConnection] = {}


def split_statements(sql: str) -> list[str]:
    """Split SQL into individual statements on ';', respecting single-quoted strings."""
    statements = []
    current: list[str] = []
    in_single_quote = False
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'" and not in_single_quote:
            in_single_quote = True
            current.append(c)
        elif c == "'" and in_single_quote:
            # '' is an escaped single quote inside a string
            if i + 1 < len(sql) and sql[i + 1] == "'":
                current.append("''")
                i += 2
                continue
            else:
                in_single_quote = False
                current.append(c)
        elif c == ";" and not in_single_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(c)
        i += 1
    # Handle trailing statement without semicolon
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements


def _load_duckpgq(conn: duckdb.DuckDBPyConnection) -> None:
    """Install and load duckpgq, trying multiple sources in order."""
    # 1. Already installed in the cached extensions volume
    try:
        conn.execute("LOAD duckpgq")
        return
    except duckdb.Error:
        pass
    # 2. DuckDB community extension repository
    try:
        conn.execute("INSTALL duckpgq FROM community")
        conn.execute("LOAD duckpgq")
        return
    except duckdb.Error:
        pass
    # 3. sqlab project's S3 mirror (primary source used by the sqlab toolchain)
    try:
        conn.execute("SET custom_extension_repository = 'http://duckpgq.s3.eu-north-1.amazonaws.com'")
        conn.execute("FORCE INSTALL duckpgq")
        conn.execute("LOAD duckpgq")
    except duckdb.Error:
        pass  # GRAPH_TABLE queries will surface a clear SQL error if this fails


def _update_hashes(conn: duckdb.DuckDBPyConnection) -> None:
    """Recompute row hashes for all user tables that have a `hash` column.

    The dump.sql inserts rows with hash=0 (the DEFAULT). This reproduces the
    logic from sqlab's Database._update_hashes so that token formulas work.
    """
    conn.execute(
        "SELECT DISTINCT table_name FROM information_schema.columns "
        "WHERE column_name = 'hash' AND table_schema = 'main'"
    )
    tables = [r[0] for r in conn.fetchall() if not r[0].startswith("sqlab_")]
    for table in tables:
        conn.execute(
            "SELECT column_name FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND column_name != 'hash' "
            "AND table_schema = 'main' ORDER BY ordinal_position"
        )
        data_headers = [r[0] for r in conn.fetchall()]
        if not data_headers:
            continue
        col_list = ", ".join(
            f"COALESCE(CAST({h} AS VARCHAR), 'NULL')" for h in data_headers
        )
        concat_expr = f"CONCAT('table:', '{table}', '|', {col_list})"
        conn.execute(
            f"UPDATE {table} SET hash = string_hash({concat_expr}) "
            f"WHERE COALESCE({table}.hash, 0) = 0"
        )


def init_connection() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(":memory:", config={"allow_unsigned_extensions": True})
    # Load duckpgq (required for CREATE PROPERTY GRAPH).
    # Try in order: already installed → community repo → sqlab's S3 mirror.
    # The extension is cached in the named volume so the download only happens once.
    _load_duckpgq(conn)
    for stmt in split_statements(DUMP_SQL):
        try:
            conn.execute(stmt)
        except duckdb.Error:
            pass  # skip individual statement errors (e.g. idempotency issues)
    # Recompute row hashes (dump.sql stores hash=0; tokens depend on real hashes)
    _update_hashes(conn)
    return conn


def get_or_create_session(sid: str | None) -> tuple[str, duckdb.DuckDBPyConnection]:
    if sid and sid in sessions:
        return sid, sessions[sid]
    new_id = str(uuid.uuid4())
    sessions[new_id] = init_connection()
    return new_id, sessions[new_id]


@app.get("/api/session")
def new_session():
    sid, _ = get_or_create_session(None)
    return {"session_id": sid}


@app.post("/api/query")
async def run_query(request: Request):
    body = await request.json()
    sql = body.get("sql", "").strip()
    sid = body.get("session_id")

    sid, conn = get_or_create_session(sid)

    if not sql:
        return {"columns": [], "rows": [], "session_id": sid}

    try:
        stmts = [s for s in split_statements(sql) if s.strip()]
        if not stmts:
            return {"columns": [], "rows": [], "session_id": sid}

        # Execute all but the last silently, then execute the last and return results
        for stmt in stmts[:-1]:
            conn.execute(stmt)

        conn.execute(stmts[-1])

        if conn.description:
            columns = [d[0] for d in conn.description]
            rows = conn.fetchall()
            serialized = [
                [str(cell) if cell is not None else None for cell in row]
                for row in rows
            ]
            return {"columns": columns, "rows": serialized, "session_id": sid}
        else:
            return {"columns": [], "rows": [], "session_id": sid}

    except duckdb.Error as e:
        return JSONResponse(
            status_code=200,
            content={"error": str(e), "session_id": sid},
        )


@app.get("/api/decrypt/{token}")
def decrypt_token(token: str, session_id: str | None = None):
    sid, conn = get_or_create_session(session_id)
    try:
        # Validate token is a safe integer-like value
        int(token)
        row = conn.execute(f"SELECT msg FROM decrypt({token})").fetchone()
        if row is None:
            return {"message": "No message found.", "session_id": sid}
        msg = row[0]
        if isinstance(msg, (bytes, bytearray)):
            msg = msg.decode("utf-8")
        else:
            msg = str(msg)
        hint = HINTS.get(str(token), "")
        return {"message": msg, "hint": hint, "session_id": sid}
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Token must be an integer."})
    except duckdb.Error as e:
        return JSONResponse(status_code=200, content={"error": str(e), "session_id": sid})


@app.get("/")
def index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
