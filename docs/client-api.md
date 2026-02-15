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

- All requests are resolved in an org context (`org_id`) from auth principal.
- All write paths are org-scoped and idempotent where retriable.

### Enroll learner

`POST /v1/courses/{courseId}/enroll`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Creates enrollment if absent.
- Appends `enrolled` event to progress event log.
- Replayed key with same payload returns existing enrollment.
- Replayed key with mismatched payload returns conflict.

### Complete pathway node

`POST /v1/courses/{courseId}/nodes/{nodeId}/complete`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Appends `item_completed` event.
- Updates/readies projection for learner progress state.

### Submit assessment attempt

`POST /v1/assessments/{assessmentId}/attempts`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Persists attempt submission.
- Persists grade/evaluation outcome.
- Appends `assessment_passed` or `assessment_failed` event.

### Issue credential

`POST /v1/credentials/{credentialId}/issue`

Headers:

- `Authorization: Bearer <accessToken>`
- `Idempotency-Key: <uuid>`

Behavior:

- Evaluates issuance rules against projection and attempts.
- Records issuance.
- Appends `credential_issued` event.

### Versioning policy

- `/v1` accepts additive response fields and optional request fields.
- Breaking contract changes require `/v2`.

### Idempotency policy

- Required on retriable mutating routes.
- Idempotency is keyed by `(org_id, idempotency_key)`.
- Requests reusing a key with different semantics return conflict.
