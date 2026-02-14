from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

# PKCE-related logic, which is used by the /oauth/authorize and /oauth/token endpoints
# in oauth.py

# generate_code_verifier creates a random string that the client will use to prove
# possession of the code_challenge

# compute_code_challenge computes the code_challenge that the client will register
# with the authorization server, derived from the code_verifier
#
# ?? what is the authorization server's "code_challenge_method" parameter?
# For now we only support S256


# compute code verifier - a random string of 43–128 chars from the unreserved set
def generate_code_verifier() -> str:
    # 32 bytes of random data gives us 43 chars after base64url encoding,
    # which is minimum length.
    random_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(random_bytes).rstrip(b"=").decode("utf-8")
    return code_verifier


# compute code challenge from code verifier using S256 method
def compute_code_challenge(code_verifier: str) -> str:
    code_verifier_bytes = code_verifier.encode("utf-8")
    sha256_digest = hashlib.sha256(code_verifier_bytes).digest()
    code_challenge = (
        base64.urlsafe_b64encode(sha256_digest).rstrip(b"=").decode("utf-8")
    )
    return code_challenge


def verify_code_challenge(code_verifier: str, expected_challenge: str) -> bool:
    """Compare challenge derived from verifier against the stored challenge.

    Uses constant-time comparison to avoid timing side-channels.
    TRADE-OFF: hmac.compare_digest is ~negligible overhead vs plain ==,
    but plain == leaks challenge length/content via response timing,
    which could help an attacker brute-force a stolen code_challenge.
    """
    actual_challenge = compute_code_challenge(code_verifier)
    return hmac.compare_digest(actual_challenge, expected_challenge)
