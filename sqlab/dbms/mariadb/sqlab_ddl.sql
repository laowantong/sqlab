-- Supplementary tables created by SQLab.

-- All the texts relative to the activities: contexts, statements, solutions, hints, etc.
-- Each row is encrypted with its own token. No need for a primary key.

DROP TABLE IF EXISTS sqlab_msg;
CREATE TABLE sqlab_msg (
  msg TEXT NOT NULL
);

-- Some metadata about the SQLab database.

DROP TABLE IF EXISTS sqlab_info;
CREATE TABLE sqlab_info (
  name TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY (name)
);
