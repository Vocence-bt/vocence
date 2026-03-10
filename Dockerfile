# Vocence Subnet - Validator image
# Build: docker build -t vocence-validator .
# Run: docker-compose up -d (see docker-compose.yml)

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv and dependencies (lockfile for reproducible builds)
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir --upgrade pip uv \
    && uv sync --frozen --no-dev --no-install-project

# Copy application code and install project
COPY . .
RUN uv sync --frozen --no-dev

# Non-root user
RUN useradd -m -u 1000 validator && chown -R validator:validator /app
USER validator

ENV NETWORK=finney
ENV NETUID=102
ENV LOG_LEVEL=INFO
ENV PATH="/app/.venv/bin:$PATH"

# Single process: sample generation + weight setting (same as vocence serve)
CMD ["vocence", "serve"]
