-- Supplementary tables created by SQLab.

DROP TABLE IF EXISTS sqlab_msg;
CREATE TABLE sqlab_msg (
  msg TEXT NOT NULL
);

DROP TABLE IF EXISTS sqlab_metadata;
CREATE TABLE sqlab_metadata (
  name VARCHAR(64) NOT NULL,
  value JSON NOT NULL,
  PRIMARY KEY (name)
);
