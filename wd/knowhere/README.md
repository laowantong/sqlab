# Knowhere Black Market — SQL Adventure

A self-contained SQL adventure game using **DuckDB** and **Property Graph Queries (PGQ)**.
Play entirely in the browser — no local tooling required beyond Docker.

---

## Quick start

```bash
docker compose up --build
```

Then open **http://localhost:8080**.

The left panel shows the current mission. Write your SQL in the editor on the right and press **▶ Run Query** (or `Ctrl+Enter`). When your query produces a `token` column, the **Unlock Next ▶** button appears — click it to reveal the next challenge.

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with the Compose plugin (v2+)
- Port `8080` free on localhost

---

## Story

The Milano is stranded on **Knowhere**, a black market colony carved inside the skull of an ancient celestial. The engines are dead and a crucial stabilizer is missing. A Ravager mechanic named Rax gives you access to the broker registry. Navigate the trade network, trace the cheapest routes to rare ship parts, and escape.

---

## Challenges

| # | Title | Key concept |
|---|-------|-------------|
| 1 | The Brokers of Knowhere | Basic `SELECT` on a relational table |
| — | Knowledge Upgrade | `CREATE PROPERTY GRAPH` + `LOAD duckpgq` |
| 2 | Following the Trades | `GRAPH_TABLE` — list all edges |
| 3 | The Ion Thruster Lead | `GRAPH_TABLE` + `WHERE` + `ORDER BY` / `LIMIT` |
| 4 | The Middleman Problem | Two-hop path pattern `(a)-[]->(b)-[]->(c)` |
| 5 | The Flux Coil Trail | Neighbours of a specific vertex |
| 6 | The Cheapest Route | `ANY SHORTEST` path |

---

## How tokens work

Every challenge ends with a token column in the result.
The token is a salted hash computed over your query's output — if the answer is correct the token matches a pre-encrypted message, which becomes the next mission briefing.

Wrong answer → the token unlocks a generic "re-read the task" message instead.

---

## Sessions

Each browser tab gets its own **in-memory DuckDB** connection, initialised from `output/dump.sql`.
Tabs are fully isolated: DDL statements (e.g. `CREATE OR REPLACE PROPERTY GRAPH`) affect only your session.

Use **↺ New Session** in the header to reset your progress and start over.

---

## Hints and solutions

`solutions.md` contains direct-access tokens for each challenge and the reference solution queries.
