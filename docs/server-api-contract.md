# Server API Contract

As of date: **February 16, 2026**

Base URL: `http://localhost:8000` (dev)

All JSON API endpoints accept and return `Content-Type: application/json`.
The `/metrics` endpoint is an exception and returns Prometheus text exposition format (`Content-Type: text/plain; version=0.0.4`).
For browser clients, use `credentials: "include"` when cookies are involved.

---

## Authentication

### POST `/auth/register`

Create a new user account and receive an access token.

**Request body** -

```json
{
  "name": "Jane Doe",
  "email": "you@example.com",
  "password": "password123"
}
```

**Success — `201 Created`**

```json
{
  "accessToken": "eyJhbG...",
  "refreshToken": "eyJhbG...",
  "user": {
    "id": "uuid",
    "email": "you@example.com",
    "name": "Jane Doe"
  }
}
```

**Errors** -

- `409`: email already exists
- `422`: invalid/missing fields (name, email, password rules)

---

### POST `/auth/login`

Authenticate an existing user and receive an access token.

**Request body** -

```json
{
  "email": "you@example.com",
  "password": "password123"
}
```

**Success — `200 OK`**

```json
{
  "accessToken": "eyJhbG...",
  "refreshToken": "eyJhbG...",
  "user": {
    "id": "uuid",
    "email": "you@example.com",
    "name": "Jane Doe"
  }
}
```

**Errors** -

- `401`: invalid email or password

Note: same error for unknown email and wrong password (prevents user enumeration).

---

### POST `/auth/refresh`

Exchange a valid refresh token for a new access token + refresh token pair.
The old refresh token is invalidated (rotation — single use).

**Request body** -

```json
{
  "refreshToken": "eyJhbG..."
}
```

**Success — `200 OK`**

```json
{
  "accessToken": "eyJhbG...",
  "refreshToken": "eyJhbG...",
  "user": {
    "id": "uuid",
    "email": "you@example.com",
    "name": "Jane Doe"
  }
}
```

**Errors** -

- `401`: expired refresh token
- `401`: invalid or tampered refresh token
- `401`: already-used refresh token (rotation detected reuse)
- `401`: user not found or deactivated

---

### POST `/auth/logout`

Revoke the current access token and (optionally) a refresh token.
Requires `Authorization: Bearer <accessToken>` header.

```json
{
  "refreshToken": "eyJhbG..."
}
```

**Success — `204 No Content`**

Always returns 204 (idempotent). Also clears the session cookie.

---

## Protected Endpoints

Protected routes require:

```http
Authorization: Bearer <accessToken>
```

Tokens are ES256 JWTs and short-lived.

### GET `/resource/me`

Returns the authenticated user's identity.

**Success — `200 OK`**

```json
{
  "username": "uuid",
  "message": "Hello uuid, you have a valid token."
}
```

**Errors** -

- `401`: invalid token
- `401`: expired token

---

## Utility

### GET `/health`

No auth required. Returns server health status.

**Success — `200 OK`**

```json
{
  "status": "ok",
  "checks": {
    "redis": "not_configured"
  },
  "slos": {
    "availability": {
      "current": 100.0,
      "target": 99.5,
      "healthy": true
    },
    "latency_p95": {
      "current": 100.0,
      "target": 95.0,
      "healthy": true
    },
    "queue_processing": {
      "current": 100.0,
      "target": 98.0,
      "healthy": true
    }
  }
}
```

---

## Recently Implemented

- `POST /auth/refresh`: refresh access token (with rotation)
- `GET /auth/me`: load user profile

---

## Common Response Shapes

```ts
interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: {
    id: string;
    email: string;
    name: string;
  };
}
```

```ts
interface AuthErrorResponse {
  detail: {
    message: string;
  };
}
```

```ts
interface TokenErrorResponse {
  detail: string;
}
```

---

## Planned Platform APIs (`/v1`) (Design Targets)

The following routes are planned platform surfaces and may be partially implemented or in progress:

- `POST /v1/courses/{courseId}/enroll`
- `POST /v1/courses/{courseId}/nodes/{nodeId}/complete`
- `POST /v1/assessments/{assessmentId}/attempts`

Use these as forward-looking contract targets and verify implementation status before relying on them in demos.
