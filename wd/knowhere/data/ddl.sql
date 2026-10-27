-- 1. Create the tables with the new hash columns required by SQLab
CREATE TABLE broker (
    id INT, 
    name VARCHAR, 
    part VARCHAR,
    extra_part_1 VARCHAR,
    extra_part_2 VARCHAR,
    hash BIGINT DEFAULT 0
);

CREATE TABLE trade (
    source_id INT, 
    target_id INT, 
    cost INT,
    hash BIGINT DEFAULT 0
);

-- 2. Create the Property Graph
CREATE PROPERTY GRAPH trade_graph
VERTEX TABLES (
    broker LABEL Broker
)
EDGE TABLES (
    trade SOURCE KEY (source_id) REFERENCES broker(id)
          DESTINATION KEY (target_id) REFERENCES broker(id)
          LABEL TRADES_WITH
);
