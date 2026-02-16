# Cache Design

## CACHING PATTERNS — A COMPARISON

1. **READ-THROUGH**  (Using This One)
   Flow:  Client → Cache → miss → DB → populate cache → return
          Client → Cache → hit  → return (skip DB entirely)

   The application asks the cache first.  On a miss, it fetches from
   the source of truth, stores the result in cache, and returns it.
   Simple, predictable, easy to debug.

2. **CACHE-ASIDE**
   Same as read-through, but the caller explicitly manages both the
   cache and the DB as separate calls.  Read-through wraps this into
   a single, cleaner pattern.

3. **WRITE-THROUGH**
   Every write goes to both the cache and the DB simultaneously.
   Guarantees the cache is always fresh, but doubles write latency.

4. **WRITE-BEHIND** (Dangerous, Don't Use)
   Writes go to cache immediately, then flush to DB asynchronously.
   Fastest writes, but risks data loss if the cache crashes before
   the flush completes.  

## CACHE INVALIDATION

Two complementary strategies:

  1. TTL (Time To Live): Every cached entry auto-expires after N seconds.
     This is the SAFETY NET — even if we forget to invalidate somewhere,
     stale data disappears on its own.

  2. Explicit invalidation: When data changes (e.g., a new progress event
     is ingested), we immediately delete the cached entry.  This gives
     near-instant consistency for the common case.

WHY BOTH:

- TTL alone → users see stale data for up to N seconds after a change
- Explicit alone → a bug that skips the delete leaves stale data forever
- Together → they cover each other's weaknesses
