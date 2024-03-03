import re
import subprocess
import nbformat
from nbconvert.preprocessors import CellExecutionError, ExecutePreprocessor

from .text_tools import FAIL, OK, RESET, WARNING, SQLFormatter

def run_notebook(config: dict) -> bool:
    ipynb_path = config["source_path"]
    record_path = config["output_dir"] / "records.json"
    if record_path.is_file() and ipynb_path.stat().st_mtime < record_path.stat().st_mtime:
        if input(f"{WARNING}The notebook is older than 'records.json'. Run it anyway (y/)? {RESET}").lower() != 'y':
            return True
    nb = nbformat.read(ipynb_path, as_version=4)
    print(f"Running '{ipynb_path}'...")
    run_notebook = ExecutePreprocessor(kernel_name='python3', timeout=None).preprocess
    success = True
    try:
        run_notebook(nb, {"metadata": {"path": ipynb_path.parent}})
    except CellExecutionError as e:
        if not "EOFError" in str(e):
            print(f"{FAIL}Error: {e}{RESET}")
            success = False
    if success or input("Updating the notebook anyway (y/)? ").lower() == 'y':
        print(f"Formatting SQL queries in '{ipynb_path}'...")
        format_sql = SQLFormatter(config)
        magic_header = "%%sql\n"
        for cell in nb.cells:
            if cell.cell_type == "code":
                if cell.source.startswith(magic_header):
                    content = cell.source[len(magic_header):]
                    (comment, query, end_comment, *whatever) = re.split(r"(?m)((?:^(?!--).*\n?)+)", content, maxsplit=1) + ["", ""]
                    cell.source = f"{magic_header}{comment}{format_sql(query)}\n{end_comment}".rstrip()
                
        # Clean up the notebook.
        for cell in nb.cells:
            cell.metadata.pop("scrolled", None)
            if cell.cell_type == "code":
                cell.metadata.pop("execution", None)
                cell.execution_count = None
                for output in cell.outputs:
                    # Suppress useless execution counts.
                    if "execution_count" in output:
                        output["execution_count"] = None
                    # Suppress redundant plain text tables.
                    if "data" in output:
                        if "text/plain" in output["data"]:
                            if output["data"]["text/plain"].startswith("+--"):
                                output["data"].pop("text/plain")

        nbformat.write(nb, ipynb_path)
        print(f"{OK}Notebook updated.{RESET}")
        subprocess.run(["jupyter", "trust", ipynb_path], check=True)
        print(f"{OK}Notebook trusted.{RESET}")

    return success
