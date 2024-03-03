-- This supplementary table is created by sqlab to store all the texts relative to the activities:
-- contexts, statements, solutions, hints, etc. Each row is encrypted with its own token.

DROP TABLE IF EXISTS sqlab_msg;
CREATE TABLE sqlab_msg (msg BYTEA NOT NULL);
