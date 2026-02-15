# Architecture: auth-service

This document explains how the auth-service codebase is organized,
with a focus on the separation between domain logic and database
storage.

## The big picture

The service has four layers. Each layer has one job, and they talk
to each other in a strict order:

```text
HTTP request
    |
    v
[ API layer** ]       Receives the request, validates input, returns HTTP responses
    |
    v
[ Service layer ]     Applies business rules ("is this user allowed to enroll?")
    |
    v
[ Repository layer ]  Reads and writes data (the only layer that touches storage)
    |
    v
[ Database ]          PostgreSQL (or in-memory dicts for tests)
```

Why this matters: if you need to change how data is stored (move from
in-memory to Postgres, or from Postgres to a different database), you
only change the repository layer. The business rules and HTTP handling
stay the same.

## Domain models vs. database tables

This is the most important distinction in the codebase. It separates
"what the application thinks about" from "how the database stores it."

### Domain models — the application's vocabulary

**Where:** `app/models/`

These are plain Python objects (frozen dataclasses) that represent the
concepts the application works with: a User, a Course, a Credential,
a ProgressEvent.

Think of domain models as the nouns in your business vocabulary:

- A **User** has an email, a password hash, and roles
- A **Course** has a slug, a title, and a version number
- A **ProgressEvent** records that a learner did something (enrolled,
  completed a module, passed an assessment)
