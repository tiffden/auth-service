# OAuth 2.0 Overview Notes

Website: <https://www.oauth.com/>

## General

### Why JWT access tokens reduce runtime coupling

A JWT (JSON Web Token) is self-contained — it carries its own claims (sub, scope, exp, etc.) and a cryptographic signature. Any resource server that **holds the authorization server's public key can validate the token locally**, without making a network call back to the authorization server. This eliminates a runtime dependency: the resource server does not need the authorization server to be available at request time. With opaque tokens, by contrast, every API request requires an introspection call back to the authorization server, creating a synchronous coupling point and single point of failure.

### Why short TTL mitigates revocation weakness

JWTs are stateless — once issued, there is no central session store to delete. If a token is compromised, the authorization server has no built-in way to "un-issue" it. The primary mitigation is a short time-to-live (TTL), **typically minutes** rather than hours. A short-lived token limits the damage window: even if stolen, it expires quickly. This trades off convenience (clients must refresh more often) for security. For scenarios requiring immediate revocation (e.g., user logout, credential compromise), a complementary strategy like a token deny-list or switching to opaque tokens with introspection is necessary.

### Why Password grant is acceptable only in controlled first-party cases

***!! The OAuth 2.1 draft REMOVES this grant entirely. !!***

The **Resource Owner Password Credentials grant** sends the user's username and password directly to the client application, which then exchanges them for a token. **This means the client handles raw credentials** — a fundamental trust violation if the client is a third party. It is only acceptable when the client is a first-party, trusted application (e.g., a company's own mobile app talking to its own API) where the user already trusts the app with their credentials. For third-party apps, this grant trains users to enter credentials into untrusted software and bypasses the consent/redirect model that protects users.

### Why PKCE is required for public clients

***!! PKCE is now recommended for all clients (public and confidential) in OAuth 2.1 !!***

**Public clients (SPAs, mobile apps, CLIs) cannot securely store a client secret** — the binary or source is accessible to the user. Without a secret, the authorization code grant is vulnerable to interception: an attacker who intercepts the authorization code (via a malicious app registered to the same custom URI scheme, or through browser history/logs) can exchange it for tokens. **PKCE (Proof Key for Code Exchange)** mitigates this by having the ***client generate a random `code_verifier`, send a hashed `code_challenge`*** with the authorization request, and then prove possession of the original verifier at the token exchange step. An attacker who intercepts only the code cannot complete the exchange because they do not have the verifier.

### Why OAuth is about authorization, not identity proof

OAuth 2.0 answers the question "what is this client allowed to do?" — not "who is the user?"
An **access token** grants scoped permissions (read emails, write files) but does not inherently prove user identity.

For authentication (proving identity), **OpenID Connect (OIDC)** was built as a layer on top of OAuth 2.0.
OIDC adds an `id_token` (a JWT with identity claims like sub, email, name) and a standardized `/userinfo` endpoint.

## Overview

### Roles: Resource Owner, Client, Authorization Server, Resource Server

**Resource Owner:** The user (or entity) that owns the protected data and can grant access to it. Typically the end user who clicks "Allow" on a consent screen.

**Client:** The application requesting access to the resource owner's data. Can be confidential (server-side app that can keep a secret) or public (SPA, mobile app that cannot).

**Authorization Server:** The server that authenticates the resource owner, obtains consent, and issues access tokens. Examples: Auth0, Keycloak, Okta, or a custom implementation.

**Resource Server:** The API that holds the protected resources. It validates incoming access tokens and serves data if the token is valid and has sufficient scope.

### Access token purpose

Types of tokens:

- **Access token** — presented to the resource server to access protected resources. Short-lived.
- **Refresh token** — presented to the authorization server to obtain a new access token. Longer-lived. Never sent to the resource server.
- **ID token** (OIDC only) — a JWT containing identity claims about the user. Consumed by the client, not the resource server.

