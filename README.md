# SQLab

![SQL adventure builder logo](assets/logo/color.svg)

An SQLab adventure is a text-based game in which the player learns SQL by creating queries to solve puzzles.

It consists itself in a self-contained database, which includes the core dataset, a handful of stored procedures and all the accompanying messages (statements of the questions, answers, instructions, etc.). Each message is encrypted independently in an additional table `sqlab_msg`.

Wrapping an SQLab adventure in a web application is not necessary (although still possible). The students can play under any generic GUI like [DBeaver](https://dbeaver.io), [phpMyAdmin](https://www.phpmyadmin.net), [pgAdmin](https://www.pgadmin.org), etc., or even in a bare command-line interface.

The students are instructed to append to their `SELECT` clauses a given formula (e.g, `salt_042(sum(hash) OVER ()) AS token`) that will calculate a token. This token (a big integer) may enable them to decrypt the next episode or, in the case of a wrong query, to receive the appropriate hint (provided that the game creator anticipated it).

As a result, they can practice by themselves, without any supervision. To avoid boredom, we recommend that the instructor logs their queries, and updates the database on the fly with new hints, improving the game for everyone in the process.

## Examples on GitHub

| Game | Pitch | Versions | DBMS | Included |
| --- | --- | --- | --- | --- |
| [Island](https://github.com/laowantong/sqlab_island) | An adaptation of [SQL Island](https://sql-island.informatik.uni-kl.de) by Johannes Schildgen | English | MySQL, PostgreSQL | Sources + SQLab database |
| Sessform | A set of independant exercises + _Mortelles Sessions_, a police investigation on a training company | French | MySQL, PostgresQL | SQLab database (coming soon) |
| Club | An adaptation of [PostgreSQL Exercises](https://pgexercises.com) by Alisdair Owens | English | PostgreSQL | Sources + SQLab database (coming later) |
| Corbeau | An original adaptation of the movie [_Le Corbeau_](https://fr.wikipedia.org/wiki/Le_Corbeau_(film,_1943)) by Henri-Georges Clouzot (1943) | French | MySQL | SQLab database (coming later) |

## How can I create my own SQLab adventure?

The `sqlab` command-line tool is not required to play an adventure, but is necessary to create one.

```
pip install sqlab
```

The documentation is not yet available. In the meantime, you may explore the repository of [SQLab Island](https://github.com/laowantong/sqlab_island). The provided dataset and Jupyter notebooks serve as source material for the creation of the adventure.
