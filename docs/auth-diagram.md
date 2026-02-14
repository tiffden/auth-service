# Authorization Diagram

Running the testcode which acts as a client shows every step:

```bash
pytest tests/api/test_oauth_pkce_flow.py -s --log-cli-level=INFO 
```

**Authorize (9 steps):** request received → response_type → client_id → redirect_uri → PKCE params → user auth (stub) → code generated → metadata stored → redirect

**Token (9 steps):** request received → grant_type → code found → not expired → consumed (single-use) → client_id matches → redirect_uri matches → PKCE verified → token issued
