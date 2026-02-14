# syntax=docker/dockerfile:1
# --------------------
# HOW TO RUN:
# docker build -f docker/Dockerfile --target runtime -t auth-service:dev .
# docker run --rm -p 8000:8000 --env-file .env auth-service:dev
#
# docker history auth-service:dev
# --------------------

############################
# Stage 1 — builder (wheels)
############################

# Why slim here? Smaller base than full Debian/Ubuntu images, but still compatible
# with manylinux wheels and common build tooling.
FROM python:3.12-slim AS builder

WORKDIR /build

# Build-only OS packages.
# - build-essential provides gcc/make and headers for packages that compile native extensions.
# - This stays in the builder stage, so the final image doesn't contain compilers.
# rm -rf /var/lib/apt/lists/* prevents apt metadata from bloating the layer.
RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

# Ensure we have modern pip tooling that can build wheels reliably.
# - wheel: needed to produce wheel artifacts
# - setuptools: common build backend for legacy packages
RUN python -m pip install --upgrade pip setuptools wheel

# Copy only dependency metadata first to maximize layer caching
# Copying pyproject.toml before code gives you good Docker cache behavior: deps don’t rebuild unless deps change
# If only your application code changes, dependency layers remain cached.
COPY pyproject.toml ./
# If you have a lock file, copy it too (uncomment if applicable):
# COPY uv.lock ./
# COPY poetry.lock ./
# COPY pdm.lock ./

# Build wheels for runtime deps into /wheels.
# Assumes your runtime deps are in [project].dependencies (not dev extras).
# Key idea: resolve/build dependencies once in the builder stage, then install from wheels
# in the runtime stage without needing compilers.
#
# --no-cache-dir: avoids pip’s download/build cache being baked into the image layer.
# --wheel-dir /wheels: outputs wheel files we can copy into the runtime image.
#
# Note: `pip wheel .` builds a wheel for this project and its dependencies based on pyproject.toml.
# If your project itself is not meant to be installed as a package, you can instead:
#   - export requirements and wheel those, or
#   - use a requirements.txt workflow.
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

############################
# Stage 2 — runtime (minimal)
# Runtime stage should contain:
# - Python interpreter
# - only runtime dependencies
# - application source
# It should NOT contain compilers or build toolchains.
############################
FROM python:3.12-slim AS runtime

WORKDIR /app

# Create a dedicated non-root runtime user.
RUN groupadd --system appuser \
  && useradd --system --gid appuser --create-home --home-dir /home/appuser appuser

# Required runtime env
# - APP_ENV=prod: explicit runtime mode so containers never default to dev behavior
# - PYTHONDONTWRITEBYTECODE=1: don’t generate .pyc files (less disk churn in containers)
# - PYTHONUNBUFFERED=1: stdout/stderr unbuffered (logs appear immediately)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=prod \
    PORT=8000

# (Optional but common) tighten pip behavior in containers
# Pip behavior hardening:
# - Disable version check noise
# - Ensure pip cache is not stored in layers
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# FROM WHEELS USING COPY - fallback works everywhere
# This is the crucial multi-stage handoff: compiled artifacts without compilers in runtime.
# Install wheels from builder stage (no compiler toolchain needed here).
# COPY --from=builder /wheels /wheels

# Install from local wheels.
# Benefits:
# - fast (no network needed if wheels are present)
# - reproducible (uses the exact wheel artifacts built earlier)
# - avoids leaving behind build deps/caches
# rm -rf /wheels - Removes wheels after installation so they don’t occupy space in the final image
# RUN python -m pip install --no-cache-dir /wheels/* \
#    && rm -rf /wheels

# VERSUS DIRECT (SAVES 7MB)
# Install wheels from builder without creating a persistent /wheels layer
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels,readonly \
    python -m pip install --no-cache-dir /wheels/*

# Now copy your app code (after deps for better caching).
COPY --chown=appuser:appuser app ./app

# Expose the port uvicorn will bind to (overridable via PORT env var)
EXPOSE ${PORT}

# Drop root privileges for runtime.
USER appuser

# Production-ish default command.
# - Bind to 0.0.0.0 so the container is reachable from outside.
# - Port is read from the PORT env var (default 8000).
# - exec replaces the shell so uvicorn is PID 1 and receives SIGTERM directly.
#
# Note: In local dev you might add `--reload`, but avoid that in production images.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port $PORT"]

############################
# Stage 3 — dev/test (tooling)
# Includes dev extras for local test workflows.
############################
FROM runtime AS devtest

USER root

# Install local project + dev tooling (pytest, ruff, pre-commit, etc.).
COPY pyproject.toml ./
RUN python -m pip install --no-cache-dir -e ".[dev]"

USER appuser
ENV APP_ENV=test

CMD ["python", "-m", "pytest", "-q"]
