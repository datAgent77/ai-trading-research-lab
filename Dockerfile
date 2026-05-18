# Paper research lab — runtime image (Python 3.13, matches pyproject requires-python).
FROM python:3.13-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Some wheels (e.g. pyarrow) may need a compiler on uncommon platforms.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY scripts ./scripts

# Default prints Typer help for the primary CLI script (override in compose).
CMD ["python", "scripts/run_backtest.py", "--help"]
