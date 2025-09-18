# App build
FROM python:3.13-slim

RUN pip install uv

WORKDIR /app

# Copy App files
COPY App/ ./

# No frontend static files needed for pure App

# Create __init__.py files for all directories containing Python files
RUN find . -name "*.py" -exec dirname {} \; | xargs -I {} touch {}/__init__.py

# Install dependencies using uv
RUN uv sync --frozen

# Activate virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]