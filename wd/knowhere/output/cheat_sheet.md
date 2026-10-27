# Cheat sheet

## Adventure

### Episode 1

**Token.** 42.

List all brokers and the parts they currently possess.

**Formula**. `salt_042(sum(nn(b.hash)) OVER ()) AS token`

Rax was right: the registry shows exactly who holds what.

```sql
SELECT b.name, b.part, salt_042(sum(nn(b.hash)) OVER ()) AS token
FROM broker b;
```

### Episode 1.5

**Token.** 900723996.

View the trade network by listing all direct broker connections in the graph.

**Formula**. `salt_012(sum(nn(t.hash)) OVER ()) AS token`

With the graph confirmed live, the market stops looking like chaos and starts looking like a network.

```sql
SELECT from_broker, to_broker, salt_012(sum(nn(t_hash)) OVER ()) AS token
FROM GRAPH_TABLE (
  trade_graph
  MATCH (a:Broker)-[t:TRADES_WITH]->(b:Broker)
  COLUMNS (
    a.name AS from_broker,
    b.name AS to_broker,
    t.hash AS t_hash
  )
);
```

### Episode 2

**Token.** 862855806.

List all broker-to-broker trades and include the cost of each trade.

**Formula**. `salt_078(sum(nn(a.hash)) OVER ()) AS token`

Now you can see not just who trades with whom, but how expensive every deal is.

```sql
SELECT from_broker, to_broker, cost, salt_078(sum(nn(hash) + cost) OVER ()) AS token
FROM GRAPH_TABLE (
  trade_graph
  MATCH (a:Broker)-[t:TRADES_WITH]->(b:Broker)
  COLUMNS (
    a.name AS from_broker,
    b.name AS to_broker,
    t.cost AS cost,
    a.hash
  )
);
```

### Episode 3

**Token.** 72003022.

Find the cheapest direct trade leading to a broker who has the Ion Thruster.

**Formula**. `salt_010(sum(nn(a.hash)) OVER ()) AS token`

That is the cheapest direct route to the Ion Thruster supplier.

```sql
SELECT seller, supplier, cost, seller_hash, supplier_hash, salt_010((nn(seller_hash) + nn(supplier_hash))/2) AS token
FROM GRAPH_TABLE (
  trade_graph
  MATCH (a:Broker)-[t:TRADES_WITH]->(b:Broker)
  WHERE b.part = 'Ion Thruster'
  COLUMNS (
    a.name AS seller,
    b.name AS supplier,
    t.cost AS cost,
    a.hash AS seller_hash,
    b.hash AS supplier_hash
  )
)
ORDER BY cost
LIMIT 1;
```

### Episode 4

**Token.** 256156672.

Find two-step trade routes that lead to a broker holding the Plasma Regulator.

**Formula**. `salt_080(sum(nn(a.hash)) OVER ()) AS token`

Two-step routes reveal the hidden bargains buried inside the market chain.

```sql
SELECT start, middleman, supplier, total_cost, salt_080(sum(nn(a_hash) + nn(b_hash) + nn(c_hash)) OVER ()) AS token
FROM GRAPH_TABLE (
  trade_graph
  MATCH (a:Broker)-[t1:TRADES_WITH]->(b:Broker)-[t2:TRADES_WITH]->(c:Broker)
  WHERE c.part = 'Plasma Regulator'
  COLUMNS (
    a.name AS start,
    b.name AS middleman,
    c.name AS supplier,
    t1.cost + t2.cost AS total_cost,
    a.hash AS a_hash,
    b.hash AS b_hash,
    c.hash AS c_hash
  )
)
ORDER BY total_cost;
```

### Episode 5

**Token.** 720293142.

Find brokers connected to the broker holding the Quantum Flux Coil.

**Formula**. `salt_023(sum(nn(a.hash)) OVER ()) AS token`

These brokers are directly connected to the current Quantum Flux Coil holder.

