# JWT Hashing Selection

## argon2-cffi — recommended for a new project

Argon2id won the Password Hashing Competition (2015) and is the current OWASP recommendation

Memory-hard — resistant to GPU/ASIC brute-force attacks in a way bcrypt is not

Single-purpose library, simple API: PasswordHasher().hash(password) / .verify(hash, password)

**Actively maintained**, wraps the reference C implementation

## passlib + bcrypt — the established option found in older implementations

Bcrypt is battle-tested and still considered secure, but it's not memory-hard

Passlib adds a nice abstraction layer with CryptContext for multi-algorithm support and automatic hash migration

However, passlib's **maintenance has been inconsistent** — there were long periods with no releases
