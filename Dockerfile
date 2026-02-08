# --------------------
# HOW TO RUN:
# docker build -t auth-service:dev .
# docker run --rm -p 8000:8000 auth-service:dev
# --------------------
FROM python:3.12-slim

# Keep Python logs unbuffered + avoid .pyc in containers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (minimal). Add more later only if you need compiled wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (better caching)
COPY pyproject.toml ./
# If you have a lock file, copy it too (uncomment the one you actually have)
# COPY uv.lock ./
# COPY poetry.lock ./
# COPY requirements.txt ./

# Install runtime deps - listed under pyproject.toml [project] dependencies=
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

# Copy your source
COPY app ./app

EXPOSE 8000

# --host 0.0.0.0 is required so the container listens on all interfaces (so the port mapping works)
# EXPOSE 8000 is documentation for the image; the real port mapping is -p 8000:8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]