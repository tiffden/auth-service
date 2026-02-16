# Server API Contract

As of date: **February 16, 2026**

Base URL: `http://localhost:8000` (dev)

All endpoints accept and return `Content-Type: application/json`.
For browser clients, use `credentials: "include"` when cookies are involved.

---

## Authentication

### POST `/auth/register`

Create a new user account and receive an access token.

**Request body**

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
  "user": {
    "id": "uuid",
    "email": "you@example.com",
    "name": "Jane Doe"
  }
}
```

**Errors**

- `409`: email already exists
- `422`: invalid/missing fields (name, email, password rules)

---

### POST `/auth/login`

Authenticate an existing user and receive an access token.

**Request body**

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
  "user": {
    "id": "uuid",
    "email": "you@example.com",
    "name": "Jane Doe"
  }
}
```

**Errors**

- `401`: invalid email or password

Note: same error for unknown email and wrong password (prevents user enumeration).

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

**Errors**

- `401`: invalid token
- `401`: expired token

---

## Utility

### GET `/health`

No auth required. Returns server health status.

**Success — `200 OK`**

```json
{
  "status": "ok"
}
```

---

## Not Yet Implemented (As of February 16, 2026)

These are referenced by client flows but are not implemented in this server as of this date:

- `POST /auth/refresh`: refresh access token
- `GET /auth/me`: load user profile

Client behavior expectation:

- handle `404` gracefully
- keep UI state coherent (show unavailable, fallback, or re-auth path)

---

## Common Response Shapes

```ts
interface AuthResponse {
  accessToken: string;
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