- A **Credential** is a badge or certificate definition
- A **UserCredential** is an issued instance ("Jane earned the
  Claude Basics badge on Feb 14")

Domain models are **frozen** — once created, they can't be changed.
If you need to update a user's password hash, you create a new User
object with the new hash. This prevents bugs where one part of the
code changes an object that another part is still reading.

Domain models know nothing about databases. They don't know what
PostgreSQL is. They don't have SQL in them. They're just data
containers with a few helper methods.

### Database tables

**Where:** `app/db/tables.py`

SQLAlchemy table definitions that describe how data is stored
in PostgreSQL. Each table maps to a domain model, but the
representation is different:

| Domain model (Python) | Database table (Postgres) | Why different |
| --------------------- | ------------------------- | ------------- |
| `tuple[str, ...]` for roles | `ARRAY(String)` column | Postgres has native arrays |
| `frozenset[str]` for scopes | `ARRAY(String)` column | Frozensets don't exist in SQL |
| `UUID` as Python object | `UUID` column type | Same concept, different type system |
| Frozen dataclass | Mutable row object | SQLAlchemy needs to track changes |

The table definitions also include things that don't exist in domain
models: foreign keys (relationships between tables), indexes (for
fast lookups), and constraints (like "email must be unique").

**Analogy:** If domain models are the forms, table definitions are
the filing cabinet's label system — which drawer, which folder,
which tab.

### Why keep them separate?

1. **Tests run without a database.** Unit tests use in-memory repos
   and domain models directly. No Postgres needed, no Docker needed,
   tests run in milliseconds.

2. **Database changes don't break business logic.** If you add an
   index, rename a column, or switch from Postgres to a different
   database, the domain models don't change. The business rules
   that use those models don't change either.

3. **The domain model is the truth.** The database table is just one
   way to persist it. You could also serialize a domain model to
   JSON, send it over a network, or store it in Redis. The domain
   model doesn't care.

---

## Repositories — the translators

**Where:** `app/repos/`

Repositories bridge domain models and database tables. They translate
between the two worlds:

- **Write:** Takes a domain model (e.g., `User`), converts it to a
  database row (`UserRow`), and saves it
- **Read:** Queries the database, gets a row back, and converts it to
  a domain model

Each repository has two implementations:

| Implementation | Where | Used for |
| -------------- | ----- | -------- |
| `InMemoryUserRepo` | `app/repos/user_repo.py` | Tests, development without Postgres |
| `PgUserRepo` | `app/repos/pg_user_repo.py` | Production, development with Postgres |

Both implement the same **Protocol** (interface). The service layer
doesn't know or care which one it's talking to.

**Analogy:** A repository is like a librarian. You ask for "the user
with email <jane@example.com>" and the librarian knows whether to look
in the filing cabinet (Postgres) or the desk drawer (in-memory dict).
You get back the same form either way.

### Protocol — the contract

**Where:** Defined at the top of each repo file (e.g., `UserRepo`)

A Protocol is a Python way of saying "any object that has these
methods will work." It's the contract between the service layer and
the repository:

```python
class UserRepo(Protocol):
    def get_by_email(self, email: str) -> User | None: ...
    def add(self, user: User) -> None: ...
```

Both `InMemoryUserRepo` and `PgUserRepo` satisfy this contract.
The service layer only knows about `UserRepo` — it doesn't import
either implementation directly.

---

## Migrations — version control for your database

**Where:** `alembic/versions/`

When you change a table definition in `app/db/tables.py`, the database
doesn't automatically update. You need a **migration** — a script that
tells Postgres "add this column" or "create this table."

Alembic manages migrations. Each migration is a Python file with an
`upgrade()` function (apply the change) and a `downgrade()` function
(undo it). Migrations run in order, tracked by a version number.

```bash
# Generate a new migration from table definition changes
alembic revision --autogenerate -m "add courses table"

# Apply all pending migrations
alembic upgrade head
```

---

## The entity map

Every entity in the system follows the same three-file pattern:

| Entity | Domain model | Database table | Repository |
| ------ | ------------ | -------------- | ---------- |
| User | `models/user.py` | `db/tables.py` → `UserRow` | `repos/user_repo.py` + `repos/pg_user_repo.py` |
| OAuth Client | `models/oauth_client.py` | `db/tables.py` → `OAuthClientRow` | `repos/oauth_client_repo.py` + `repos/pg_oauth_client_repo.py` |
| Auth Code | `models/authorization_code.py` | `db/tables.py` → `AuthorizationCodeRow` | `repos/auth_code_repo.py` + `repos/pg_auth_code_repo.py` |
| Organization | `models/organization.py` | `db/tables.py` → `OrganizationRow` | (repos planned) |
| Course | `models/course.py` | `db/tables.py` → `CourseRow` | (repos planned) |
| Assessment | `models/assessment.py` | `db/tables.py` → `AssessmentRow` | (repos planned) |
| Progress | `models/progress.py` | `db/tables.py` → `ProgressEventRow` | (repos planned) |
| Credential | `models/credential.py` | `db/tables.py` → `CredentialRow` | (repos planned) |
| AI Session | (planned Week 9) | `db/tables.py` → `AISessionRow` | (planned Week 9) |

---

## How a request flows through the system

Example: a learner enrolls in a course.

```text
1. POST /v1/courses/intro-to-claude/enroll
      |
2. API layer (courses.py)
   - Validates the JWT token → gets a Principal (who is this user?)
   - Checks: does this course exist?
      |
3. Service layer (future: enrollment_service.py)
   - Business rule: is the user already enrolled? → 409 Conflict
   - Creates a CourseProgress domain model (status = "in_progress")
   - Creates a ProgressEvent domain model (type = "enrolled")
      |
4. Repository layer
   - Saves CourseProgress to the course_progress table
   - Appends ProgressEvent to the progress_events table
      |
5. Returns 201 Created with the enrollment details
```

---

## Configuration: database on or off

The service works in two modes:

| Mode | When | DATABASE_URL | Repos used |
| ---- | ---- | ------------ | ---------- |
| In-memory | Tests, quick development | Not set | `InMemory*Repo` |
| PostgreSQL | Development with DB, staging, production | Set | `Pg*Repo` |

This is controlled by a single environment variable. When
`DATABASE_URL` is not set, the app starts without a database and
uses Python dicts for storage. All existing tests run this way —
no Docker or Postgres required.

---

## Key terms glossary

| Term | Plain English | Where in code |
| ---- | ------------- | ------------- |
| **Domain model** | A Python object representing a business concept | `app/models/` |
| **Frozen dataclass** | A domain model that can't be changed after creation | `@dataclass(frozen=True)` |
| **Table definition** | The database schema for a domain model | `app/db/tables.py` |
| **Repository** | The translator between domain models and database rows | `app/repos/` |
| **Protocol** | A contract saying "any class with these methods will work" | `class UserRepo(Protocol)` |
| **Migration** | A versioned script that changes the database schema | `alembic/versions/` |
| **Projection** | A pre-computed summary derived from raw events | `course_progress` table |
| **Event sourcing** | Storing every action as an append-only event | `progress_events` table |
| **Lifespan** | Startup/shutdown hooks for the FastAPI app | `app/main.py` |
| **Session** | A database connection scoped to one HTTP request | `app/db/engine.py` |
