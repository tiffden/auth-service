# How to Install Docker

brew install --cask docker
open -a Docker

verify:
docker --version
docker info

## Run Docker Desktop Application

Mac> Run Docker (from Applications directory)

## Build Docker

cd project root directory
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml ps

## DETAILS

Docker is a tool that lets you package an application together with:

- its runtime
- its dependencies
- its configuration
into a **container** that runs the same way on every machine.

On macOS, Docker does **not** run directly on the operating system. Instead, it runs inside a small Linux virtual machine, the Docker App.

## Key Terms

Docker Engine - background service that builds and runs containers
Docker CLI - the terminal 'docker' command
Docker Desktop - the macOS app that runs Docker Engine in a Linux virtual machine
Image - built immutable template for a container
Container - RUNNING instance of a container
Docker Compose - tool for running multiple containers together using a YAML file
Service - one container definition inside a Compose file

## Step 1 — Install Docker

brew install --cask docker

This installs Docker Desktop for macOS, which is a bundled distribution containing:
 • Docker Engine (runs inside a Linux VM)
 • Docker CLI (docker)
 • Docker Compose (docker compose)
 • A lightweight Linux virtual machine
 • A graphical UI (Docker Desktop)

The Docker CLI alone is not enough. Docker Desktop is required because it runs the **Docker Engine**.

## Step 2 — Start Docker Desktop

Docker (from Applications)

When Docker Desktop starts:
 • A Linux virtual machine is launched
 • The Docker daemon (dockerd) starts inside that VM
 • The Docker CLI on your Mac connects to that daemon

Without Docker Desktop running, Docker commands will fail because there is no engine to talk to.

## Step 3 — Build and Run the Application

From the repository root:

docker compose -f docker/docker-compose.yml up -d --build

Uses Docker Compose, which is a declarative tool for running multiple containers together.

-f docker/docker-compose.yml
Specifies the Compose file to use.
This file defines:
 • services (containers)
 • how they are built
 • ports, environment variables, volumes, and networks

up
Brings the application into the running state:
 • creates containers (if needed)
 • starts them in dependency order
 • creates networks and volumes

-d (detached mode)
Runs containers in the background and returns control to your terminal.

--build
Forces Docker to rebuild images before starting containers.
This ensures code changes are reflected in the running app.

### What Docker Creates for This Project

Running the command above may create:
 • Images
Built from Dockerfiles defined in the Compose file
 • Containers
Running instances of those images
 • Networks
Allow containers to talk to each other
 • Volumes (if defined)
Persist data across restarts

You can see these objects using:

docker images
docker ps
docker network ls
docker volume ls

## Step 4 — Verify Everything Is Running

Check running containers
docker ps
You should see containers listed with a STATUS of Up.

View logs
docker compose -f docker/docker-compose.yml logs
To follow logs live:
docker compose -f docker/docker-compose.yml logs -f

Test an auth-service Endpoint
curl -i <http://localhost:8000/health>

Run tests
docker compose -f docker/docker-compose.yml run --rm test
docker compose -f docker/docker-compose.yml run --rm test tests/api/test_auth.py -q
docker compose -f docker/docker-compose.yml run --rm test -k health -q

Run tests using a running container, start that container then:
docker compose -f docker/docker-compose.yml up -d test
docker compose -f docker/docker-compose.yml exec test python -m pytest -q

## Step 5 — Stop the Application

docker compose -f docker/docker-compose.yml down

This stops containers and removes:
 • containers
 • networks created by Compose

Images remain cached unless explicitly removed.

## Step 6 — Fully Reset and Cleanup Commands (Advanced)

docker compose -f docker/docker-compose.yml down --volumes

If you want only this codebase artifacts left locally, remove old ones:
docker rm -f docker-api 2>/dev/null || true
docker image rm docker-api:latest docker/welcome-to-docker:latest auth-services:week2-day3 2>/dev/null || true
docker image prune -f
