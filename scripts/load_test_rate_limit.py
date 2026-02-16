#!/usr/bin/env python3
"""Load test script — demonstrates rate limiting behavior.

RUN:  python scripts/load_test_rate_limit.py

Sends TOTAL_REQUESTS to a rate-limited endpoint in rapid succession and
prints a summary showing how many succeeded (200) vs. were throttled (429).

Prerequisites:
  - The API must be running: uvicorn app.main:app --port 8000
  - A valid test user must exist (the default seed user works)

This script is educational — it's not a production load testing tool.
For real load testing, use tools like locust, k6, or wrk.
"""

from __future__ import annotations

import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
TOTAL_REQUESTS = 100


def main() -> None:
    print("Rate Limit Load Test")
    print("=" * 50)
    print(f"Target: {BASE_URL}/resource/me")
    print(f"Total requests: {TOTAL_REQUESTS}")
    print()

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        # Step 1: Get an access token via the OAuth flow
        # For simplicity, we use the login form + extract a token
        # In a real setup, you'd use the OAuth PKCE flow
        print("Obtaining access token...")

        # Login to get a session cookie
        resp = client.post(
            "/login",
            data={"email": "test@example.com", "password": "test-password"},
            follow_redirects=False,
        )
        if resp.status_code not in (200, 302):
            print(f"Login failed: {resp.status_code}")
            sys.exit(1)

        # For this test, we'll use the internal token endpoint
        # Since we're testing rate limits, we can use any valid JWT
        print("Note: Using direct token creation for load test")
        print("(In production, use the OAuth PKCE flow)")
        print()

        # Import and create a token directly (test helper)
        from app.services import token_service

        token = token_service.create_access_token(sub="load-test-user")

        # Step 2: Send requests and track results
        results: dict[int, int] = {}
        start = time.monotonic()

        for i in range(TOTAL_REQUESTS):
            resp = client.get(
                "/resource/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            results[resp.status_code] = results.get(resp.status_code, 0) + 1

            # Print progress every 20 requests
            if (i + 1) % 20 == 0:
                print(f"  Sent {i + 1}/{TOTAL_REQUESTS} requests...")

        elapsed = time.monotonic() - start

        # Step 3: Print results
        print()
        print(f"Results after {TOTAL_REQUESTS} requests ({elapsed:.2f}s):")
        print("─" * 40)

        allowed = results.get(200, 0)
        throttled = results.get(429, 0)
        other = sum(v for k, v in results.items() if k not in (200, 429))

        print(f"  Allowed  (200): {allowed:>4}")
        print(f"  Throttled(429): {throttled:>4}")
        if other:
            print(f"  Other:          {other:>4}")

        print()
        print("Token bucket capacity: 60 (default)")
        print("Refill rate: 1 token/second")
        print()

        if throttled > 0:
            print("Rate limiting is working correctly.")
            print("The first ~60 requests succeeded (bucket capacity),")
            print("then subsequent requests were throttled.")
        else:
            print("WARNING: No requests were throttled.")
            print("This might mean rate limiting is not configured correctly.")


if __name__ == "__main__":
    main()
