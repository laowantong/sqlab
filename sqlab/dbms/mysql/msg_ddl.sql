-- This supplementary table is created by sqlab to store all the texts relative to the activities:
-- contexts, statements, solutions, hints, etc. Each row is encrypted with its own token.

DROP TABLE IF EXISTS `sqlab_msg`;
CREATE TABLE `sqlab_msg` (
  `msg` blob NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
