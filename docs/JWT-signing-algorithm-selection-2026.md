# JWT Signing Algorithm Selection (February 2026 Recommendations)

## Acronyms

- **ECDSA** — Elliptic Curve Digital Signature Algorithm
- **EdDSA** — Edwards-curve Digital Signature Algorithm
- **Ed25519** — EdDSA using Curve25519 (the specific curve)

- **RSA** — Rivest-Shamir-Adleman
- **RSASSA-PSS** — RSA Signature Scheme with Appendix - Probabilistic Signature Scheme
- **RSASSA-PKCS#1** — RSA Signature Scheme with Appendix - Public-Key Cryptography Standards #1

- **HMAC** — Hash-based Message Authentication Code
- **SHA-256** — Secure Hash Algorithm, 256-bit

- **HSM** — Hardware Security Module
- **KMS** — Key Management Service

- **JWE** — JSON Web Encryption
- **JWK** — JSON Web Key
- **JWKS** — JSON Web Key Set
- **JOSE** — JSON Object Signing and Encryption

## Recommended (in order of preference)

### EdDSA (Ed25519) — the modern choice

Fastest signing and verification of all asymmetric options (62x faster signing than RSA-2048, 14x faster than ES256)
64-byte signatures (compact)
Designed with constant-time implementations to resist side-channel attacks

**Caveat:** HSM support is still catching up — AWS KMS added Ed25519 in late 2025, Azure Key Vault still lacks it

### ES256 (ECDSA with P-256 + SHA-256) — the safe default

Small keys (256-bit) and small signatures
Excellent HSM and cloud KMS support across all major providers
Good balance of performance, security, and ecosystem compatibility

### PS256 (RSASSA-PSS with SHA-256) — RSA done right

Provably secure padding scheme, unlike PKCS#1 v1.5
Use this if you need RSA (legacy systems, specific compliance requirements)
Larger keys (2048+ bit) and signatures than EC-based options

## Acceptable but not preferred

### RS256 (RSASSA-PKCS#1 v1.5 with SHA-256) — widest compatibility

Most broadly supported across every stack and library
Fine for existing systems, but prefer PS256 for new RSA deployments
PKCS#1 v1.5 padding has had historical vulnerabilities (Bleichenbacher attacks)

================================

## Avoid

HS256/HS384/HS512 (HMAC) for multi-party systems — symmetric key means the verifier can also forge tokens. Only appropriate when issuer and verifier are the same service.
alg: none — must always be rejected; a classic JWT attack vector

RS384/RS512 without reason — larger hashes add overhead without meaningful security gain over RS256 with a 2048+ bit key
