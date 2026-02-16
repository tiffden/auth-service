# Rate Limit Design

Rate limiting controls how many requests a client can make in a given
time window.  Without it, a single misbehaving client (or attacker)
can overwhelm the server, degrading service for everyone else.

## CHOOSING AN ALGORITHM

There are several rate-limiting algorithms, each with trade-offs:

**FIXED WINDOW**  (e.g., "100 requests per minute")
   Simple: keep a counter, reset it every minute.
   Problem: a user can send 100 requests at 11:59:59 and 100 more
   at 12:00:01 — 200 requests in 2 seconds.  This "boundary burst"
   defeats the purpose.

**SLIDING WINDOW LOG**
   Track every request timestamp.  Count how many fall in the last
   60 seconds.  Accurate, but storing a timestamp per request is
   memory-hungry at scale.

**LEAKY BUCKET**
   Requests enter a queue (bucket) and are processed at a fixed rate,
   like water dripping from a bucket.  Good for smoothing traffic,
   but doesn't allow ANY bursts — even legitimate ones.

==> **TOKEN BUCKET**  (what we use)
   Imagine a bucket that holds N tokens.  It refills at a steady rate
   (e.g., 1 token/second).  Each request costs 1 token.  If the
   bucket is empty, the request is rejected.

Why **TOKEN BUCKET** wins for APIs:

- Allows short bursts up to bucket capacity.  Real users click in bursts (load a page = 5 parallel API calls), not at a uniform rate.

- Enforces a long-term average rate (the refill rate).

- Memory-efficient: only stores (token_count, last_refill_time), not a list of timestamps.  Two numbers per client.

- Simple atomic implementation with Redis.