```sql
SELECT broker, coil_holder, salt_023(sum(nn(a_hash)) OVER ()) AS token
FROM GRAPH_TABLE (
  trade_graph
  MATCH (a:Broker)-[t:TRADES_WITH]->(b:Broker)
  WHERE b.part = 'Quantum Flux Coil'
  COLUMNS (
    a.name AS broker,
    b.name AS coil_holder,
    a.hash AS a_hash
  )
);
```

### Episode 6

**Token.** 773309375.

Find the cheapest trade route of any length leading to a broker holding the Ion Thruster.

**Formula**. `salt_045(sum(nn(start_hash)) OVER ()) AS token`

The market finally gives up its secret: sometimes the cheapest route is direct, and sometimes it takes a few carefully chosen trades.

```sql
SELECT start, destination, total_cost, salt_045(sum(nn(start_hash)) OVER ()) AS token
FROM (
  WITH RECURSIVE paths(start_id, current_id, total_cost, visited) AS (
    SELECT b.id, b.id, 0, [b.id]
    FROM broker b
    UNION ALL
    SELECT paths.start_id, t.target_id, paths.total_cost + t.cost, array_append(paths.visited, t.target_id)
    FROM paths
    JOIN trade t ON t.source_id = paths.current_id
    WHERE list_position(paths.visited, t.target_id) IS NULL
  )
  SELECT
    b_start.name AS start,
    b_end.name AS destination,
    b_start.hash AS start_hash,
    p.total_cost
  FROM paths p
  JOIN broker b_start ON b_start.id = p.start_id
  JOIN broker b_end ON b_end.id = p.current_id
  WHERE b_end.part = 'Ion Thruster'
    AND p.start_id != p.current_id
  ORDER BY total_cost
  LIMIT 1
);
```

### Episode 7

**Token.** 229297520.

Find the shortest ancestral path from Groot to the elder whose title is 'Keeper of Coordinates', and return how many generations away that elder is.

**Formula**. `salt_046(sum(nn(_hash)) OVER ()) AS token`

The living memory surfaces: a lineage path traced root by root until the elder who knows the way.

```sql
SELECT seeker, elder, safe_world_source, generations_apart, salt_046(sum(nn(_hash)) OVER ()) AS token
FROM GRAPH_TABLE (
    groot_lineage_graph
    MATCH p = ANY SHORTEST
        (g:Colossus WHERE g.name = 'Groot')
        -[d:DESCENDS_FROM]->*
        (e:Colossus WHERE e.title = 'Keeper of Coordinates')
    COLUMNS (
        g.name AS seeker,
        e.name AS elder,
        e.world AS safe_world_source,
        path_length(p) AS generations_apart,
        e.hash AS _hash
    )
);
```

### Episode 8

**Token.** 365802695.

Find the shortest trade path from Kraglin to the broker holding the Ion Thruster, avoiding all compromised brokers along the way.

**Formula**. `salt_086(sum(nn(_hash)) OVER ()) AS token`

The Sovereign can't intercept what they can't see. The safe path surfaces.

```sql
CREATE OR REPLACE TABLE safe_trade AS
SELECT t.*
FROM trade t
JOIN broker b1 ON t.source_id = b1.id
JOIN broker b2 ON t.target_id = b2.id
WHERE b1.compromised = 0
  AND b2.compromised = 0;

CREATE OR REPLACE PROPERTY GRAPH safe_trade_graph
VERTEX TABLES (
    broker LABEL Broker
)
EDGE TABLES (
    safe_trade
      SOURCE KEY (source_id) REFERENCES broker (id)
      DESTINATION KEY (target_id) REFERENCES broker (id)
      LABEL TRADES_WITH
);

SELECT start, destination, hops, salt_086(sum(nn(_hash)) OVER ()) AS token
FROM GRAPH_TABLE (
    safe_trade_graph
    MATCH p = ANY SHORTEST
        (a:Broker WHERE a.name = 'Kraglin')
        -[t:TRADES_WITH]->*
        (b:Broker WHERE b.part = 'Ion Thruster')
    COLUMNS (
        a.name AS start,
        b.name AS destination,
        path_length(p) AS hops,
        b.hash AS _hash
    )
);
```

### Episode 9

**Token.** 483130130.


