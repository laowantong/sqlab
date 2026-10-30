CREATE TABLE broker (
    id INT,
    name VARCHAR,
    part VARCHAR,
    extra_part_1 VARCHAR,
    extra_part_2 VARCHAR,
    compromised INT DEFAULT 0,
    hash BIGINT DEFAULT 0
);

CREATE TABLE flora_colossus (
    id BIGINT PRIMARY KEY,
    name VARCHAR,
    title VARCHAR,
    world VARCHAR,
    hash BIGINT DEFAULT 0
);

CREATE TABLE lineage (
    descendant_id BIGINT,
    ancestor_id BIGINT,
    relation VARCHAR,
    hash BIGINT DEFAULT 0
);

CREATE PROPERTY GRAPH groot_lineage_graph
VERTEX TABLES (
    flora_colossus LABEL Colossus
)
EDGE TABLES (
    lineage
      SOURCE KEY (descendant_id) REFERENCES flora_colossus (id)
      DESTINATION KEY (ancestor_id) REFERENCES flora_colossus (id)
      LABEL DESCENDS_FROM
);

CREATE TABLE trade (
    source_id INT, 
    target_id INT, 
    cost INT,
    hash BIGINT DEFAULT 0
);

CREATE PROPERTY GRAPH trade_graph
VERTEX TABLES (
    broker LABEL Broker
)
EDGE TABLES (
    trade SOURCE KEY (source_id) REFERENCES broker(id)
          DESTINATION KEY (target_id) REFERENCES broker(id)
          LABEL TRADES_WITH
);
