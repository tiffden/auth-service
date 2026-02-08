# --------------------
# HOW TO RUN:
# docker build -t auth-service:dev .
# docker run --rm -p 8000:8000 auth-service:dev
# --------------------
# syntax=docker/dockerfile:1

############################
# Stage 1 — builder (wheels)
############################
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tooling only in builder.
# (We keep it minimal; add gcc/libpq-dev/etc only if a dependency needs it.)
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

# Upgrade pip tooling (wheel build needs wheel package).
RUN python -m pip install --upgrade pip setuptools wheel

# Copy only dependency metadata first to maximize layer caching
# Copying pyproject.toml before code gives you good Docker cache behavior: deps don’t rebuild unless deps change
COPY pyproject.toml ./
# If you have a lock file, copy it too (uncomment if applicable):
# COPY uv.lock ./
# COPY poetry.lock ./
# COPY pdm.lock ./

# Build wheels for runtime deps into /wheels.
# Assumes your runtime deps are in [project].dependencies (not dev extras).
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

############################
# Stage 2 — runtime (minimal)
############################
FROM python:3.12-slim AS runtime

WORKDIR /app

# Required runtime env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# (Optional but common) tighten pip behavior in containers
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Install wheels from builder stage (no compiler toolchain needed here).
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/* \
  && rm -rf /wheels

# Now copy your app code (after deps for better caching).
COPY app ./app

# If your FastAPI app is app.main:app, expose 8000
EXPOSE 8000

# Use a non-dev server command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]