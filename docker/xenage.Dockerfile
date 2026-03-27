FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY structures /app/structures
COPY src /app/src
COPY tests /app/tests

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/src:/app

CMD ["xenage-control-plane"]
