FROM python:3.12-slim

# Install Poetry
RUN pip install poetry

# Prevent Poetry from creating venvs inside container
ENV POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Copy dependency metadata first (better caching)
COPY pyproject.toml poetry.lock README.md ./

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy project files
COPY . .

# Run the CLI
ENTRYPOINT ["python", "-m", "sqlab"]