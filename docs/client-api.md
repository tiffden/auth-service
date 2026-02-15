# Client API Reference

Base URL: `http://localhost:8000` (dev)

All endpoints accept and return `Content-Type: application/json`.
Use `credentials: "include"` on fetch calls to send cookies.

---

## Authentication

### POST /auth/register

Create a new user account and receive an access token.

**Request body:**

```json
{
  "name": "Jane Doe",
  "email": "you@example.com",
  "password": "password123"
}
```

| Field      | Type   | Rules                 |
| ---------- | ------ | --------------------- |
| `name`     | string | Required, non-empty   |
| `email`    | string | Required, valid email |
| `password` | string | Required, min 8 chars |

**Success — 201 Created:**

```json
{
  "accessToken": "eyJhbG...",
  "user": {
    "id": "uuid",
    "email": "you@example.com",
    "name": "Jane Doe"
  }
}
```

**Errors:**

| Status | Condition            | Body                                                                      |
| ------ | -------------------- | ------------------------------------------------------------------------- |
| 409    | Email already exists | `{ "detail": { "message": "A user with this email already exists" } }`    |
| 422    | Invalid email        | `{ "detail": { "message": "Invalid email address" } }`                    |
| 422    | Missing name         | `{ "detail": { "message": "Name is required" } }`                         |
| 422    | Password too short   | `{ "detail": { "message": "Password must be at least 8 characters" } }`   |

**curl:**

```bash
curl -i -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane Doe","email":"you@example.com","password":"password123"}'
```

---

### POST /auth/login

Authenticate an existing user and receive an access token.

**Request body:**

```json
{
  "email": "you@example.com",
  "password": "password123"
}
```

| Field      | Type   | Rules    |
| ---------- | ------ | -------- |
| `email`    | string | Required |
| `password` | string | Required |

**Success — 200 OK:**

```json
{
  "accessToken": "eyJhbG...",
  "user": {
    "id": "uuid",
    "email": "you@example.com",
    "name": "Jane Doe"
  }
}
```

**Errors:**

| Status | Condition                     | Body                                                          |
| ------ | ----------------------------- | ------------------------------------------------------------- |
| 401    | Wrong email or wrong password | `{ "detail": { "message": "Invalid email or password" } }`    |

Same error for unknown email and wrong password (prevents user enumeration).

**curl:**

```bash
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"password123"}'
```

---

## Protected Endpoints

All protected endpoints require the `Authorization` header:

```html
Authorization: Bearer <accessToken>
```

Tokens are ES256 JWTs, valid for 15 minutes.

| Status | Condition       | Body                             |
| ------ | --------------- | -------------------------------- |
| 401    | Missing/invalid | `{ "detail": "Invalid token" }`  |
| 401    | Expired         | `{ "detail": "Token expired" }`  |

### GET /resource/me

Returns the authenticated user's identity.

**Success — 200 OK:**

```json
{
  "username": "uuid",
  "message": "Hello uuid, you have a valid token."
}
```

**curl:**

```bash
curl -i http://localhost:8000/resource/me \
  -H "Authorization: Bearer <accessToken>"
```

---

## Utility

### GET /health

No auth required. Returns server status.

**Success — 200 OK:**

```json
{ "status": "ok" }
```

---

## Not Yet Implemented

These endpoints are referenced by the client but do not exist on the server yet:

| Endpoint        | Method | Purpose                                              |
| --------------- | ------ | ---------------------------------------------------- |
| `/auth/refresh` | POST   | Refresh access token (cookie-based, no auth header)  |
| `/auth/me`      | GET    | Load user profile (Bearer token)                     |

The client should handle 404 gracefully for these until they are built.

---

## Common Response Shape

**Success (auth endpoints):**

```typescript
interface AuthResponse {
  accessToken: string;
  user: {
    id: string;
    email: string;
    name: string;
  };
}
```

**Error:**

```typescript
// Auth endpoints (register, login)
interface ErrorResponse {
  detail: {
    message: string;  // Human-readable, safe to display
  };
}

// Protected endpoints (resource/me, etc.)
interface ErrorResponse {
  detail: string;  // e.g. "Token expired", "Invalid token"
}
```

The client reads `detail.message` for auth errors and `detail` (string) for token errors.

---

## Week 4 Planned Platform APIs (`/v1`)

These routes are the next platform surface aligned to the Week 4 data model.
They are design targets and may not be implemented yet.

### Tenant scope

- `users` are global identities; org access is resolved through `org_memberships`.
- Request authorization resolves an active org context (`org_id`) from membership.
- Write paths that can be retried are idempotent.

### Enroll learner

`POST /v1/courses/{courseId}/enroll`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Upserts `course_progress` to `in_progress` for `(org_id, user_id, course_id)`.
- Appends `progress_events` with `type=enrolled`.
- Replayed key with same payload returns original progress snapshot.
- Replayed key with mismatched payload returns conflict.

### Complete module item

`POST /v1/courses/{courseId}/nodes/{nodeId}/complete`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Appends `progress_events` with `type=item_completed` and `entity_type=module_item`.
- Returns `202 Accepted` if projection is async, or `200 OK` if synchronous.
- Projection updates `course_progress` (`percent_complete`, `last_activity_at`).

### Start assessment attempt

`POST /v1/assessments/{assessmentId}/attempts`

Headers:

- `Authorization: Bearer <accessToken>`
- Optional `Idempotency-Key: <uuid>`

Behavior:

- Creates `assessment_attempts` row with `status=in_progress`.
- Freezes `assessment_version` at start.
- Returns `attemptId`.

### Submit assessment attempt

`POST /v1/attempts/{attemptId}/submit`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Updates `assessment_attempts` to `status=submitted`.
- Appends `progress_events` with `type=assessment_submitted`.
- Grading path writes `attempt_responses`, updates attempt to `graded`, then appends:
  - `assessment_passed`, or
  - `assessment_failed`

### Issue credential

`POST /v1/credentials/{credentialId}/issue`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Evaluates eligibility using `course_progress` and assessment attempts.
- Records `user_credentials` with `evidence_json`.
- Appends `progress_events` with `type=credential_issued`.

### AI interaction logging (Week 9 implementation target)

This is included to match the Week 4 schema shape, but implementation is planned later.

- Session table: `ai_sessions`
- Child events: `ai_interactions`
- Human signal: `ai_feedback`

### Versioning policy

- `/v1` accepts additive response fields and optional request fields.
- Breaking contract changes require `/v2`.

### Idempotency policy

- Required on retriable mutating routes.
- Idempotency is keyed by `(org_id, idempotency_key)`.
- Requests reusing a key with different semantics return conflict.
