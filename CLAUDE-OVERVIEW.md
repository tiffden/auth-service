# CLAUDE-OVERVIEW

As Claude, I need to understand the existing auth implementation to plan:

1. **Token service**: Read `app/services/token_service.py` fully — how are access tokens created? What claims are included? What's the signing config?

2. **Login flow**: Read `app/api/login.py` fully — how does the current login work? What does it return? How are tokens issued?

3. **Auth dependencies**: Read `app/api/dependencies.py` fully — how are tokens validated on protected routes?

4. **Config**: Read `app/core/config.py` — what token-related settings exist (secret, algorithm, TTLs)?

5. **API contract**: Check `docs/server-api-contract.md` if it exists — what does it say about /auth/refresh?

6. **Existing routes**: Read `app/api/auth.py` or whatever file defines auth routes — is there a stub for refresh?

7. **User model**: Read `app/models/user.py` — what fields does User have?

8. **Token blacklist**: Read `app/services/token_blacklist.py` — how does token revocation work?

9. **Tests**: Check `tests/api/test_auth.py` — what auth tests exist already?

10. **Main app router setup**: Read `app/main.py` to see how routers are included.