Access token purpose:

 **Bearer Tokens** — A bearer token means "whoever holds this token is authorized." There is no proof-of-possession; the token itself is the credential. This makes transport security (TLS) essential — if intercepted, anyone can use it.
 **Token Lifetime** — Access tokens should have short lifetimes (minutes to an hour). Short TTLs limit exposure if a token is leaked and reduce the need for complex revocation infrastructure. Refresh tokens handle session continuity.
 **Scope** — Scopes define what permissions the token grants (e.g., `read:messages`, `write:profile`). They are requested by the client, consented to by the user, and enforced by the resource server. Scope is about permission, not identity.

Key concepts to extract:
 • Bearer = possession is authorization — anyone with the token can use it, so protect it in transit and storage
 • Why short TTL is recommended — limits damage window of compromised tokens, reduces reliance on revocation
 • Scope is not identity; it is permission — scope says what you can do, not who you are

### What OAuth is Not

It is **authorization**, **not authentication** by itself. OAuth tells the resource server "this client is allowed to do X" but does not tell the client "this user is person Y."

Authentication requires OpenID Connect, which extends OAuth with identity tokens and a standardized identity layer.

## Grant Types

**Grant Types** — the different flows a client can use to obtain an access token, each suited to different client types and trust levels.

### Authorization Code Grant

A redirect-based flow designed for confidential and public clients where the user interacts via a browser:

1. **Client redirects** the user to the authorization server's `/authorize` endpoint with `response_type=code`, `client_id`, `redirect_uri`, `scope`, and `state`.
2. **User authenticates** with the authorization server and consents to the requested scopes.
3. **Authorization server redirects** back to the client's `redirect_uri` with a short-lived authorization `code` and the `state` parameter.
4. **Client exchanges** the code for tokens by calling the `/token` endpoint (back-channel, server-to-server) with the code, `client_id`, `client_secret` (if confidential), and `redirect_uri`.
5. **Authorization server returns** an access token (and optionally a refresh token).

 • **PKCE extension**: The client generates a `code_verifier` (random string) and sends `code_challenge = SHA256(code_verifier)` in step 1. In step 4, the client sends the original `code_verifier`. The authorization server verifies the hash matches before issuing tokens. This protects against code interception attacks.
 • **Why public clients need PKCE**: Public clients cannot keep a client secret. Without PKCE, a stolen authorization code can be exchanged by an attacker. PKCE binds the code to the original requester.

What to extract:
 • Redirect-based flow — the user's browser mediates between client and authorization server
 • Code exchange step — the code-to-token exchange happens on a secure back channel, not through the browser
 • Why access tokens are not returned in the front channel — returning tokens in a redirect URL exposes them in browser history, logs, and referrer headers. The code is a short-lived, single-use intermediary that limits this exposure.

### !! Resource Owner Password Credentials (Password Grant)

**!! The OAuth 2.1 specification removes this grant entirely. !!**

A direct credential exchange — the client collects the user's username and password and sends them straight to the authorization server's `/token` endpoint with `grant_type=password`.

Flow:

1. User gives credentials directly to the client application.
2. Client sends `grant_type=password`, `username`, `password`, `client_id`, and optionally `client_secret` to `/token`.
3. Authorization server validates credentials and returns an access token.

 **When it is acceptable**: Only for first-party, highly trusted clients (e.g., a company's own native app) where the user already implicitly trusts the app with credentials, and redirect-based flows are impractical.

 **Why it is dangerous for third-party apps**: The client sees the user's raw password. Third-party apps could log, leak, or misuse it. It bypasses the consent screen and trains users to type passwords into arbitrary apps. There is no support for MFA or federated login.

### Client Credentials Grant

Machine-to-machine authentication where no user is involved:

1. Client sends `grant_type=client_credentials`, `client_id`, and `client_secret` to the `/token` endpoint.
2. Authorization server validates the client's credentials and returns an access token.

 • No user context — the token represents the client (service) itself, not a user.
 • Service identity vs user identity — the resulting token's `sub` claim is the client, and there is no user to consent. Scopes are pre-configured for the client.

 Use cases: microservice-to-microservice calls, background jobs, cron tasks, any server-side process that needs API access on its own behalf.

## JWT (JSON Web Token)

A JWT is a compact, URL-safe token format consisting of three Base64url-encoded parts separated by dots: `header.payload.signature`.

**Structure:**

- **Header** — algorithm (`alg`: RS256, ES256, etc.) and token type (`typ`: JWT).
- **Payload** — claims: registered (`iss`, `sub`, `aud`, `exp`, `iat`, `jti`), public, and private claims.
- **Signature** — `HMAC` or `RSA`/`ECDSA` signature over header + payload, ensuring integrity and authenticity.

**Signature validation**: The resource server validates a JWT by checking the signature against the authorization server's public key (obtained from a JWKS endpoint), verifying `exp` has not passed, and confirming `iss` and `aud` match expected values. No network call to the authorization server is needed at validation time.

Resource servers must verify the `aud` claim to ensure the token was issued for this API and not another service in the ecosystem. This prevents token reuse across services. Without this check, a token intended for Service A could be replayed against Service B if both trust the same authorization server.  

**Claims**: Structured key-value data embedded in the token. Standard claims include `sub` (subject/user), `iss` (issuer), `aud` (audience), `exp` (expiration), `scope`/`scp` (permissions).

**When JWTs are appropriate**: When you need stateless, locally-validated tokens for distributed systems where calling back to the authorization server for every request is impractical or introduces unwanted coupling.

**When opaque tokens are better**: When you need immediate revocation capability, when token payloads would be too large, when you do not want token contents visible to the client, or in simpler architectures where an introspection endpoint is acceptable.  How fast "Immediate revocation" is depends on how introspection results are **cached at the resource server** layer.

Key architecture:
 Local validation vs introspection — JWTs enable local validation (no network call); opaque tokens require introspection (network call to the authorization server). Local validation scales better but sacrifices instant revocation.

 Revocation difficulty — JWTs cannot be "recalled" once issued. Mitigation strategies include short TTLs, token deny-lists, or event-driven cache invalidation. Opaque tokens can be revoked instantly by deleting them from the authorization server's store.

 Trust boundaries — JWTs expose claims to anyone who decodes them (Base64, not encrypted by default). Do not put sensitive data in JWT payloads unless using JWE (encrypted JWTs). Opaque tokens reveal nothing without an introspection call.

## Refresh Tokens

 **Why they exist** — Access tokens are deliberately short-lived to limit exposure. Refresh tokens allow the client to obtain new access tokens without re-prompting the user for credentials, maintaining session continuity while keeping access tokens short-lived.

 **Rotation** — Refresh token rotation issues a new refresh token with every use and invalidates the old one. If an attacker steals and uses a refresh token, the legitimate client's next refresh attempt will fail (because the token was already rotated), signaling a compromise. This enables automatic breach detection.

 **Revocation complexity** — Refresh tokens are long-lived and stored server-side, so they can be explicitly revoked (unlike JWTs). However, managing revocation across distributed systems adds complexity. A centralized token store or event-based propagation is needed to ensure revoked refresh tokens are rejected everywhere.

## Other Topics in OAuth

 • **Token Introspection** (RFC 7662) — An endpoint (`/introspect`) where a resource server can send an opaque token to the authorization server and get back its metadata (active, scope, exp, sub, etc.). Required when using opaque tokens; unnecessary when using self-contained JWTs.
 • **Revocation Endpoint** (RFC 7009) — An endpoint (`/revoke`) where a client can request the invalidation of an access or refresh token. The authorization server marks the token as revoked. Essential for logout flows and credential compromise response.
 • **Dynamic Client Registration** (RFC 7591) — An endpoint (`/register`) where clients can programmatically register themselves with the authorization server and obtain a `client_id` and `client_secret`. Useful for platforms that onboard many third-party integrations without manual admin configuration.

## Implementation of Endpoints

```bash
pytest tests/api/test_oauth_pkce_flow.py -v -s
```

Authorize (9 steps):

1. request received →
2. response_type →
3. client_id →
4. redirect_uri →
5. PKCE params →
6. user auth (stub) →
7. code generated →
8. metadata stored →
9. redirect

Token (9 steps):

1. request received →
2. grant_type →
3. code found →
4. not expired →
5. consumed (single-use) →
6. client_id matches →
7. redirect_uri matches →
8. PKCE verified →
9. token issued
