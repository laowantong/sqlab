## Accompanying material for _Learning SQL from Within_

This directory contains the code for the paper _Learning SQL from within: integrating database exercises into the database itself_ by [author names removed for review] (2024).

It is organized as follows:

- [`code.ipynb`](https://nbviewer.org/github/laowantong/sqlab/blob/main/pub/2024-10.%20Learning%20SQL%20from%20Within/code.ipynb): A Jupyter notebook compiling all the working example queries of the paper, as well as the Python code to generate some tables and figures.
- `output`: A directory used by the notebook to store the generated files.
- `README.md`: This file.
- `sqlab_company.sql`: A SQL script that creates and populates a MySQL database for a fictional company, as defined in _Fundamentals of database systems, 7th edition_ by Ramez Elmasri and Shamkant B. Navathe (Addison-Wesley, 2017), and augmented with SQLab metadata (`hash` columns, triggers, etc.).

### Optional installations

You can skim the notebook and its pre-generated outputs without installing anything.

However, if you want to run the notebook yourself, you will need a [MySQL](https://dev.mysql.com/doc/mysql-installation-excerpt/8.0/en/) server to create the database:

```bash
mysql -u root -p < sqlab_company.sql
```

On the Python side, we recommend installing Jupyter Notebook via [Anaconda](https://www.anaconda.com/products/distribution). It already comes with the necessary packages, except for [JupySQL](https://jupysql.ploomber.io/en/latest/quick-start.html). 
Otherwise, you will need to install manually 
[Jupyter Notebook](https://jupyter.org/install),
[NumPy](https://numpy.org/install/),
[Plotly](https://plotly.com/python/getting-started/),
[Pandas](https://pandas.pydata.org/pandas-docs/stable/getting_started/install.html),
[SQLAlchemy](https://docs.sqlalchemy.org/en/20/intro.html#installation),
and [Connector/Python](https://dev.mysql.com/doc/connector-python/en/connector-python-installation-binary.html).

Note that you don't need to install SQLab to run the code in this directory, as the databases it creates are standalone by nature.
